import logging

from flask import Blueprint, jsonify, request

import source.handlers.events as events_handler
from source.schemas.event import validate_event

router = Blueprint("events", __name__)
log = logging.getLogger(__name__)


@router.post("")
def create_event():
    """
    Записать событие
    ---
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [source, message]
          properties:
            source:
              type: string
              example: nginx
            message:
              type: string
              example: upstream timed out
    responses:
      201:
        description: событие записано
      400:
        description: в теле нет source или message
    """
    body = request.get_json(silent=True)
    error = validate_event(body)
    if error:
        log.warning("отброшено событие: %s", error)
        return jsonify(error=error), 400

    return jsonify(events_handler.create_event(body, request)), 201


@router.get("")
def list_events():
    """
    Показать записанные события, свежие сверху
    ---
    parameters:
      - in: query
        name: source
        type: string
        required: false
        description: показать только события этого источника
    responses:
      200:
        description: список событий
    """
    found = events_handler.list_events(request.args.get("source"))
    return jsonify(count=len(found), events=found)
