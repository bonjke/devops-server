import subprocess
import paramiko
import logging
from typing import Tuple, Optional, Dict, Any
from io import StringIO

from ..models import Server
from ..storage import JsonStore

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Исполнитель команд - SSH и локальные"""

    def __init__(self, storage: JsonStore):
        self.storage = storage
        self.ssh_clients: Dict[str, paramiko.SSHClient] = {}

    def execute_local(self, command: str, cwd: Optional[str] = None,
                      env: Optional[Dict[str, str]] = None, timeout: int = 300) -> Tuple[int, str, str]:
        logger.info(f"Executing local command: {command}")
        try:
            result = subprocess.run(command, shell=True, cwd=cwd, env=env,
                                    capture_output=True, text=True, timeout=timeout)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timeout after {timeout}s"
        except Exception as e:
            return -1, "", f"Command execution error: {str(e)}"

    def _load_private_key(self, key_str: str) -> paramiko.PKey:
        """
        Автоматически определяет тип SSH ключа и загружает его.
        Поддерживает RSA, Ed25519, ECDSA, DSS и новый формат OpenSSH.
        """
        key_io = StringIO(key_str)
        
        # Пробуем все типы по порядку
        for key_class in [
            paramiko.Ed25519Key,
            paramiko.RSAKey,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ]:
            try:
                key_io.seek(0)
                return key_class.from_private_key(key_io)
            except Exception:
                continue
        
        raise ValueError("Unable to load SSH private key: unsupported key type or invalid format")

    def _get_ssh_client(self, server: Server) -> paramiko.SSHClient:
        """Получить или создать SSH клиента для сервера"""
        if server.id in self.ssh_clients:
            client = self.ssh_clients[server.id]
            try:
                transport = client.get_transport()
                if transport and transport.is_active():
                    return client
            except Exception:
                pass

        logger.info(f"Creating SSH connection to {server.name} ({server.ip})")

        credentials = self.storage.get_credentials()
        private_key_str = credentials.ssh_keys.get(server.ssh_key_name)

        if not private_key_str:
            raise ValueError(f"SSH key '{server.ssh_key_name}' not found in credentials")

        private_key = self._load_private_key(private_key_str)

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=server.ip,
                port=server.ssh_port,
                username=server.ssh_user,
                pkey=private_key,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
            )
            self.ssh_clients[server.id] = client
            logger.info(f"SSH connection established to {server.name}")
            return client
        except Exception as e:
            logger.error(f"SSH connection failed to {server.name}: {e}")
            raise

    def execute_ssh(self, server_id: str, command: str, timeout: int = 300) -> Tuple[int, str, str]:
        server = self.storage.get_server(server_id)
        if not server:
            return -1, "", f"Server {server_id} not found"

        logger.info(f"Executing SSH command on {server.name}: {command}")

        try:
            client = self._get_ssh_client(server)
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode('utf-8', errors='replace')
            stderr_str = stderr.read().decode('utf-8', errors='replace')
            logger.info(f"SSH command completed with code {exit_status}")
            return exit_status, stdout_str, stderr_str

        except paramiko.SSHException as e:
            if server_id in self.ssh_clients:
                del self.ssh_clients[server_id]
            return -1, "", f"SSH error: {str(e)}"
        except Exception as e:
            return -1, "", f"Command execution error: {str(e)}"

    def close_connections(self):
        for client in self.ssh_clients.values():
            try:
                client.close()
            except Exception:
                pass
        self.ssh_clients.clear()

    def __del__(self):
        self.close_connections()
