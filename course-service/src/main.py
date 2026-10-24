import logging
import logging.config

import yaml

from src.core.config import get_settings
from src.web.app import create_app
from src.web.lifespans import lifespan_app
from src.web.routers import all_routers

logger = logging.getLogger(__name__)


def build_app():
    with open("log-config.yaml", encoding="UTF-8") as f:
        logging.config.dictConfig(yaml.safe_load(f))

    settings = get_settings()
    app = create_app(settings, all_routers, lifespan_app)
    logger.debug("Created app=%s settings=%s", app, settings)
    return app


app = build_app()