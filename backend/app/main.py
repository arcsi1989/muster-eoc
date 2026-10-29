from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app.api import (
    routes_advisories,
    routes_exposure,
    routes_health,
    routes_playbook,
    routes_risk,
    routes_territory,
)
from app.config import Settings, get_settings
from app.db import create_fresh_engine
from app.errors import register_error_handlers
from app.ingest.loader import load_gold
from app.playbook.service import load_playbook
from app.scoring_config import load_scoring_config


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_fresh_engine(settings.database_path)
        with Session(engine) as session:
            load_gold(session, settings.data_dir)
        app.state.engine = engine
        app.state.playbook = load_playbook(settings.playbook_rules_path, settings.playbook_path)
        app.state.scoring_config = load_scoring_config(settings.scoring_config_path)
        yield
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
    ):
        app.include_router(router.router)
    return app


app = create_app()
