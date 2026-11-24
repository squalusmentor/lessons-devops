def validate_event(body):
    """Проверяет тело запроса на создание события, возвращает текст ошибки или None"""
    if not isinstance(body, dict):
        return "тело запроса должно быть объектом JSON"

    if not body.get("source") or not body.get("message"):
        return "нужны поля source и message"

    return None
