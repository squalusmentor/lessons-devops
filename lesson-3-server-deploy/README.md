# Урок 3. Деплой на сервер и HTTPS

В уроке 2 контейнер собирался и запускался у тебя на компьютере. Здесь тот же
контейнер едет на настоящую виртуалку: заводим `docker-compose` с параметром
хоста, забираем приватный код с сервера по токену, ставим на виртуалке Docker,
открываем порты и добавляем HTTPS через самоподписанный сертификат.

Сайт внутри — тот же, из урока 1, собирается тем же Dockerfile-подходом, что
в уроке 2. Здесь только то, что добавляется при переезде на реальный сервер.

---

## 1. docker-compose — зачем и что внутри

В уроке 2 контейнер поднимался командой `docker run` с кучей флагов, которые
надо было держать в голове или в истории терминала. `docker-compose.yml`
описывает те же флаги файлом: команда получается одна и та же что локально,
что на сервере — меняется только `.env`, а не список аргументов.

Наш файл — [docker-compose.yml](docker-compose.yml):

```yaml
services:
  web:
    build:
      context: ..
      dockerfile: lesson-3-server-deploy/Dockerfile
      args:
        APP_HOST: ${APP_HOST}
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped
```

| Ключ | Что значит |
|---|---|
| `build.context` | то же самое, что `..` в `docker build` из урока 2 — контекст сборки, корень репозитория |
| `build.dockerfile` | какой Dockerfile использовать — путь **от `context`**, а не от папки, где лежит сам `docker-compose.yml`. Поэтому здесь `lesson-3-server-deploy/Dockerfile`, а не просто `Dockerfile` |
| `build.args.APP_HOST` | прокидывает `ARG APP_HOST` внутрь сборки (см. Dockerfile) |
| `ports` | то же самое, что `-p` в `docker run`, можно перечислить несколько портов |
| `restart: unless-stopped` | контейнер поднимется заново после падения или перезагрузки сервера. `docker run` без ключа так не умеет |

`${APP_HOST}` compose подставляет сам, если рядом с `docker-compose.yml`
лежит файл `.env` — про него следующий пункт.

Команды:

| Команда | Что делает |
|---|---|
| `docker compose up -d --build` | собрать образ и поднять контейнер в фоне |
| `docker compose down` | остановить и удалить контейнер и сеть |
| `docker compose logs -f` | логи, как `docker logs -f` |
| `docker compose ps` | что сейчас поднято |

---

## 2. Хост в `.env`

В репозитории лежит [`.env.example`](.env.example) — шаблон с локальным
значением. Перед запуском копируешь его в `.env`:

```bash
cp .env.example .env
```

`.env` в git не попадает (см. [`.gitignore`](.gitignore)) — у каждого свой:

```
# локально
APP_HOST=127.0.0.1

# на сервере — публичный IP виртуалки
APP_HOST=203.0.113.10
```

`APP_HOST` идёт build-аргументом в Dockerfile и используется в двух местах:
`baseURL` сайта при сборке Hugo (как в уроке 2) и `CN` сертификата — до этого
дойдём в пункте 6.

---

## 3. Приватный репозиторий: токен для git на сервере

Свой проект (упакованный сайт из урока 2) ты перенёс в приватный репозиторий
организации на GitHub. У виртуалки нет твоего браузера и твоего логина —
`git clone`/`git pull` там просят авторизацию отдельно. Для этого — токен.

**GitHub → аватар → Settings → Developer settings → Personal access tokens
→ Fine-grained tokens → Generate new token**:

| Поле | Значение |
|---|---|
| Resource owner | организация, где лежит репозиторий |
| Repository access | Only select repositories → выбрать свой репозиторий |
| Permissions → Repository permissions | Contents: **Read-only** — этого достаточно для `clone`/`pull` |
| Expiration | разумный срок, не «No expiration» |

Токен показывается один раз при создании — скопировать сразу.

На виртуалке:

```bash
git clone https://<TOKEN>@github.com/<org>/<repo>.git
```

Дальше `git pull` внутри этой папки работает без повторного ввода — токен
уже в адресе удалённого репозитория (`git remote -v` его покажет). Это
означает, что токен в открытом виде лежит в `.git/config` на диске
виртуалки — держи его read-only и с сроком действия, не расшаривай доступ
к серверу посторонним.

---

## 4. Docker и docker compose на виртуалке

Проверить, что уже стоит:

```bash
docker --version
docker compose version
```

Если команда не найдена — ставим официальным скриптом (сам определяет
дистрибутив, тянет Docker Engine и плагин compose одним заходом):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

После `usermod` группа применится только в новой сессии — переподключись
по ssh (или `newgrp docker`), иначе `docker ps` будет падать с
`permission denied`. Проверка та же — `docker --version && docker compose version`.

---

## 5. Какие порты открыты

Что слушает сама виртуалка:

```bash
ss -tulpn
```

`State LISTEN`, `Local Address:Port` и последняя колонка — какой процесс.
До `docker compose up` там не будет ни 80, ни 443, после — появятся оба.

Это только локальный список процессов. Отдельно от него — файрвол:

```bash
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

Если `ufw` не установлен или неактивен — пропускай. Плюс к этому у самой
виртуалки (Timeweb / Yandex Cloud / VK Cloud / …) в панели управления обычно
есть свой Firewall/Security Group — 80 и 443 нужно открыть и там тоже,
иначе `docker ps` покажет контейнер живым, а снаружи в него никто не попадёт.

---

## 6. Самоподписанный сертификат и HTTPS

Домена у виртуалки нет, только IP — а Let's Encrypt на голый IP сертификат
не выпускает (нужен домен для проверки владения). Для урока хватит
самоподписанного сертификата: браузер такому не доверяет по умолчанию,
но соединение всё равно шифруется, и повадки HTTPS видно вживую.

Скрипт — [certs/generate.sh](certs/generate.sh):

```bash
#!/bin/sh
set -e

HOST="${1:-localhost}"
OUT_DIR="${2:-$(dirname "$0")}"

mkdir -p "$OUT_DIR"

openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$OUT_DIR/site.key" \
    -out "$OUT_DIR/site.crt" \
    -days 365 \
    -subj "/CN=$HOST"
```

| Флаг | Смысл |
|---|---|
| `-x509` | сразу выпустить сертификат, а не запрос на подпись (CSR) |
| `-nodes` | не шифровать приватный ключ паролем — иначе nginx не сможет стартовать без ввода пароля |
| `-newkey rsa:2048` | сгенерировать новую пару ключей RSA-2048 |
| `-keyout` / `-out` | куда положить приватный ключ / сертификат |
| `-days 365` | срок действия |
| `-subj "/CN=$HOST"` | на какой хост выписан (Common Name), без диалоговых вопросов |

**В Dockerfile** скрипт копируется и запускается на этапе сборки runtime-образа:

```dockerfile
RUN apk add --no-cache openssl

COPY lesson-3-server-deploy/certs/generate.sh /tmp/generate.sh
RUN sh /tmp/generate.sh "${APP_HOST}" /etc/nginx/certs && rm /tmp/generate.sh
```

Сертификат и ключ оказываются внутри образа в `/etc/nginx/certs/` ещё до
первого запуска контейнера — не нужно ничего монтировать или генерировать
при старте.

**В nginx** — второй `server { }` в [nginx/site.conf](nginx/site.conf),
рядом с уже знакомым по уроку 2 блоком на 80:

```nginx
server {
    listen 443 ssl;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    ssl_certificate     /etc/nginx/certs/site.crt;
    ssl_certificate_key /etc/nginx/certs/site.key;

    location / {
        try_files $uri $uri/ =404;
    }

    error_page 404 /404.html;
}
```

`server_name _` — «любой Host-заголовок»: домена нет, различать нечего.
`ssl_certificate` / `ssl_certificate_key` — пути ровно те, куда всё положил
`generate.sh`.

Первый заход на `https://` браузер встретит предупреждением
«Соединение не защищено» — это ожидаемо для самоподписанного сертификата,
жмёшь «Дополнительно → Перейти на сайт (небезопасно)». В `curl` то же самое
лечится флагом `-k`.

---

## 7. Собираем и проверяем

Из этой папки:

```bash
cp .env.example .env
docker compose up -d --build
```

Проверено на локальной сборке (`APP_HOST=127.0.0.1`):

```
$ curl -sI http://127.0.0.1/
HTTP/1.1 200 OK
Server: nginx/1.27.5
Content-Type: text/html
Content-Length: 3987

$ curl -I https://127.0.0.1/
curl: (60) SSL certificate problem: self-signed certificate
More details here: https://curl.se/docs/sslcerts.html

$ curl -sIk https://127.0.0.1/
HTTP/1.1 200 OK
Server: nginx/1.27.5

$ echo | openssl s_client -connect 127.0.0.1:443 2>/dev/null | openssl x509 -noout -subject
subject=CN=127.0.0.1
```

Ровно то поведение, что описано в пункте 6: без `-k` — обрыв на проверке
сертификата, с `-k` — 200, `CN` в сертификате равен `APP_HOST` из `.env`.

---

## 8. Практика: разверни свой сервис

Проект из практики урока 2 (упакованный в Docker чужой/свой сайт) уже лежит
в твоём приватном репозитории организации. Задача — поднять его на реальной
виртуалке по HTTP, а потом добавить HTTPS. Шаги:

1. По примеру этого урока напиши `docker-compose.yml` для своего проекта —
   с `APP_HOST` через `.env`, портом 80 наружу.
2. Выпусти fine-grained токен на чтение своего репозитория (пункт 3) и
   склонируй репозиторий на виртуалку по HTTPS с этим токеном.
3. Проверь на виртуалке `docker --version` и `docker compose version`.
   Если нет — поставь (пункт 4).
4. Посмотри `ss -tulpn` до запуска. Проверь и при необходимости открой
   80-й порт — и в `ufw` (если есть), и в панели облака (пункт 5).
5. Создай `.env` на виртуалке с `APP_HOST=<IP виртуалки>` — на своей машине
   при этом `.env` останется с `127.0.0.1`.
6. `docker compose up -d --build` на виртуалке. Зайди в браузере на
   `http://<IP виртуалки>` — сайт должен открыться.
7. Вернись в IDE. Скопируй в свой проект `certs/generate.sh` из этого урока,
   заведи `nginx/certs`-раздел под сертификат.
8. Пропиши в своём Dockerfile генерацию сертификата на сборке — по образцу
   пункта 6: `apk add openssl`, копирование скрипта, запуск, путь вывода.
9. Добавь в свой `site.conf` второй `server { }` на 443 с `ssl_certificate`
   и `ssl_certificate_key`, указывающими на эти пути. Пробрось порт 443
   в `docker-compose.yml`.
10. Закоммить и запушь изменения. На виртуалке — `git pull`, затем
    `docker compose up -d --build`. Проверь `https://<IP виртуалки>` в
    браузере (с предупреждением о сертификате — это нормально) и
    `curl -Ik https://<IP виртуалки>/`.

Результат — рабочий адрес `https://<IP виртуалки>` и команды/вывод,
которыми ты это проверил.

---

## Что дальше

Урок 4: базовая отладка приложений на сервере, память, CPU и диск, чистка
Docker-образов, load average, OOM и троттлинг, ping/traceroute и логи
