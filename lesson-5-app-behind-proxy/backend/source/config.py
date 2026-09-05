import os


class Settings:
    """Настройки приложения, все значения приезжают из переменных окружения"""

    EVENT_LIMIT: int = int(os.environ.get("EVENT_LIMIT", "100"))
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
