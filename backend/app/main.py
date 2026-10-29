from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app.agent.cycle import AdvisoryCycle
from app.api import (
    routes_advisories,
    routes_audit,
    routes_exposure,
    routes_health,
    routes_packages,
    routes_playbook,
    routes_risk,
    routes_sitrep,
    routes_territory,
)
from app.config import Settings, get_settings
from app.db import create_fresh_engine
from app.errors import register_error_handlers
from app.ingest.loader import load_gold
from app.llm.factory import build_provider
from app.llm.provider import LLMProvider
from app.playbook.service import load_playbook
from app.scoring_config import load_scoring_config


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None) -> FastAPI:
    """`llm` overrides the provider chosen from settings (tests inject a fake: T2)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scoring = load_scoring_config(settings.scoring_config_path)
        provider = llm or build_provider(settings, scoring.draft.max_tokens)  # fails without a key
        engine = create_fresh_engine(settings.database_path)
        with Session(engine) as session:
            load_gold(session, settings.data_dir)
        app.state.engine = engine
        app.state.playbook = load_playbook(settings.playbook_rules_path, settings.playbook_path)
        app.state.cycle = AdvisoryCycle(
            engine, app.state.playbook, settings.checkpoint_path, provider, scoring.draft
        )
        app.state.settings = settings
        app.state.scoring_config = scoring
        yield
        app.state.cycle.close()
        engine.dispose()

    app = FastAPI(title="SGW storm preparation prototype", lifespan=lifespan)
    register_error_handlers(app)
    for router in (
        routes_health,
        routes_advisories,
        routes_territory,
        routes_exposure,
        routes_risk,
        routes_playbook,
        routes_packages,
        routes_audit,
        routes_sitrep,
    ):
        app.include_router(router.router)
    return app


app = create_app()
