import logging

import psycopg

from source import db
from source.config import settings

log = logging.getLogger(__name__)


def health():
    """Живо ли приложение и отвечает ли база. Возвращает тело ответа и код"""
    try:
        stored = db.count()
    except psycopg.OperationalError as error:
        log.error("база недоступна: %s", error)
        return {"status": "error", "detail": "база недоступна"}, 503

    return {"status": "ok", "stored": stored, "limit": settings.EVENT_LIMIT}, 200


def whoami(request):
    """Всё, что приложение знает о том, кто к нему пришёл"""
    return {
        "remote_addr": request.remote_addr,
        "host": request.headers.get("Host"),
        "x_real_ip": request.headers.get("X-Real-IP"),
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
    }
