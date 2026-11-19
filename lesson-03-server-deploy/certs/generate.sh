#!/bin/sh
# Самоподписанный TLS-сертификат — когда домена ещё нет, а https нужен уже сейчас.
# Браузер такому сертификату не доверяет по умолчанию — это ожидаемо, не баг.
set -e

HOST="${1:-localhost}"
OUT_DIR="${2:-$(dirname "$0")}"

mkdir -p "$OUT_DIR"

openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$OUT_DIR/site.key" \
    -out "$OUT_DIR/site.crt" \
    -days 365 \
    -subj "/CN=$HOST"
