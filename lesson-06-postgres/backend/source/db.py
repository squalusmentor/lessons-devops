import psycopg
from psycopg.rows import dict_row

from source.config import settings

# Хранилище событий: таблица в Postgres. В уроке 5 здесь был deque в памяти процесса.
# Роутеры и хендлеры про замену не знают, они по-прежнему зовут функции из этого файла


def connect():
    """Одно соединение на запрос: открыли, сделали дело, закрыли.
    dict_row отдаёт строки словарями, чтобы их можно было сразу отдать в JSON"""
    return psycopg.connect(settings.DATABASE_URL, row_factory=dict_row)


def init():
    """Создать таблицу, если её ещё нет. Вызывается один раз при старте приложения"""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id        serial PRIMARY KEY,
                time      timestamptz NOT NULL DEFAULT now(),
                source    text NOT NULL,
                message   text NOT NULL,
                client_ip text
            )
        """)


# Значения в запрос подставляет драйвер через %s. Собирать SQL f-строкой нельзя:
# кто угодно пришлёт в message кусок SQL, и он выполнится
def add_event(source, message, client_ip):
    with connect() as conn:
        return conn.execute(
            "INSERT INTO events (source, message, client_ip) VALUES (%s, %s, %s) RETURNING *",
            (source, message, client_ip),
        ).fetchone()


def list_events(source=None):
    with connect() as conn:
        if source is None:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT %s",
                (settings.EVENT_LIMIT,),
            )
        else:
            rows = conn.execute(
                "SELECT * FROM events WHERE source = %s ORDER BY id DESC LIMIT %s",
                (source, settings.EVENT_LIMIT),
            )
        return rows.fetchall()


def count():
    with connect() as conn:
        return conn.execute("SELECT count(*) AS total FROM events").fetchone()["total"]
