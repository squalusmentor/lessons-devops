# 7. LLM на сервере: Ollama и Qwen3-4B

Ollama это сервер для запуска LLM одной командой: сам качает модель, держит её в памяти и отдаёт HTTP API. Qwen3-4B в сжатом виде весит ~2.5 ГБ и работает даже без видеокарты

| Что нужно | Минимум |
|---|---|
| ОС | Linux-сервер (Ubuntu) или WSL |
| Память | 8 ГБ |
| Диск | 5 ГБ |
| GPU | не обязательно, с ним ответы в разы быстрее |

В задании названы vLLM и SGLang. Ollama проще поднять и объяснить, поэтому основной путь через неё. Если проверяющий требует именно vLLM, смотри раздел в конце

---

## Шаг 1. Установка

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Ставит бинарь `ollama` и systemd-службу `ollama`. Сервер слушает `127.0.0.1:11434`

```bash
systemctl status ollama
```

Служба в `active (running)`

---

## Шаг 2. Скачать модель

```bash
ollama pull qwen3:4b
```

Качает модель из библиотеки Ollama

```bash
ollama list
```

Скачанные модели и их размер

---

## Шаг 3. Первый запрос из консоли

```bash
ollama run qwen3:4b --think=false --verbose "Объясни, что такое под в Kubernetes, в двух предложениях"
```

| Флаг | Что делает |
|---|---|
| `--think=false` | отключает режим рассуждений; без него Qwen3 сначала долго пишет размышления, потом ответ |
| `--verbose` | после ответа печатает статистику |

Статистика после ответа:

```
total duration:       4.1s
load duration:        1.2s
prompt eval count:    24 token(s)
prompt eval duration: 210ms
prompt eval rate:     114.29 tokens/s
eval count:           58 token(s)
eval duration:        2.6s
eval rate:            22.31 tokens/s
```

| Строка | Что значит |
|---|---|
| `total duration` | всё время запроса |
| `load duration` | загрузка модели в память; большое только на первом запросе |
| `prompt eval count` | сколько токенов во входном промпте |
| `prompt eval rate` | скорость чтения промпта, токенов в секунду |
| `eval count` | сколько токенов сгенерировано в ответе |
| `eval rate` | скорость генерации, главная метрика «насколько быстро отвечает» |

Токен это кусок слова, с которым работает модель. Русский текст режется мельче английского, поэтому токенов в нём больше на то же число слов. Цифры выше примерные, у тебя будут свои

```bash
ollama ps
```

Какие модели сейчас в памяти

| Столбец | Что значит |
|---|---|
| `SIZE` | сколько памяти занимает модель |
| `PROCESSOR` | `100% CPU` или `100% GPU`; если видеокарта есть, а тут CPU, драйвер не подхватился |
| `UNTIL` | через сколько модель выгрузится из памяти без запросов, по умолчанию 5 минут |

---

## Шаг 4. Запрос через API

Так к модели обращаются приложения

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3:4b",
  "prompt": "Назови три команды kubectl",
  "stream": false,
  "think": false
}'
```

`stream: false` отдаёт ответ одним JSON целиком вместо потока по токенам. В ответе поле `response` с текстом и та же статистика в наносекундах: `total_duration`, `load_duration`, `prompt_eval_count`, `eval_count`, `eval_duration`

Скорость генерации из этих полей: `eval_count / eval_duration * 10^9` токенов в секунду

```bash
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:4b", "messages": [{"role": "user", "content": "Привет"}]}'
```

Тот же сервер в формате OpenAI API. Так подключаются готовые библиотеки и чат-интерфейсы. В конце ответа блок `usage`: `prompt_tokens`, `completion_tokens`, `total_tokens`

Ollama по умолчанию слушает только localhost. Если стучишься с другой машины, добавь в службу `Environment="OLLAMA_HOST=0.0.0.0"` так же, как в шаге 5, и открой порт 11434 в файрволе

---

## Шаг 5. Логирование промптов

По умолчанию в логе видно только сам факт запроса: время, код ответа, длительность. Чтобы видеть текст промпта, включаем debug-режим через переменную окружения службы

```bash
sudo systemctl edit ollama
```

Открывает редактор для дополнения к unit-файлу службы. Вписать:

```ini
[Service]
Environment="OLLAMA_DEBUG=1"
```

```bash
sudo systemctl restart ollama
journalctl -u ollama -f
```

Перезапускает службу с новой переменной и показывает её лог в реальном времени. Во втором терминале повтори `curl` из шага 4: в логе появятся строки `level=DEBUG` с текстом промпта. Если промпта не видно, поставь `OLLAMA_DEBUG=2`, это ещё более подробный уровень trace

Обратно: `sudo systemctl revert ollama` и `sudo systemctl restart ollama`

На собесе стоит сказать: в проде промпты в логах это риск. Пользователи пишут в чат персональные данные и пароли, и всё это оседает в логах и системе сбора логов. Debug включают на время разбора проблемы

---

## Если нужен именно vLLM

vLLM это сервер для продакшена: обслуживает много запросов параллельно и быстрее Ollama под нагрузкой. Работает только с видеокартой NVIDIA, для Qwen3-4B нужно от 12 ГБ видеопамяти. Без видеокарты остаётся Ollama

```bash
docker run --gpus all -p 8000:8000 --ipc=host \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -e VLLM_LOGGING_LEVEL=DEBUG \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen3-4B --max-model-len 8192 --enable-log-requests
```

| Параметр | Что делает |
|---|---|
| `--gpus all` | отдаёт контейнеру видеокарты; в WSL работает с установленным драйвером NVIDIA на Windows |
| `--ipc=host` | общая память с хостом, без неё vLLM падает при больших батчах |
| `-v ~/.cache/huggingface` | модель скачивается один раз и переживает перезапуск контейнера |
| `--model` | модель с Hugging Face |
| `--max-model-len` | максимальная длина контекста; меньше длина, меньше нужно видеопамяти |
| `--enable-log-requests` | логировать каждый входящий запрос |
| `VLLM_LOGGING_LEVEL=DEBUG` | в новых версиях текст промпта пишется только на уровне debug |

В старых версиях vLLM флага `--enable-log-requests` нет, запросы там логируются по умолчанию. Если контейнер ругается на флаг, просто убери его

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-4B",
    "messages": [{"role": "user", "content": "Назови три команды kubectl"}],
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

Тот же формат OpenAI API, что у Ollama. `enable_thinking: false` отключает рассуждения Qwen3

Статистика vLLM пишется в лог контейнера раз в 10 секунд:

```
Avg prompt throughput: 12.4 tokens/s, Avg generation throughput: 85.1 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.8%
```

| Поле | Что значит |
|---|---|
| `Avg prompt throughput` | скорость обработки входящих промптов |
| `Avg generation throughput` | скорость генерации суммарно по всем запросам |
| `Running` | сколько запросов обрабатывается прямо сейчас |
| `Waiting` | сколько стоит в очереди; растёт значит сервер не справляется |
| `GPU KV cache usage` | занятость памяти под контекст запросов; под 100% новые запросы начинают ждать |

Те же метрики для Prometheus отдаются на `http://localhost:8000/metrics`

SGLang запускается и проверяется так же: свой образ `lmsysorg/sglang`, тот же OpenAI API и флаг `--log-requests` для логирования промптов
