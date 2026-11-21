import logging.config

import yaml
from fastapi import FastAPI

from src.core.config import get_settings
from src.web.app import create_app
from src.web.lifespans import lifespan_app
from src.web.routers import all_routers


def build_app() -> FastAPI:
    with open("log-config.yaml", encoding="UTF-8") as f:
        logging.config.dictConfig(yaml.safe_load(f))

    settings = get_settings()
    return create_app(settings, all_routers, lifespan_app)


app = build_app()
