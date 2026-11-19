FROM python:3.13-slim

# Без этого python копит вывод в буфере и логи появляются в docker logs пачками
# или не появляются вовсе, пока процесс жив
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости отдельным слоем: пока requirements.txt не менялся,
# pip install при пересборке берётся из кэша
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# --access-logfile - это дефис, то есть stdout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "main:app"]
