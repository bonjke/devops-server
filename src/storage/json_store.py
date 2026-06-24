import json
import os
from typing import List, Optional, Dict, Any
from pathlib import Path
from cryptography.fernet import Fernet
import logging

from ..models import Server, Service, Credentials

logger = logging.getLogger(__name__)


class JsonStore:
    """Управление JSON-хранилищем для серверов, сервисов и credentials"""
    
    def __init__(self, data_dir: str, encryption_key: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.servers_file = self.data_dir / "servers.json"
        self.services_file = self.data_dir / "services.json"
        self.credentials_file = self.data_dir / "credentials.json"
        
        # Инициализация шифрования для credentials
        self.cipher = None
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        
        self._init_files()
    
    def _init_files(self):
        """Инициализация файлов если они не существуют"""
        if not self.servers_file.exists():
            self._write_json(self.servers_file, {"servers": []})
        
        if not self.services_file.exists():
            self._write_json(self.services_file, {"services": []})
        
        if not self.credentials_file.exists():
            empty_creds = Credentials().model_dump()
            self._write_credentials(empty_creds)
    
    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """Чтение JSON файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return {}
    
    def _write_json(self, file_path: Path, data: Dict[str, Any]):
        """Запись в JSON файл"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing {file_path}: {e}")
            raise
    
    def _encrypt_data(self, data: str) -> str:
        """Шифрование данных"""
        if self.cipher:
            return self.cipher.encrypt(data.encode()).decode()
        return data
    
    def _decrypt_data(self, data: str) -> str:
        """Расшифровка данных"""
        if self.cipher:
            try:
                return self.cipher.decrypt(data.encode()).decode()
            except Exception as e:
                logger.error(f"Decryption error: {e}")
                return data
        return data
    
    # === SERVERS ===
    
    def get_servers(self) -> List[Server]:
        """Получить все серверы"""
        data = self._read_json(self.servers_file)
        return [Server(**server) for server in data.get("servers", [])]
    
    def get_server(self, server_id: str) -> Optional[Server]:
        """Получить сервер по ID"""
        servers = self.get_servers()
        for server in servers:
            if server.id == server_id:
                return server
        return None
    
    def add_server(self, server: Server) -> bool:
        """Добавить новый сервер"""
        try:
            data = self._read_json(self.servers_file)
            servers = data.get("servers", [])
            
            # Проверка на дубликат
            if any(s['id'] == server.id for s in servers):
                logger.warning(f"Server {server.id} already exists")
                return False
            
            servers.append(server.model_dump())
            data["servers"] = servers
            self._write_json(self.servers_file, data)
            return True
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            return False
    
    def update_server(self, server: Server) -> bool:
        """Обновить сервер"""
        try:
            data = self._read_json(self.servers_file)
            servers = data.get("servers", [])
            
            for i, s in enumerate(servers):
                if s['id'] == server.id:
                    servers[i] = server.model_dump()
                    data["servers"] = servers
                    self._write_json(self.servers_file, data)
                    return True
            
            logger.warning(f"Server {server.id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating server: {e}")
            return False
    
    def delete_server(self, server_id: str) -> bool:
        """Удалить сервер"""
        try:
            data = self._read_json(self.servers_file)
            servers = data.get("servers", [])
            
            initial_len = len(servers)
            servers = [s for s in servers if s['id'] != server_id]
            
            if len(servers) == initial_len:
                logger.warning(f"Server {server_id} not found")
                return False
            
            data["servers"] = servers
            self._write_json(self.servers_file, data)
            return True
        except Exception as e:
            logger.error(f"Error deleting server: {e}")
            return False
    
    # === SERVICES ===
    
    def get_services(self) -> List[Service]:
        """Получить все сервисы"""
        data = self._read_json(self.services_file)
        return [Service(**service) for service in data.get("services", [])]
    
    def get_service(self, service_id: str) -> Optional[Service]:
        """Получить сервис по ID"""
        services = self.get_services()
        for service in services:
            if service.id == service_id:
                return service
        return None
    
    def add_service(self, service: Service) -> bool:
        """Добавить новый сервис"""
        try:
            data = self._read_json(self.services_file)
            services = data.get("services", [])
            
            if any(s['id'] == service.id for s in services):
                logger.warning(f"Service {service.id} already exists")
                return False
            
            services.append(service.model_dump())
            data["services"] = services
            self._write_json(self.services_file, data)
            return True
        except Exception as e:
            logger.error(f"Error adding service: {e}")
            return False
    
    def update_service(self, service: Service) -> bool:
        """Обновить сервис"""
        try:
            data = self._read_json(self.services_file)
            services = data.get("services", [])
            
            for i, s in enumerate(services):
                if s['id'] == service.id:
                    services[i] = service.model_dump()
                    data["services"] = services
                    self._write_json(self.services_file, data)
                    return True
            
            logger.warning(f"Service {service.id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating service: {e}")
            return False
    
    def delete_service(self, service_id: str) -> bool:
        """Удалить сервис"""
        try:
            data = self._read_json(self.services_file)
            services = data.get("services", [])
            
            initial_len = len(services)
            services = [s for s in services if s['id'] != service_id]
            
            if len(services) == initial_len:
                logger.warning(f"Service {service_id} not found")
                return False
            
            data["services"] = services
            self._write_json(self.services_file, data)
            return True
        except Exception as e:
            logger.error(f"Error deleting service: {e}")
            return False
    
    # === CREDENTIALS ===
    
    def get_credentials(self) -> Credentials:
        """Получить credentials (расшифрованные)"""
        try:
            with open(self.credentials_file, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()
            
            if self.cipher and encrypted_data:
                decrypted_data = self._decrypt_data(encrypted_data)
                return Credentials(**json.loads(decrypted_data))
            else:
                return Credentials(**json.loads(encrypted_data))
        except Exception as e:
            logger.error(f"Error reading credentials: {e}")
            return Credentials()
    
    def _write_credentials(self, creds_dict: Dict[str, Any]):
        """Записать credentials (зашифрованные)"""
        try:
            json_data = json.dumps(creds_dict, indent=2)
            
            if self.cipher:
                encrypted_data = self._encrypt_data(json_data)
                with open(self.credentials_file, 'w', encoding='utf-8') as f:
                    f.write(encrypted_data)
            else:
                with open(self.credentials_file, 'w', encoding='utf-8') as f:
                    f.write(json_data)
        except Exception as e:
            logger.error(f"Error writing credentials: {e}")
            raise
    
    def update_credentials(self, credentials: Credentials) -> bool:
        """Обновить credentials"""
        try:
            self._write_credentials(credentials.model_dump())
            return True
        except Exception as e:
            logger.error(f"Error updating credentials: {e}")
            return False
