from pydantic import BaseModel
from typing import Dict, Any


class Credentials(BaseModel):
    """Модель для хранения учетных данных"""
    digitalocean: Dict[str, str] = {}
    vdsina: Dict[str, str] = {}
    ssh_keys: Dict[str, str] = {}  # key_name: private_key_content
    jira: Dict[str, str] = {}
    confluence: Dict[str, str] = {}
    custom: Dict[str, Any] = {}  # Для дополнительных credentials

    class Config:
        extra = "ignore"  # Игнорировать неизвестные поля (например _comment)
