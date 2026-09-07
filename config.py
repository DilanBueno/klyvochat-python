from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    SIGNALING_URL: str = "ws://localhost:8080"
    API_URL: str = "http://localhost:8080"
    DB_PATH: str = "data/klyvochat.db"
    THEME: str = "dark"
    LOG_LEVEL: str = "INFO"
    STUN_SERVERS: List[str] = [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
