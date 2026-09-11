from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    SIGNALING_URL: str = "wss://your-hostinger-domain.com"
    API_URL: str = "https://your-hostinger-domain.com"
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
        # Mantém localhost como fallback em desenvolvimento local.
        # Em produção (Hostinger), crie o arquivo .env na raiz com as URLs do servidor.


settings = Settings()
