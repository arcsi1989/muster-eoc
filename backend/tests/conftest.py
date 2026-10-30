from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import advisory_context
from app.agent.cycle import AdvisoryCycle
from app.agent.lifecycle import issue_next_advisory
from app.config import Settings
from app.db import create_fresh_engine
from app.ingest.loader import load_gold
from app.llm.factory import build_provider
from app.llm.provider import LLMProvider
from app.llm.schemas import DraftRequest, DraftResult, Paragraph, Prompt, Section, SitrepDraft
from app.main import create_app
from app.playbook.service import Playbook, load_playbook
from app.scoring_config import ScoringConfig, load_scoring_config

ClientFactory = Callable[..., AbstractContextManager[TestClient]]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-fixtures",
        action="store_true",
        help="rewrite the frontend's real response fixtures from fresh backend responses",
    )


def test_settings(tmp_path: Path) -> Settings:
    # _env_file=None: tests never read a local .env (CODING_STANDARDS T2).
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_path=tmp_path / "test.sqlite",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
        eval_results_path=None,  # no committed evaluation in the audit log; test_evals sets one
    )


@pytest.fixture
def make_client(tmp_path: Path) -> ClientFactory:
    """A client whose app uses the given provider instead of the one in settings."""

    @contextmanager
    def factory(llm: LLMProvider | None = None) -> Iterator[TestClient]:
        with TestClient(create_app(test_settings(tmp_path), llm)) as test_client:
            yield test_client

    return factory


@pytest.fixture
def client(make_client: ClientFactory) -> Iterator[TestClient]:
    with make_client() as test_client:
        yield test_client


@dataclass
class SeededScenario:
    """A fresh database with the gold data loaded, wired like the app but without HTTP."""

    session: Session
    playbook: Playbook
    scoring: ScoringConfig
    cycle: AdvisoryCycle

    def issue_until(self, advisory_no: int) -> None:
        """Issues advisories until `advisory_no` is current, through the app's own replay and
        advisory cycle (scoring, findings, decision package). Past the last advisory it raises
        ScenarioComplete, as the API does."""
        while advisory_context.current_advisory_no(self.session) < advisory_no:
            issue_next_advisory(self.session, self.scoring, self.cycle)
            self.session.expire_all()  # the cycle writes through its own sessions


SeededFactory = Callable[..., AbstractContextManager[SeededScenario]]


@pytest.fixture
def make_seeded(tmp_path: Path) -> SeededFactory:
    """A seeded session whose advisory cycle uses the given provider (template by default)."""

    @contextmanager
    def factory(llm: LLMProvider | None = None) -> Iterator[SeededScenario]:
        # Its own folder, so a test can use a seeded session and an HTTP client side by side.
        (tmp_path / "seeded").mkdir(exist_ok=True)
        settings = test_settings(tmp_path / "seeded").model_copy(
            update={"llm_provider": "template"}
        )
        scoring = load_scoring_config(settings.scoring_config_path)
        playbook = load_playbook(settings.playbook_rules_path, settings.playbook_path)
        engine = create_fresh_engine(settings.database_path)
        provider = llm or build_provider(settings, scoring)
        cycle = AdvisoryCycle(engine, playbook, settings.checkpoint_path, provider, scoring)
        try:
            with Session(engine) as session:
                load_gold(session, settings.data_dir)
            with Session(engine) as session:
                yield SeededScenario(session, playbook, scoring, cycle)
        finally:
            cycle.close()
            engine.dispose()

    return factory


@pytest.fixture
def seeded(make_seeded: SeededFactory) -> Iterator[SeededScenario]:
    with make_seeded() as scenario:
        yield scenario


def draft_of(*paragraphs: Paragraph) -> SitrepDraft:
    return SitrepDraft(sections=[Section(heading="Situation", paragraphs=list(paragraphs))])


class FakeProvider:
    """A fake provider: returns the given drafts in turn (or raises), and records what it was
    shown."""

    name = "fake"
    model: str | None = "fake-model"

    def __init__(self, *outputs: SitrepDraft | Exception) -> None:
        self.outputs = list(outputs)
        self.requests: list[DraftRequest] = []
        self.prompts: list[Prompt] = []

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
        self.requests.append(request)
        self.prompts.append(prompt)
        output = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(output, Exception):
            raise output
        usage = {"input_tokens": 100, "output_tokens": 50}
        return DraftResult(output, self.name, self.model, prompt.version, 42, usage)
