from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from muster.agent.cycle import AdvisoryCycle
from muster.api import (
    routes_activation,
    routes_advisories,
    routes_audit,
    routes_calibration,
    routes_challenger,
    routes_copilot,
    routes_exposure,
    routes_field,
    routes_forecast,
    routes_health,
    routes_packages,
    routes_planning,
    routes_playbook,
    routes_risk,
    routes_sitrep,
    routes_territory,
    routes_trace,
)
from muster.api.error_handlers import register_error_handlers
from muster.challenger import model as challenger_model
from muster.challenger import promotion
from muster.config import Settings, get_settings
from muster.db import create_fresh_engine
from muster.evals import audit as evals
from muster.ingest.loader import load_gold
from muster.llm.config import load_llm_config
from muster.llm.factory import build_provider
from muster.llm.provider import LLMProvider
from muster.models_config import load_models_config
from muster.playbook.service import load_playbook
from muster.scoring_config import load_scoring_config
from muster.tracing import store as tracing


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None) -> FastAPI:
    """`llm` overrides the provider chosen from settings (tests inject a fake: T2)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scoring = load_scoring_config(settings.scoring_config_path)
        provider = llm or build_provider(settings, scoring)  # fails without a key
        app.state.llm = provider
        engine = create_fresh_engine(settings.database_path)
        trained = challenger_model.load(settings.challenger_model_path)
        with Session(engine) as session:
            load_gold(session, settings.data_dir)
            app.state.challenger = promotion.register(session, trained) if trained else None
            evals.record_latest(session, settings.eval_results_path)
            session.commit()
        app.state.engine = engine
        llm_config = load_llm_config(settings.llm_config_path)
        app.state.llm_config = llm_config
        tracing.start(
            engine,
            llm_config,
            settings.otel_exporter_otlp_endpoint,
            settings.otel_exporter_otlp_timeout_s,
        )
        app.state.playbook = load_playbook(settings.playbook_rules_path, settings.playbook_path)
        app.state.cycle = AdvisoryCycle(
            engine, app.state.playbook, settings.checkpoint_path, provider, scoring
        )
        app.state.settings = settings
        app.state.scoring_config = scoring
        app.state.models_config = load_models_config(settings.models_config_path)
        yield
        tracing.stop()
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
        routes_forecast,
        routes_playbook,
        routes_packages,
        routes_planning,
        routes_activation,
        routes_audit,
        routes_sitrep,
        routes_copilot,
        routes_calibration,
        routes_challenger,
        routes_field,
        routes_trace,
    ):
        app.include_router(router.router)
    return app


app = create_app()
