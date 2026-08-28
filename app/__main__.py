import uvicorn

from app.config import SETTINGS

uvicorn.run(
    "app.main:app",
    host=SETTINGS.host,
    port=SETTINGS.port,
)
