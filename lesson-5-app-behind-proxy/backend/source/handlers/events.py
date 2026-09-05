import logging
from datetime import datetime, timezone

from source.storage import events

log = logging.getLogger(__name__)


def client_ip(request):
    """За прокси remote_addr это адрес nginx, настоящий адрес приезжает заголовком"""
    return request.headers.get("X-Real-IP", request.remote_addr)


def create_event(body, request):
    event = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": body["source"],
        "message": body["message"],
        "client_ip": client_ip(request),
    }
    events.appendleft(event)
    log.info("событие от %s (%s): %s", event["source"], event["client_ip"], event["message"])
    return event


def list_events(source):
    found = [event for event in events if source is None or event["source"] == source]
    log.debug("отдали %s событий, фильтр source=%s", len(found), source)
    return found
