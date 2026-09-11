# Урок 6. Postgres и сохранность данных

В уроке 5 события лежали в памяти процесса: перезапустил контейнер, и их нет. Здесь на место `deque` встаёт Postgres, и появляется главный вопрос урока: где живут данные, когда контейнеры умирают, и как их не потерять

В уроке третий контейнер с базой, volume, проверка готовности базы через healthcheck, пароль в `.env`, дамп с восстановлением и автозапуск после ребута

---

## 1. Зачем база

Приложению нужно место, где данные переживут перезапуск. Первое, что приходит в голову, писать в файл. Файл внутри контейнера умирает вместе с контейнером, файл на диске хоста живёт, но как только событий станет много, начнутся проблемы: два процесса пишут одновременно и портят друг другу строки, фильтр по `source` это чтение файла целиком, удалить старое значит переписать файл

Postgres решает ровно это. Это отдельный сервер: слушает порт 5432, хранит данные в таблицах на диске, принимает запросы на SQL и сам разбирается с одновременной записью. Приложение подключается к нему по сети через драйвер, как nginx к приложению в уроке 5, только протокол свой

Вся база этого урока это одна таблица `events`:

| Колонка | Тип | Что там |
|---|---|---|
| `id` | `serial` | номер события, база выдаёт сама по порядку |
| `time` | `timestamptz` | время записи, база подставляет сама |
| `source` | `text` | кто прислал |
| `message` | `text` | текст события |
| `client_ip` | `text` | адрес клиента из `X-Real-IP` |

Весь SQL, который нужен приложению, помещается в [db.py](backend/source/db.py): создать таблицу, записать строку, выбрать строки, посчитать их

---

## 2. Три контейнера

[docker-compose.yml](docker-compose.yml) целиком:

```yaml
services:
  postgres:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build: ./backend
    restart: unless-stopped
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      EVENT_LIMIT: ${EVENT_LIMIT:-100}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy

  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "${HTTP_PORT:-8080}:80"
    volumes:
      - ./nginx/site.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend

volumes:
  pgdata:
```

Что здесь нового по сравнению с уроком 5:

| Ключ | Что значит |
|---|---|
| `image: postgres:17-alpine` | готовый образ с Docker Hub, свой Dockerfile не нужен |
| `environment` у `postgres` | по этим переменным образ при первом запуске создаёт пользователя, пароль и базу |
| `volumes: pgdata:/var/lib/postgresql/data` | папка, в которой Postgres держит данные, живёт в volume. Пункт 5 |
| `volumes: pgdata:` внизу файла | объявление этого volume на уровне проекта |
| `healthcheck` | как docker проверяет, что база готова принимать соединения. Пункт 6 |
| `depends_on` с `condition: service_healthy` | `backend` создаётся только после того, как проверка прошла |
| у `postgres` нет `ports` | база доступна только из docker-сети, снаружи в неё не попасть. Так же, как `backend` в уроке 5 |

Одни и те же `POSTGRES_*` уезжают в два сервиса: `postgres` по ним создаёт базу, `backend` по ним подключается. `POSTGRES_HOST: postgres` это имя сервиса из compose, в docker-сети оно работает как доменное имя, ровно как `backend` в `proxy_pass` из урока 5

---

## 3. Что поменялось в приложении

Раскладка та же, что в уроке 5. Поменялся слой хранения и те, кто его зовёт:

| Файл | Что изменилось |
|---|---|
| [requirements.txt](backend/requirements.txt) | добавился драйвер `psycopg` |
| [config.py](backend/source/config.py) | читает `POSTGRES_*` и собирает из них `DATABASE_URL` |
| `storage.py` стал [db.py](backend/source/db.py) | вместо `deque` четыре функции с SQL |
| [handlers/events.py](backend/source/handlers/events.py), [handlers/system.py](backend/source/handlers/system.py) | зовут функции из `db.py` вместо работы со списком |
| [routers/system.py](backend/source/routers/system.py) | `/health` отдаёт код ответа, который вернул хендлер |
| [main.py](backend/main.py) | `db.init()` при старте создаёт таблицу, если её ещё нет |
| `routers/events.py`, `schemas/`, `logger.py` | без изменений |

`DATABASE_URL` это адрес базы одной строкой, в таком виде его ждёт драйвер и в таком же виде он встречается в чужих проектах:

```
postgresql://events:change-me@postgres:5432/events
             логин  пароль    хост     порт база
```

Запись события в [db.py](backend/source/db.py):

```python
def add_event(source, message, client_ip):
    with connect() as conn:
        return conn.execute(
            "INSERT INTO events (source, message, client_ip) VALUES (%s, %s, %s) RETURNING *",
            (source, message, client_ip),
        ).fetchone()
```

`%s` это места для значений, драйвер подставляет их сам. Собирать SQL f-строкой нельзя: кто угодно пришлёт в `message` кусок SQL, и он выполнится. Это единственное правило про SQL, которое нужно знать уже сейчас

`EVENT_LIMIT` сменил смысл: в базе лежат все события, переменная ограничивает, сколько отдаёт `GET /events`

`/health` теперь ходит в базу за `count(*)`. Если база не отвечает, приложение отдаёт 503 вместо 200: жив ли сервис, теперь зависит и от базы тоже

---

## 4. Запуск и проверка

Из этой папки:

```bash
cp .env.example .env
docker compose up -d --build
```

В выводе появились две новые строки: compose дождался, пока база станет `Healthy`, и только потом взялся за `backend`:

```
 Container lesson-6-postgres-postgres-1 Started
 Container lesson-6-postgres-postgres-1 Waiting
 Container lesson-6-postgres-postgres-1 Healthy
 Container lesson-6-postgres-backend-1 Starting
 Container lesson-6-postgres-backend-1 Started
 Container lesson-6-postgres-nginx-1 Starting
 Container lesson-6-postgres-nginx-1 Started
```

```
$ docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
SERVICE    STATUS                    PORTS
backend    Up 8 seconds              5000/tcp
nginx      Up 8 seconds              0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
postgres   Up 14 seconds (healthy)   5432/tcp
```

Те же запросы, что в уроке 5, реальный вывод:

```
$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":0}

$ curl -s -X POST http://localhost:8080/events \
    -H 'Content-Type: application/json' \
    -d '{"source":"deploy","message":"release v1.3"}'
{"client_ip":"172.20.0.1","id":1,"message":"release v1.3","source":"deploy","time":"2026-09-11T17:56:09+00:00"}

$ curl -s -X POST http://localhost:8080/events \
    -H 'Content-Type: application/json' \
    -d '{"source":"cron","message":"backup ok"}'
{"client_ip":"172.20.0.1","id":2,"message":"backup ok","source":"cron","time":"2026-09-11T17:56:09+00:00"}

$ curl -s 'http://localhost:8080/events?source=cron'
{"count":1,"events":[{"client_ip":"172.20.0.1","id":2,"message":"backup ok","source":"cron","time":"2026-09-11T17:56:09+00:00"}]}

$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":2}
```

В ответе появился `id`: его выдала база

Заглянуть в базу можно напрямую, `psql` это консольный клиент Postgres, он есть в образе:

```
$ docker compose exec postgres psql -U events events
events=# \dt
        List of relations
 Schema |  Name  | Type  | Owner
--------+--------+-------+--------
 public | events | table | events
(1 row)

events=# SELECT id, time, source, message, client_ip FROM events ORDER BY id;
 id |             time              | source |   message    | client_ip
----+-------------------------------+--------+--------------+------------
  1 | 2026-09-11 17:56:09.928252+00 | deploy | release v1.3 | 172.20.0.1
  2 | 2026-09-11 17:56:09.946402+00 | cron   | backup ok    | 172.20.0.1
(2 rows)

events=# \q
```

| В psql | Что делает |
|---|---|
| `\dt` | список таблиц |
| `\d events` | колонки таблицы и их типы |
| `\q` | выйти |

Swagger UI там же, где был: **http://localhost:8080/apidocs/**

---

## 5. Volume: где живут данные

Файловая система контейнера живёт, пока живёт контейнер. `docker compose down` удаляет контейнеры, и всё, что было записано внутрь, исчезает вместе с ними. Для nginx и backend это нормально: внутри них нет ничего, чего нет в образе. Внутри Postgres лежит база

Volume это папка на диске хоста, которой управляет docker. Она создаётся отдельно от контейнера и живёт отдельно: контейнер можно удалить и создать заново, папка останется и примонтируется в новый контейнер по тому же пути. За это отвечают две строки compose: `pgdata:/var/lib/postgresql/data` у сервиса и `pgdata:` в секции `volumes` внизу

```
$ docker volume ls
DRIVER    VOLUME NAME
local     lesson-6-postgres_pgdata

$ docker volume inspect lesson-6-postgres_pgdata --format '{{.Mountpoint}}'
/var/lib/docker/volumes/lesson-6-postgres_pgdata/_data
```

Имя собралось из имени проекта и имени volume. `Mountpoint` это где папка лежит на самом деле, но ходить туда руками незачем: с данными Postgres работает только сам Postgres

Bind mount из урока 5 и named volume это два способа дать контейнеру папку с хоста:

| | Bind mount | Named volume |
|---|---|---|
| Запись в compose | `./nginx/site.conf:/etc/nginx/conf.d/default.conf` | `pgdata:/var/lib/postgresql/data` |
| Где лежит на хосте | там, где ты сказал | в `/var/lib/docker/volumes/`, путь выбирает docker |
| Для чего | конфиги и код, которые правишь руками | данные, которые пишет сам контейнер |

Проверка сохранности. В базе два события. Убираем контейнеры целиком и поднимаем заново:

```
$ docker compose down
 ...
 Container lesson-6-postgres-postgres-1 Removed
 Network lesson-6-postgres_default Removed

$ docker volume ls
DRIVER    VOLUME NAME
local     lesson-6-postgres_pgdata

$ docker compose up -d
$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":2}
```

Контейнеры и сеть удалены, volume остался, события на месте. Удалить данные можно только явно, флагом `-v`:

```
$ docker compose down -v
 ...
 Volume lesson-6-postgres_pgdata Removed

$ docker compose up -d
$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":0}
```

`down -v` это единственная команда урока, после которой данные не вернуть. Перед ней всегда дамп, пункт 8

---

## 6. Готовность базы: healthcheck и depends_on

`docker compose ps` показывает `Up`, как только процесс в контейнере запустился. Для Postgres это ещё ничего не значит: при первом запуске он несколько секунд создаёт базу, и порт 5432 в это время закрыт. Приложение при старте идёт в базу создавать таблицу, и если база не готова, падает. Обычный `depends_on` из урока 5 здесь не спасает: он задаёт только порядок запуска и не ждёт, пока сервис заработает

Healthcheck решает это. Docker сам выполняет команду внутри контейнера по расписанию и по её коду выхода ведёт статус:

| Параметр | Что значит |
|---|---|
| `test` | команда проверки. `pg_isready` спрашивает у сервера, принимает ли он соединения, и отвечает кодом выхода. `-h localhost` заставляет спрашивать по TCP, как ходит приложение: через unix-сокет сервер отвечает раньше, чем открывает порт |
| `interval: 5s` | как часто проверять |
| `timeout: 3s` | сколько ждать ответа команды |
| `retries: 5` | после скольких неудач подряд контейнер считается `unhealthy` |

Статус виден в `docker compose ps`, у контейнера с healthcheck он проходит две стадии. Первые секунды после `up`:

```
$ docker compose ps -a
SERVICE    STATUS
backend    Created
nginx      Created
postgres   Up 1 second (health: starting)

$ docker compose ps -a
SERVICE    STATUS
backend    Up 1 second
nginx      Up 1 second
postgres   Up 7 seconds (healthy)
```

`backend` и `nginx` в первом выводе только созданы и не запущены: `depends_on` с `condition: service_healthy` заставляет compose ждать `healthy`, прежде чем запускать `backend`. Отсюда строки `Waiting` и `Healthy` в выводе `up` из пункта 4

---

## 7. Пароль в .env

Пароль от базы это первый настоящий секрет в курсе. Правило то же, что для `APP_HOST` в уроке 3: живёт в `.env`, который не попадает в git, в репозитории лежит только [.env.example](.env.example) с заглушкой:

```
POSTGRES_USER=events
POSTGRES_PASSWORD=change-me
POSTGRES_DB=events
```

`.env` защищает пароль от git и от чужих глаз в репозитории, и только. На сервере его видит любой, у кого есть доступ к docker:

```
$ docker compose exec backend env | grep POSTGRES
POSTGRES_USER=events
POSTGRES_PASSWORD=change-me
POSTGRES_DB=events
POSTGRES_HOST=postgres
```

**Грабли.** `POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB` образ читает один раз, при первом запуске с пустым volume. Дальше пароль живёт в базе, и переменная на него не влияет. Меняем пароль в `.env` и пересоздаём:

```
$ docker compose up -d
 Container lesson-6-postgres-postgres-1 Recreated
 Container lesson-6-postgres-backend-1 Recreated

$ docker compose ps
SERVICE    STATUS
backend    Restarting (3) Less than a second ago
nginx      Up 12 seconds
postgres   Up 10 seconds (healthy)

$ docker compose logs backend | grep FATAL | tail -1
backend-1  | connection failed: connection to server at "172.20.0.3", port 5432 failed: FATAL:  password authentication failed for user "events"
```

База здорова, приложение падает по кругу: в `.env` новый пароль, в базе старый. Поменять пароль в самой базе, и приложение поднимется на следующем перезапуске:

```
$ docker compose exec postgres psql -U events events -c "ALTER USER events PASSWORD 'new-password'"
ALTER ROLE

$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":4}
```

Внутри контейнера `psql` ходит через unix-сокет без пароля, поэтому в базу пускает, даже когда приложение не может войти

---

## 8. Дамп и восстановление

Volume защищает от `docker compose down`. От умершего диска, случайного `down -v` и кривой миграции он не защищает. Для этого дамп: файл с SQL, из которого базу можно собрать заново

```bash
docker compose exec -T postgres pg_dump -U events --clean --if-exists events > backup.sql
```

| Часть | Что значит |
|---|---|
| `exec -T` | не подключать терминал к команде. Без `-T` в файл попадут `\r\n` вместо `\n`, и `psql` при восстановлении подавится |
| `pg_dump -U events events` | выгрузить базу `events` от имени пользователя `events` |
| `--clean --if-exists` | добавить в начало дампа `DROP TABLE IF EXISTS`, чтобы восстанавливать поверх существующей базы. Без этого восстановление упрётся в «таблица уже существует»: приложение создаёт её при старте |
| `> backup.sql` | файл появляется на хосте, рядом с compose |

Останавливать приложение на время дампа не нужно, `pg_dump` снимает согласованный снимок и не мешает записи

Дамп это обычный текст, открой его через `less backup.sql`. Между служебными `SET` и комментариями там ровно то, что нужно, чтобы собрать базу заново: удалить старую таблицу, создать новую, залить строки:

```sql
DROP TABLE IF EXISTS public.events;

CREATE TABLE public.events (
    id integer NOT NULL,
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    source text NOT NULL,
    message text NOT NULL,
    client_ip text
);

COPY public.events (id, "time", source, message, client_ip) FROM stdin;
1	2026-09-11 17:57:37.020663+00	deploy	release v1.1	172.20.0.1
2	2026-09-11 17:57:37.040071+00	deploy	release v1.2	172.20.0.1
3	2026-09-11 17:57:37.059465+00	deploy	release v1.3	172.20.0.1
4	2026-09-11 17:57:37.077963+00	cron	backup ok	172.20.0.1
\.

SELECT pg_catalog.setval('public.events_id_seq', 4, true);
```

Восстановление это прогон этого файла через `psql`:

```bash
docker compose exec -T postgres psql -U events events < backup.sql
```

Полный прогон: в базе четыре события, сняли дамп, снесли данные, восстановили:

```
$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":4}

$ docker compose exec -T postgres pg_dump -U events --clean --if-exists events > backup.sql
$ docker compose down -v
$ docker compose up -d
$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":0}

$ docker compose exec -T postgres psql -U events events < backup.sql
DROP TABLE
CREATE TABLE
...
COPY 4
 setval
--------
      4
(1 row)

$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":4}

$ curl -s -X POST http://localhost:8080/events \
    -H 'Content-Type: application/json' \
    -d '{"source":"deploy","message":"after restore"}'
{"client_ip":"172.20.0.1","id":5,"message":"after restore","source":"deploy","time":"2026-09-11T17:57:55+00:00"}
```

`COPY 4` это четыре восстановленные строки, `setval 4` это счётчик `id`, который встал на место: следующее событие получило номер 5, как и должно

Дамп на том же диске, что и база, бэкапом не считается: диск умирает вместе с обоими. Бэкап должен уехать с сервера, и это практика

---

## 9. Автозапуск после ребута

На виртуалке сервис должен подниматься сам после перезагрузки. За это отвечают две вещи, и обе уже есть

Первая, `restart: unless-stopped` у каждого сервиса: docker поднимает такой контейнер после падения и после старта самого docker. Вторая, docker это сервис systemd, и он включён в автозапуск:

```
$ systemctl is-enabled docker
enabled

$ systemctl status docker
● docker.service - Docker Application Container Engine
     Loaded: loaded (/usr/lib/systemd/system/docker.service; enabled; preset: disabled)
     Active: active (running) since Fri 2026-09-11 20:52:34 MSK; 7min ago
```

systemd это первый процесс в Linux, он запускает всё остальное. Каждый сервис описан юнитом, файлом с тем, что запускать, после чего и что делать при падении. Юнит docker можно посмотреть:

```
$ systemctl cat docker
[Unit]
Description=Docker Application Container Engine
After=network-online.target nss-lookup.target docker.socket firewalld.service containerd.service time-set.target
...
[Service]
ExecStart=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock
Restart=always
```

Тот же `restart`, что в compose, только уровнем ниже: systemd перезапускает docker, docker перезапускает контейнеры

| Команда | Что делает |
|---|---|
| `systemctl status docker` | жив ли сервис и последние строки лога |
| `systemctl is-enabled docker` | включён ли автозапуск |
| `sudo systemctl enable docker` | включить, если `disabled` |
| `sudo systemctl restart docker` | перезапустить |
| `journalctl -u docker -n 20` | лог сервиса, тот же `journalctl` из урока 4 с фильтром по юниту |

Проверка простая: `sudo reboot`, зайти обратно по ssh и посмотреть, что поднялось без тебя:

```
$ uptime
 21:05:50 up 0 min,  1 user,  load average: 0.00, 0.00, 0.00

$ docker compose ps
SERVICE    STATUS
backend    Up 10 seconds
nginx      Up 10 seconds
postgres   Up 10 seconds (healthy)

$ curl -s http://localhost:8080/health
{"limit":100,"status":"ok","stored":4}
```

Никто не набирал `docker compose up`, контейнеры поднялись сами, данные на месте благодаря volume из пункта 5

---

## 10. Практика: бэкап в S3 раз в сутки

**Легенда.** База поднята, события копятся, бэкапов нет. Диск виртуалки не вечен, `down -v` по ошибке тоже случается. Нужно, чтобы раз в сутки дамп базы уезжал в S3 без участия человека

S3 это объектное хранилище: есть бакет, в нём файлы по именам, доступ по паре ключей. Endpoint, имя бакета, access key и secret key возьми у меня

### Что сделать

**1. Взять свой проект** из практики урока 5 и подключить к нему Postgres по образцу этого урока: сервис с volume и healthcheck, `condition: service_healthy` у приложения, пароль в `.env`. Хранение в приложении переписать на базу, роутеры при этом трогать не должно быть нужно

**2. Добавить в compose четвёртый сервис `backup`** со своим Dockerfile. Внутри контейнера три вещи: `pg_dump`, клиент S3 и запуск по расписанию. Инструменты любые: aws cli, s3cmd, mc, rclone, boto3 в питоне, cron внутри контейнера или цикл со `sleep`. Единственное требование к `pg_dump`: он должен быть не старше сервера, клиент 16 против сервера 17 откажется работать. Проще всего собрать контейнер бэкапа на том же `postgres:17-alpine`

**3. Дамп ходит к базе по сети**, по имени сервиса `postgres`, как приложение. Никаких `docker compose exec` изнутри контейнера. Все креды, и от базы, и от S3, приезжают через `.env`, в образ и в git не попадает ничего

**4. Имя файла с датой**, чтобы копии не затирали друг друга

**5. Первый дамп сразу при старте контейнера.** Иначе проверять придётся завтра. Дальше по расписанию

**6. Проверить восстановление.** Скачать файл из бакета, снести базу через `down -v`, поднять заново, восстановить из скачанного файла. События на месте, значит бэкап настоящий. Бэкап, из которого ни разу не восстанавливались, не считается

**7. Лог контейнера бэкапа в stdout**: когда запустился, что выгрузил, сколько байт, куда положил. В `docker compose logs backup` должно быть видно, что происходит

**8. Выкатить на виртуалку** и дождаться первого бэкапа по расписанию, не по старту

Результат: имя файла в бакете, `docker compose logs backup` с записью о выгрузке и команды с выводом, которыми ты восстановил базу из скачанного дампа

---

## Что дальше

Здесь начинается собственный проект. Выбери тему в [project-list.md](../project-list.md): дальше он едет через все оставшиеся уроки, от пайплайна до кластера

Урок 7: CI/CD на GitHub Actions, сборка образа, пуш в registry, секреты, деплой и откат на предыдущую версию
