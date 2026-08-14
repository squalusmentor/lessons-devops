# =============================================================================
# То же самое, что в уроке 2 (Hugo -> nginx), плюс:
#   - хост приходит аргументом снаружи (ARG APP_HOST) — влияет на baseURL сайта
#     и на CN самоподписанного сертификата;
#   - в runtime-этапе появляется TLS-сертификат для 443.
# Контекст сборки — КОРЕНЬ репозитория, собирать из этой папки:
#   docker build -f Dockerfile -t lesson3-web --build-arg APP_HOST=127.0.0.1 ..
# С docker-compose это делает сам compose (см. docker-compose.yml).
# =============================================================================


# ---------- Этап 1: сборка сайта (как в уроке 2) ----------
FROM ghcr.io/gohugoio/hugo:v0.164.0 AS builder
WORKDIR /src
COPY lesson-1-base-web/ ./

ARG APP_HOST=localhost
RUN hugo --minify --baseURL "http://${APP_HOST}/"


# ---------- Этап 2: nginx + самоподписанный сертификат ----------
FROM nginx:1.27-alpine
ARG APP_HOST=localhost

# openssl нужен только здесь, на этапе сборки — сгенерировать сертификат.
# В итоговом слое он останется (это ~3 МБ), отдельно вычищать его смысла нет.
RUN apk add --no-cache openssl

RUN rm /etc/nginx/conf.d/default.conf
COPY lesson-3-server-deploy/nginx/site.conf /etc/nginx/conf.d/site.conf

COPY lesson-3-server-deploy/certs/generate.sh /tmp/generate.sh
RUN sh /tmp/generate.sh "${APP_HOST}" /etc/nginx/certs && rm /tmp/generate.sh

COPY --from=builder /src/public /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
