import logging
import os
from logging.handlers import RotatingFileHandler

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "mobile_router.log"


def configure_logging(app):
    log_level_name = os.environ.get("MOBILE_ROUTER_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_dir = os.environ.get("MOBILE_ROUTER_LOG_DIR", DEFAULT_LOG_DIR)
    log_path = os.path.join(log_dir, DEFAULT_LOG_FILE)

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    app.logger.setLevel(log_level)

    for handler in app.logger.handlers:
        handler.setFormatter(formatter)
        handler.setLevel(log_level)

    if not any(getattr(handler, "_mobile_router_file_handler", False) for handler in app.logger.handlers):
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(log_path, maxBytes=512_000, backupCount=2)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        file_handler._mobile_router_file_handler = True
        app.logger.addHandler(file_handler)

    return log_path
