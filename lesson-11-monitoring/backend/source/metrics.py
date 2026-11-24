import time

from flask import g, request
from prometheus_client import Counter, Histogram, disable_created_metrics

# Без служебных рядов *_created: они хранят время создания метрики и только
# засоряют вывод. Вызов стоит до создания самих метрик
disable_created_metrics()

# Метка path берётся из шаблона маршрута (/events). Реальный адрес породил бы
# новый временной ряд на каждый случайный URL от сканера, и Prometheus пух бы
requests_total = Counter(
    "http_requests_total", "HTTP-запросы", ["method", "path", "status"]
)
request_seconds = Histogram(
    "http_request_duration_seconds", "Время ответа на запрос", ["path"]
)

# Метрика продукта: сколько событий приняли. Имя в коде без _total,
# библиотека дописывает суффикс счётчика сама
events_received = Counter("events_received", "Принятые события")


def init(app):
    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def record(response):
        # Запросы Prometheus к самому /metrics в статистику не идут,
        # иначе они разбавляют долю ошибок
        if request.path == "/metrics":
            return response

        path = request.url_rule.rule if request.url_rule else "unmatched"
        requests_total.labels(request.method, path, response.status_code).inc()
        request_seconds.labels(path).observe(time.perf_counter() - g.started)
        return response
