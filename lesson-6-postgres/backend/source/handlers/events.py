import logging

from source import db

log = logging.getLogger(__name__)


def client_ip(request):
    """За прокси remote_addr это адрес nginx, настоящий адрес приезжает заголовком"""
    return request.headers.get("X-Real-IP", request.remote_addr)


def serialize(row):
    """Строка таблицы в JSON: время из datetime в строку ISO, как было в уроке 5"""
    return {**row, "time": row["time"].isoformat(timespec="seconds")}


def create_event(body, request):
    event = db.add_event(body["source"], body["message"], client_ip(request))
    log.info("событие от %s (%s): %s", event["source"], event["client_ip"], event["message"])
    return serialize(event)


def list_events(source):
    found = [serialize(row) for row in db.list_events(source)]
    log.debug("отдали %s событий, фильтр source=%s", len(found), source)
    return found
