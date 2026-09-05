from collections import deque

from source.config import settings

# Хранилище событий: deque сам выбрасывает самые старые, когда упирается в maxlen.
# Живёт в памяти процесса, перезапустил контейнер и событий нет.
# В уроке 6 на это место встанет Postgres, и файл станет db.py
events = deque(maxlen=settings.EVENT_LIMIT)
