import os


class Settings:
    """Настройки приложения, все значения приезжают из переменных окружения"""

    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "postgres")
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "events")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "events")

    # Строка подключения: адрес, логин, пароль и имя базы одним URL.
    # В таком виде её ждёт драйвер, и в таком же виде она встречается
    # в чужих проектах под именем DATABASE_URL
    DATABASE_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/{POSTGRES_DB}"

    # Сколько событий отдавать в GET /events
    EVENT_LIMIT: int = int(os.environ.get("EVENT_LIMIT", "100"))
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
