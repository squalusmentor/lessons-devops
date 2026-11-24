from flask import Blueprint, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

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


@router.get("/metrics")
def metrics():
    # Без docstring со Swagger-разметкой: в документацию API маршрут не попадает
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)


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
