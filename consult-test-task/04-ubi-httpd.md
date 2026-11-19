# 4–5. Свой образ на UBI 7.7 с httpd

UBI (Universal Base Image) это бесплатный базовый образ Red Hat Enterprise Linux. Внутри RHEL-окружение и пакетный менеджер `yum`. Его выбирают компании, у которых серверы на RHEL, чтобы контейнеры были на той же системе

Структура папки:

```
ubi-httpd/
├── Dockerfile
└── index.html
```

---

## Dockerfile

```dockerfile
FROM registry.access.redhat.com/ubi7/ubi:7.7

RUN yum install -y httpd && yum clean all

COPY index.html /var/www/html/index.html

EXPOSE 80

# в контейнере нет systemd, поэтому httpd запускается напрямую и в foreground:
# контейнер живёт, пока жив главный процесс
CMD ["/usr/sbin/httpd", "-D", "FOREGROUND"]
```

| Инструкция | Что делает |
|---|---|
| `FROM` | базовый образ UBI 7.7 из реестра Red Hat |
| `RUN yum install` | ставит apache; `yum clean all` убирает кэш пакетов, чтобы образ был меньше |
| `COPY` | заменяет стандартную страницу своей |
| `EXPOSE 80` | документирует порт, сам порт не открывает |
| `CMD` | что запускается при старте контейнера |

Типичная ошибка: `CMD systemctl start httpd`. В контейнере нет systemd, команда падает. А просто `httpd` без `-D FOREGROUND` уходит в фон, главный процесс завершается, и контейнер сразу останавливается

## index.html

```html
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>UBI httpd</title></head>
  <body><h1>Hello from UBI 7.7 + httpd</h1></body>
</html>
```

---

## Сборка

```bash
cd ubi-httpd
docker build -t ubi-httpd:1.0 .
```

Собирает образ из Dockerfile в текущей папке и даёт ему имя `ubi-httpd` с тегом `1.0`

```bash
docker images ubi-httpd
```

Образ появился в списке

UBI 7 снят с поддержки в 2024 году. Если `yum install` падает на загрузке репозитория, причина в этом. Тогда стоит договориться с проверяющим и взять `ubi8/ubi`: Dockerfile тот же, только пакеты ставятся через `dnf`

---

## Запуск и проверка

```bash
docker run -d --name web -p 8080:80 ubi-httpd:1.0
```

| Флаг | Что делает |
|---|---|
| `-d` | запуск в фоне |
| `--name web` | имя контейнера вместо случайного |
| `-p 8080:80` | порт 8080 хоста ведёт на порт 80 контейнера |

```bash
docker ps
```

Контейнер `web` в статусе `Up`. Если его нет в списке, он упал: смотри `docker ps -a` и `docker logs web`

```bash
curl http://localhost:8080
```

Должен вернуться наш `index.html` с `Hello from UBI 7.7 + httpd`

```bash
docker logs web
```

Лог httpd. Предупреждение `AH00558: Could not reliably determine the server's fully qualified domain name` безобидное: у сервера не задан `ServerName`, на работу это не влияет

| Команда | Что делает |
|---|---|
| `docker exec -it web bash` | зайти внутрь контейнера |
| `docker stop web` | остановить |
| `docker rm web` | удалить остановленный контейнер |
