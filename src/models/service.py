from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class Service(BaseModel):
    """Модель сервиса"""
    id: str
    name: str
    stack: str  # Например: "node:18-alpine", "python:3.11-slim"
    port: Optional[int] = None
    health_endpoint: Optional[str] = None
    deploy_path: str
    start_command: str
    stop_command: Optional[str] = None
    env_file: Optional[str] = None
    environment: Dict[str, str] = Field(default_factory=dict)
    docker_compose_file: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "id": "svc-001",
                "name": "api-gateway",
                "stack": "node:18-alpine",
                "port": 3000,
                "health_endpoint": "/health",
                "deploy_path": "/opt/apps/api-gateway",
                "start_command": "npm start",
                "env_file": ".env.prod",
                "environment": {
                    "NODE_ENV": "production"
                }
            }
        }
