from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Server(BaseModel):
    """Модель сервера"""
    id: str
    name: str
    provider: str = "digitalocean"
    droplet_id: Optional[str] = None
    ip: str
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key_name: str  # Имя ключа из credentials
    tags: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)  # service_ids
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "id": "srv-001",
                "name": "prod-api-01",
                "provider": "digitalocean",
                "droplet_id": "123456",
                "ip": "1.2.3.4",
                "ssh_port": 22,
                "ssh_user": "root",
                "ssh_key_name": "id_rsa_prod",
                "tags": ["prod", "api"],
                "services": ["svc-001", "svc-002"]
            }
        }
