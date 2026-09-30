from flask import Blueprint, jsonify, request

import source.handlers.system as system_handler

router = Blueprint("system", __name__)


@router.get("/health")
def health():
    """
    Живо ли приложение и доступна ли база
    ---
    responses:
      200:
        description: статус и сколько событий лежит в базе
      503:
        description: база не отвечает
    """
    body, status = system_handler.health()
    return jsonify(body), status


@router.get("/whoami")
def whoami():
    """
    Показать, что приложение видит о запросе
    ---
    responses:
      200:
        description: адрес соединения и заголовки от прокси
    """
    return jsonify(system_handler.whoami(request))
