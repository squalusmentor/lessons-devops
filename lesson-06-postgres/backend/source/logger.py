import logging
import sys

from source.config import settings


def setup_logging():
    """Логи уходят в stdout: оттуда их забирает docker и отдаёт по docker compose logs"""
    logging.basicConfig(
        stream=sys.stdout,
        level=settings.LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
