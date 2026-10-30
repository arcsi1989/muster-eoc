"""Runs golden cases the way the app runs them: a fresh database with the gold data, advisories
issued through the advisory cycle, setup steps through the decision package lifecycle, then the
copilot's `answer` or the draft's grounded generation with the provider under evaluation. Each
run gives a transcript: what the model was shown, what it answered, and what changed."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, col, select

from app import advisory_context
from app.agent import lifecycle
from app.agent.cycle import AdvisoryCycle
from app.agent.decisions import DecisionRequest, Declaration
from app.agent.draft import produce_draft
from app.agent.draft_request import draft_request
from app.agent.field import FieldReportRequest
from app.classification import RESTRICTED_KEYS
from app.config import Settings
from app.copilot.chat import ToolCall, answer
from app.db import create_fresh_engine
from app.errors import DataNotLoaded
from app.evals.golden import Case, Step
from app.ingest.loader import load_gold
from app.llm.provider import LLMProvider
from app.llm.schemas import PackageDraft, Prompt
from app.llm.template import TemplateProvider
from app.models import (
    Advisory,
    Asset,
    DecisionPackage,
    Facility,
    FieldReport,
    OpState,
    PackageItem,
    Sitrep,
    StagingArea,
)
from app.playbook.service import Playbook, load_playbook
from app.scoring_config import ScoringConfig, load_scoring_config

DRAFT_REQUEST = "draft_request"  # the one "tool call" of a draft: the request it was shown


@dataclass(frozen=True)
class Prompts:
    """The prompts under evaluation; a candidate prompt replaces one here."""

    copilot: Prompt
    sitrep: Prompt


@dataclass(frozen=True)
class Transcript:
    question: str | None
    answer: str
    tool_calls: list[ToolCall]  # what the model called and was shown, in order
    citations: list[str]
    provider: str
    fallback: bool
    model: str | None
    prompt_version: str | None
    # operational state, decisions, reports or approvals the run changed
    state_changes: list[str] = field(default_factory=list)
    restricted_values: dict[str, list[float]] = field(default_factory=dict)  # of named entities
    draft: dict[str, Any] | None = None  # a sitrep case's draft as the package stores it
    draft_items: list[dict[str, Any]] = field(default_factory=list)  # its gaps and conflicts
    approved: list[str] = field(default_factory=list)  # rule and entity IDs of approved items

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _rows(session: Session, model: type[SQLModel]) -> dict[str, str]:
    return {
        json.dumps(
            row.model_dump(include=_KEYS[model]), default=str, sort_keys=True
        ): model.__name__
        for row in session.exec(select(model))
    }


# What a case must never change: operational state, decisions, field reports, approvals.
_KEYS: dict[type[SQLModel], set[str]] = {
    OpState: {"entity", "key", "value"},
    PackageItem: {"id", "status", "decided_by"},
    FieldReport: {"item_id", "status"},
    Sitrep: {"advisory_no", "approved_by"},
}


def _state(session: Session) -> dict[str, str]:
    session.expire_all()
    state: dict[str, str] = {}
    for model in _KEYS:
        state |= _rows(session, model)
    return state


def _changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    gone = [f"{before[k]} was {k}" for k in sorted(before.keys() - after.keys())]
    new = [f"{after[k]} is {k}" for k in sorted(after.keys() - before.keys())]
    return gone + new


def _restricted_values(session: Session, ids: list[str]) -> dict[str, list[float]]:
    values: dict[str, list[float]] = {}
    for entity_id in ids:
        for model in (Asset, Facility, StagingArea):
            row = session.get(model, entity_id)
            if row is not None:
                dumped = row.model_dump()
                values[entity_id] = [
                    float(v)
                    for k, v in dumped.items()
                    if k in RESTRICTED_KEYS and isinstance(v, int | float)
                ]
    return values


class World:
    """One scenario: the app's pieces over a fresh database. The advisory cycle drafts with the
    template, so only the case under evaluation calls the provider."""

    def __init__(self, folder: Path, settings: Settings) -> None:
        self.scoring: ScoringConfig = load_scoring_config(settings.scoring_config_path)
        self.playbook: Playbook = load_playbook(
            settings.playbook_rules_path, settings.playbook_path
        )
        self._engine = create_fresh_engine(folder / "eval.sqlite")
        with Session(self._engine) as session:
            load_gold(session, settings.data_dir)
        self._template = TemplateProvider.from_config(self.scoring)
        self._cycle = AdvisoryCycle(
            self._engine, self.playbook, folder / "checkpoints.sqlite", self._template, self.scoring
        )
        self.session = Session(self._engine)

    def close(self) -> None:
        self.session.close()
        self._cycle.close()
        self._engine.dispose()

    def issue_until(self, advisory_no: int) -> None:
        while advisory_context.current_advisory_no(self.session) < advisory_no:
            lifecycle.issue_next_advisory(self.session, self.scoring, self._cycle)
            self.session.expire_all()  # the cycle writes through its own sessions

    def _item(self, advisory_no: int, rule_id: str, entity_id: str) -> int:
        item = self.session.exec(
            select(PackageItem).where(
                PackageItem.advisory_no == advisory_no,
                PackageItem.rule_id == rule_id,
                PackageItem.entity_id == entity_id,
            )
        ).first()
        if item is None or item.id is None:
            raise DataNotLoaded(f"no item {rule_id} {entity_id} at advisory {advisory_no}")
        return item.id

    def apply(self, step: Step) -> None:
        self.issue_until(step.at)
        if step.rename_asset:
            asset = self.session.get(Asset, step.rename_asset.asset_id)
            if asset is None:
                raise DataNotLoaded(f"no asset {step.rename_asset.asset_id}")
            asset.name = step.rename_asset.name
            self.session.add(asset)
            self.session.commit()
        elif step.declare:
            declaration = Declaration(step.declare.level, step.declare.role)
            lifecycle.declare(self.session, self._cycle, declaration)
        elif step.decide:
            d = step.decide
            item_id = self._item(step.at, d.rule_id, d.entity_id)
            request = DecisionRequest(d.role, d.action)
            lifecycle.decide(self.session, self.playbook, self._cycle, step.at, item_id, request)
        elif step.report_field:
            r = step.report_field
            item_id = self._item(step.at, r.rule_id, r.entity_id)
            report = FieldReportRequest(r.district, r.outcome, r.note)
            lifecycle.report_field_work(self.session, self.playbook, self._cycle, item_id, report)
        self.session.expire_all()

    def run(self, case: Case, provider: LLMProvider, prompts: Prompts) -> Transcript:
        """One run of `case` at its advisory, which must be current."""
        before = _state(self.session)
        if case.task == "copilot":
            transcript = self._ask(case, provider, prompts.copilot)
        else:
            transcript = self._draft(case, provider, prompts.sitrep)
        changes = _changes(before, _state(self.session))
        restricted = _restricted_values(self.session, case.expect.restricted_values_of)
        return replace(transcript, state_changes=changes, restricted_values=restricted)

    def _ask(self, case: Case, provider: LLMProvider, prompt: Prompt) -> Transcript:
        question = case.question or ""
        result = answer(self.session, self.playbook, provider, question, [], self.scoring, prompt)
        return Transcript(
            question=question,
            answer=result.text,
            tool_calls=result.tool_calls,
            citations=[c.id for c in result.citations],
            provider=result.provider,
            fallback=result.fallback,
            # the answering model; the template answers with no model and no prompt
            model=None if result.fallback else provider.model,
            prompt_version=None if result.fallback or provider.model is None else prompt.version,
        )

    def _draft(self, case: Case, provider: LLMProvider, prompt: Prompt) -> Transcript:
        advisory = self.session.get(Advisory, case.advisory)
        package = self.session.get(DecisionPackage, case.advisory)
        if advisory is None or package is None:
            raise DataNotLoaded(f"advisory {case.advisory} has no decision package")
        config = self.scoring.draft
        request = draft_request(self.session, advisory, self.playbook, package.changes, config)
        outcome = produce_draft(provider, self._template, prompt, request, 1 + config.retries)
        draft = PackageDraft(
            provider=outcome.provider,
            fallback=outcome.fallback,
            model=outcome.result.model,
            prompt_version=outcome.prompt_version,
            fallback_reason=outcome.fallback_reason,
            sections=outcome.result.draft.sections,
        )
        cited = [
            i
            for s in draft.sections
            for p in s.paragraphs
            for i in dict.fromkeys(p.clause_ids + p.asset_ids)
        ]
        approved = self.session.exec(
            select(PackageItem).where(
                col(PackageItem.advisory_no) <= case.advisory, PackageItem.status == "approved"
            )
        ).all()
        return Transcript(
            question=None,
            answer=draft.text(),
            tool_calls=[ToolCall(DRAFT_REQUEST, {}, request.shown())],
            citations=list(dict.fromkeys(cited)),
            provider=draft.provider,
            fallback=draft.fallback,
            model=draft.model,
            prompt_version=draft.prompt_version,
            draft=draft.model_dump(mode="json"),
            draft_items=[asdict(i) for i in request.items if i.kind in ("gap", "conflict")],
            approved=sorted({i.rule_id for i in approved} | {i.entity_id for i in approved}),
        )


@contextmanager
def world(folder: Path, settings: Settings) -> Iterator[World]:
    folder.mkdir(parents=True, exist_ok=True)
    w = World(folder, settings)
    try:
        yield w
    finally:
        w.close()
