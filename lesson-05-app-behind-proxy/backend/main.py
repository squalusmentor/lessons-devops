from flasgger import Swagger
from flask import Flask

from source.logger import setup_logging
from source.routers.events import router as events_router
from source.routers.system import router as system_router

setup_logging()

app = Flask(__name__)
app.json.ensure_ascii = False

Swagger(app, template={"info": {"title": "Приёмник событий", "version": "1"}})

app.register_blueprint(system_router)
app.register_blueprint(events_router, url_prefix="/events")
