# Урок 11. Метрики и алерты

В уроке 10 цифры по памяти и CPU доставались из API Netdata ручными запросами, а о падении сервиса узнавали от пользователей. Здесь цифры отдаёт само приложение, Prometheus собирает их каждые 5 секунд, а правила и Alertmanager решают, когда сообщить человеку

К стеку из урока 6 добавляются четыре части: эндпоинт `/metrics` в приложении, Prometheus, экспортёр для Postgres и Alertmanager

---

## 1. Как это устроено

```
backend :5000/metrics  ◀──┐
                          ├── prometheus :9090 ──▶ alertmanager :9093 ──▶ получатель
postgres-exporter :9187 ◀─┘
```

| Контейнер | Роль |
|---|---|
| `backend` | приложение из урока 6 с новым эндпоинтом `/metrics` |
| `postgres-exporter` | отдаёт состояние Postgres в том же формате, у самой базы `/metrics` нет |
| `prometheus` | раз в 5 секунд опрашивает обе цели, хранит значения, вычисляет правила алертов |
| `alertmanager` | принимает сработавшие алерты и доставляет их получателю |

Prometheus сам приходит за метриками (pull), приложение ничего не отправляет. Поэтому падение цели фиксируется без участия самой цели: на каждом опросе Prometheus записывает метрику `up`, 1 если цель ответила и 0 если нет

---

## 2. Запуск

Стек поднимается из папки урока:

```bash
cp .env.example .env
docker compose up -d --build
```

```
$ docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
SERVICE             STATUS                    PORTS
alertmanager        Up 18 seconds             127.0.0.1:9093->9093/tcp
backend             Up 12 seconds             5000/tcp
nginx               Up 12 seconds             0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
postgres            Up 18 seconds (healthy)   5432/tcp
postgres-exporter   Up 12 seconds             9187/tcp
prometheus          Up 18 seconds             127.0.0.1:9090->9090/tcp
```

---

## 3. Метрики приложения

```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/metrics').read().decode())" | grep -E '^(http_|events_)'
```

После нескольких запросов к приложению (три `POST /events`, пять `GET /health`, один несуществующий адрес) вывод такой, лишнее убрано:

```
http_requests_total{method="POST",path="/events",status="201"} 3.0
http_requests_total{method="GET",path="/health",status="200"} 5.0
http_requests_total{method="GET",path="unmatched",status="404"} 1.0
http_request_duration_seconds_bucket{le="0.025",path="/health"} 5.0
http_request_duration_seconds_bucket{le="0.05",path="/health"} 5.0
...
http_request_duration_seconds_bucket{le="+Inf",path="/health"} 5.0
http_request_duration_seconds_count{path="/health"} 5.0
http_request_duration_seconds_sum{path="/health"} 0.04654330000005302
events_received_total 3.0
```

Метрика это строка вида `имя{метки} значение`. Каждая комбинация имени и меток образует отдельный ряд, поэтому у `http_requests_total` три ряда, а Prometheus хранит для каждого историю значений

| Тип | Как ведёт себя | Где в уроке |
|---|---|---|
| counter | только растёт, при рестарте приложения обнуляется | `http_requests_total`, `events_received_total` |
| histogram | счётчики по корзинам: `le="0.05"` это число запросов быстрее 0.05 с | `http_request_duration_seconds_*` |
| gauge | значение растёт и падает | `pg_up` в разделе 6 |

### Что изменилось в приложении

| Файл | Что изменилось |
|---|---|
| [requirements.txt](backend/requirements.txt) | добавилась библиотека `prometheus-client` |
| [source/metrics.py](backend/source/metrics.py) | определения метрик и два хука Flask: замер времени до запроса и запись после ответа |
| [main.py](backend/main.py) | `metrics.init(app)` подключает хуки |
| [routers/system.py](backend/source/routers/system.py) | маршрут `/metrics` отдаёт `generate_latest()` |
| [handlers/events.py](backend/source/handlers/events.py) | `events_received.inc()` после записи события в базу |
| [nginx/site.conf](nginx/site.conf) | `/metrics` отвечает 404 |

Определения метрик:

```python
# Метка path берётся из шаблона маршрута (/events). Реальный адрес породил бы
# новый временной ряд на каждый случайный URL от сканера, и Prometheus пух бы
requests_total = Counter(
    "http_requests_total", "HTTP-запросы", ["method", "path", "status"]
)
request_seconds = Histogram(
    "http_request_duration_seconds", "Время ответа на запрос", ["path"]
)
```

Три аргумента `Counter`: имя метрики, описание и список имён меток. Метки задаёт код приложения, Prometheus читает то, что приложение напечатало

Метки играют роль колонок таблицы, а счётчик это колонка с числом. Каждая строка вывода `/metrics` соответствует строке такой таблицы:

| method | path | status | http_requests_total |
|---|---|---|---|
| POST | /events | 201 | 3 |
| GET | /health | 200 | 5 |
| GET | unmatched | 404 | 1 |

| Что | Как устроено |
|---|---|
| строки | строка появляется с первым запросом такой комбинации. Пока не было ни одного ответа 500, строки с `status="500"` в выводе нет |
| порядок | значения подставляются по позициям: `.labels(request.method, path, response.status_code)` идёт в том же порядке, что и `["method", "path", "status"]` |
| `unmatched` | адреса, не совпавшие ни с одним маршрутом, в том числе запросы сканеров, считаются и сворачиваются в одну строку |
| `/metrics` | запросы к самому `/metrics` в счётчик не попадают |

Метки позволяют задавать вопросы к одному счётчику: фильтровать строки (`status=~"5.."` оставляет ошибки, раздел 7) и сворачивать колонки (`sum by (status)`, раздел 5). Без них остался бы единственный счётчик «запросов всего»

Каждая уникальная комбинация значений это отдельный ряд, поэтому число рядов растёт вместе с числом разных значений в колонках. У `method` и `status` значений немного. У `path` без шаблона их было бы без предела: `/users/1`, `/users/2`, случайные адреса сканеров. По этой причине в метку идёт шаблон маршрута (`/users/<id>`), и ряд получается один на маршрут

У гистограммы метка одна, `path`: на каждое её значение приходится 17 рядов (15 корзин, `_count` и `_sum`), и дополнительные метки умножали бы это число

Prometheus ходит к `backend:5000` напрямую по docker-сети, поэтому снаружи через nginx метрики не нужны:

```
$ curl -i -s localhost:8080/metrics | head -1
HTTP/1.1 404 Not Found
```

---

## 4. Prometheus

Весь конфиг, [prometheus/prometheus.yml](prometheus/prometheus.yml):

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

rule_files:
  - alerts.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: backend
    static_configs:
      - targets: ["backend:5000"]

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]
```

| Ключ | Что значит |
|---|---|
| `scrape_interval` | как часто опрашивать цели. В проде 15-60 секунд, 5 секунд в уроке ради быстрого результата |
| `evaluation_interval` | как часто вычислять правила алертов |
| `rule_files` | файл с правилами, раздел 7 |
| `alerting` | куда отправлять сработавшие алерты |
| `job_name` | имя группы целей, попадает в метку `job` каждого ряда |
| `targets` | адрес цели по имени сервиса из compose, как `proxy_pass` в nginx |

Данные Prometheus живут на volume `promdata`, как данные Postgres в уроке 6

Результат опроса виден в метрике `up`:

```
$ curl -s -G localhost:9090/api/v1/query --data-urlencode 'query=up'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"up","instance":"backend:5000","job":"backend"},"value":[1795522848.696,"1"]},{"metric":{"__name__":"up","instance":"postgres-exporter:9187","job":"postgres"},"value":[1795522848.696,"1"]}]}}
```

Метки `job` и `instance` Prometheus дописал сам, обе цели отвечают

---

## 5. Запросы

У учебного стека нет пользователей, поэтому к сервису идут тестовые запросы: 60 штук к `/health` за полминуты

```bash
for i in $(seq 60); do curl -s -o /dev/null localhost:8080/health; sleep 0.5; done
```

Затем Prometheus спрашивают, сколько запросов в секунду пришло за последнюю минуту:

```
$ curl -s -G localhost:9090/api/v1/query --data-urlencode 'query=sum(rate(http_requests_total[1m]))'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1795522848.703,"1.0226628571428573"]}]}}
```

Текст в `query` написан на PromQL, языке запросов самого Prometheus. `curl` отправляет его в HTTP API, Prometheus вычисляет и возвращает JSON, а в `value` лежат время вычисления и результат

Те же запросы с другим значением `query` и результаты:

| Запрос | Результат | Что значит |
|---|---|---|
| `sum(rate(http_requests_total[1m]))` | `1.02` | в среднем 1 запрос в секунду за последнюю минуту |
| `sum by (status) (rate(http_requests_total[1m]))` | `200`: 1.02, остальные коды 0 | то же в разбивке по коду ответа |
| `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[1m])))` | `0.024` | 95% запросов отвечают быстрее 0.024 с |

Цикл идёт полминуты со скоростью 2 запроса в секунду. Окно `[1m]` усредняет скорость по всей минуте: 60 запросов делятся на 60 секунд, отсюда около 1

| Часть запроса | Что делает |
|---|---|
| `[1m]` | окно в одну минуту: берутся все значения ряда за это время |
| `rate()` | скорость роста счётчика в секунду. Сам счётчик показывает сумму за всё время жизни, а скорость показывает, что происходит сейчас |
| `sum()` | складывает ряды в один |
| `by (status)` | складывает ряды, сохраняя разбивку по метке |
| `histogram_quantile(0.95, ...)` | оценивает перцентиль по корзинам гистограммы |

---

## 6. Экспортёр

У Postgres своего `/metrics` нет, его роль играет отдельный контейнер:

```yaml
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.17.1
    environment:
      DATA_SOURCE_NAME: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?sslmode=disable
    depends_on:
      postgres:
        condition: service_healthy
```

Экспортёр подключается к базе как обычный клиент, по тому же логину и паролю из `.env`, и пересказывает её состояние в формате Prometheus. Одна из метрик, `pg_up`, показывает, отвечает ли база:

```
$ curl -s -G localhost:9090/api/v1/query --data-urlencode 'query=pg_up'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"pg_up","instance":"postgres-exporter:9187","job":"postgres"},"value":[1795522848.726,"1"]}]}}
```

У `up{job="postgres"}` и `pg_up` разный смысл: `up` говорит, что жив экспортёр, `pg_up` говорит, что жива база. Разница видна в разделе 7

---

## 7. Алерты

Правила в [prometheus/alerts.yml](prometheus/alerts.yml):

```yaml
groups:
  - name: backend
    rules:
      - alert: BackendDown
        expr: up{job="backend"} == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "backend не отдаёт метрики"

      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m])) > 0.05
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "больше 5% запросов заканчиваются ошибкой 5xx"
```

| Поле | Что значит |
|---|---|
| `expr` | условие в виде такого же запроса, как в разделе 5. Алерт существует, пока выражение возвращает хотя бы один ряд |
| `for` | сколько условие должно держаться до отправки алерта. Единичный всплеск человека не будит |
| `labels` | по ним Alertmanager выбирает получателя |
| `annotations` | текст для человека |
| `status=~"5.."` | фильтр по регулярному выражению: все коды, начинающиеся на 5 |

Алерт проходит три состояния:

| Состояние | Что значит |
|---|---|
| inactive | условие не выполняется |
| pending | условие выполняется, но `for` ещё не истекло |
| firing | условие держится дольше `for`, алерт ушёл в Alertmanager |

Alertmanager в уроке настроен без доставки, [alertmanager/alertmanager.yml](alertmanager/alertmanager.yml):

```yaml
route:
  receiver: default

receivers:
  - name: default
```

Получатель `default` ничего не отправляет: алерт принят и виден в интерфейсе. Куда слать, описывается в блоке `receivers`, это задача практики

### Упал backend

```bash
docker compose stop backend
```

Через 15 секунд алерт ждёт `for`:

```
$ curl -s localhost:9090/api/v1/alerts
{"status":"success","data":{"alerts":[{"labels":{"alertname":"BackendDown","instance":"backend:5000","job":"backend","severity":"critical"},"annotations":{"summary":"backend не отдаёт метрики"},"state":"pending","activeAt":"2026-11-24T12:21:05.806484505Z","value":"0e+00"}]}}
```

Через 45 секунд он `firing` и дошёл до Alertmanager, вывод сокращён:

```
$ curl -s localhost:9093/api/v2/alerts
[{"annotations":{"summary":"backend не отдаёт метрики"},...,"labels":{"alertname":"BackendDown","instance":"backend:5000","job":"backend","severity":"critical"},"receivers":[{"name":"default"}],"status":{"inhibitedBy":[],"mutedBy":[],"silencedBy":[],"state":"active"},...}]
```

### Упала база

Backend поднят обратно (`docker compose start backend`). Без базы он остаётся живым и отвечает на `/health` кодом 503, на запись события кодом 500. Алерт `HighErrorRate` ловит долю таких ответов среди всех ответов приложения, она считается по `http_requests_total`. Экспортёр Postgres в этом алерте не участвует

Ошибки появляются только на запросах, поэтому в одном терминале идёт постоянный трафик, он играет роль пользователей. Цикл работает до остановки через `Ctrl+C`:

```bash
while true; do curl -s -o /dev/null localhost:8080/health; sleep 1; done
```

Во втором терминале останавливается Postgres:

```bash
docker compose stop postgres
```

Примерно через минуту:

```
$ curl -s localhost:9090/api/v1/alerts
{"status":"success","data":{"alerts":[{"labels":{"alertname":"HighErrorRate","severity":"critical"},"annotations":{"summary":"больше 5% запросов заканчиваются ошибкой 5xx"},"state":"firing","activeAt":"2026-11-24T12:22:20.806484505Z","value":"1e+00"}]}}
```

`value` 1 это доля ошибок 100%. Для сравнения, экспортёр в это время жив и сообщает, что базы нет: `up` у обеих целей равен 1, `pg_up` равен 0:

```
$ curl -s -G localhost:9090/api/v1/query --data-urlencode 'query=pg_up'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"pg_up","instance":"postgres-exporter:9187","job":"postgres"},"value":[1795523171.308,"0"]}]}}
```

| Что сломали | `up{job="backend"}` | `pg_up` | `BackendDown` | `HighErrorRate` |
|---|---|---|---|---|
| остановлен backend | 0 | 1 | сработал | молчит, запросов к приложению нет, считать нечего |
| остановлен Postgres | 1 | 0 | молчит, процесс жив | сработал |

Приложение с лежащей базой отвечает на `/metrics`, поэтому для одного `BackendDown` это выглядит как «всё работает». Доля ошибок видит то, что видит пользователь

---

## 8. Что считать

| Что | Метрика в уроке | Алерт |
|---|---|---|
| доступность | `up` | `BackendDown` |
| доля ошибок | `http_requests_total` по кодам 5xx | `HighErrorRate` |
| скорость запросов | `http_requests_total` | нет, нужна как фон при чтении графиков |
| время ответа | `http_request_duration_seconds` | в практике |
| состояние базы | `pg_up` | в практике |
| результат для продукта | `events_received_total` | в практике: падение до нуля при живом сервисе |
| ресурсы хоста | Netdata из урока 10 | нет |

Выбор метрик и порогов в командах это всегда компромисс, у каждого решения урока есть цена:

| Решение | Цена |
|---|---|
| алерт на долю ошибок, без алерта на загрузку CPU | рост нагрузки без ошибок алерт не поймает, он виден только на графиках |
| `for: 30s` | сообщение приходит на 30 секунд позже сбоя |
| два алерта вместо одного | два правила в поддержке, зато «процесс жив, но сервис не работает» не проходит мимо |
| метка `path` из шаблона маршрута | в метриках нет конкретных адресов, при разборе инцидента нужный адрес ищется в логах |

---

## 9. Практика: узнать о поломке раньше пользователя

**Легенда.** Проект работает на виртуалке, о падении приходится узнавать из сообщений пользователей. Нужно, чтобы о недоступности и о всплеске ошибок первым узнавал владелец проекта, и сразу в Telegram

Готовая работа выглядит так:

| № | Что есть в итоге |
|---|---|
| 1 | В проекте есть `/metrics`: счётчик запросов с методом, шаблоном маршрута и кодом ответа, гистограмма времени ответа, одна метрика результата для продукта. Снаружи через nginx `/metrics` недоступен |
| 2 | Prometheus и Alertmanager в compose проекта, данные Prometheus на volume, обе цели в статусе `up` |
| 3 | Для базы проекта подключён экспортёр, состояние базы видно в Prometheus |
| 4 | Алерты на недоступность сервиса, на долю ошибок и на время ответа. Пороги и `for` выбраны под проект |
| 5 | Alertmanager отправляет алерты в Telegram. Токен бота лежит вне git |
| 6 | Оба алерта проверены поломкой: остановлен backend, остановлена база. Сообщения в Telegram пришли |

Alertmanager умеет Telegram из коробки, раздел `telegram_configs` в его документации

Результат: вывод `/metrics` из проекта, скриншот целей Prometheus в статусе UP, файл правил, скриншоты сообщений в Telegram при двух поломках, ответы на два вопроса:

1. Почему выбраны именно эти пороги и значения `for`, и что пользователь успевает почувствовать до того, как сообщение придёт
2. Почему в списке алертов нет алерта на загрузку CPU

---

## Что дальше

Урок 12: Kubernetes. Приложение с базой переезжает в кластер, где `/metrics` и проверки готовности используются так же, как здесь
