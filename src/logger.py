import logging
from logging.handlers import RotatingFileHandler

from constants import (
    LOG_FILE_FORMAT_STRING,
    LOG_FILE_MAX_SIZE,
    LOG_FILE_NAME,
)

formatter = logging.Formatter(LOG_FILE_FORMAT_STRING)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

rotating_handler = RotatingFileHandler(
    LOG_FILE_NAME,
    mode="a",
    maxBytes=LOG_FILE_MAX_SIZE,
)
rotating_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[stream_handler, rotating_handler])

logger = logging.getLogger("wallpaper_changer")
