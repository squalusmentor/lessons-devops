from flask import Blueprint, jsonify, request

import source.handlers.system as system_handler

router = Blueprint("system", __name__)


@router.get("/health")
def health():
    """
    Живо ли приложение
    ---
    responses:
      200:
        description: статус и сколько событий лежит в памяти
    """
    return jsonify(system_handler.health())


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
