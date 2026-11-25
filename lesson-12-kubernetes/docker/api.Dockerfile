FROM golang:1.26.8 AS builder
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY cmd ./cmd
COPY internal ./internal
COPY gen-swagger.sh gen-swagger.sh

RUN chmod +x gen-swagger.sh
RUN sh gen-swagger.sh
RUN CGO_ENABLED=0 go build -o main cmd/server/main.go

FROM alpine:3.20
WORKDIR /app

# Копируем бинарник
COPY --from=builder /app/main .

# Копируем swagger docs
COPY --from=builder /app/docs ./docs

# Копируем конфиги и промпты
COPY --from=builder /app/internal/config ./internal/config

EXPOSE 8080
CMD ["./main"]
