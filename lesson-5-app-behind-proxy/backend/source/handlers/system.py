from source.config import settings
from source.storage import events


def health():
    return {"status": "ok", "stored": len(events), "limit": settings.EVENT_LIMIT}


def whoami(request):
    """Всё, что приложение знает о том, кто к нему пришёл"""
    return {
        "remote_addr": request.remote_addr,
        "host": request.headers.get("Host"),
        "x_real_ip": request.headers.get("X-Real-IP"),
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
    }
