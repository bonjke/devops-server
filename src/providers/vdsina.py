"""
VDSina Provider
Manages servers via VDSina Public API
API docs: https://vdsina.ru/files/docs/public_api.pdf
Base URL: https://userapi.vdsina.com  (international account)
Auth: token in HTTP header Authorization
"""

import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

VDSINA_API_URL = "https://userapi.vdsina.com"


class VDSinaProvider:
    """Provider for working with VDSina"""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_token,
            "Content-Type": "application/json"
        })
        logger.info("VDSinaProvider initialized")

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{VDSINA_API_URL}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        data = response.json()
        if data.get("status") != "ok":
            raise RuntimeError(f"VDSina API error: {data.get('status_msg', 'Unknown error')} — {data.get('description', '')}")
        return data.get("data", {})

    def get_account(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/account")

    def get_balance(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/account.balance")

    def list_datacenters(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/datacenter")

    def list_server_groups(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/server-group")

    def list_server_plans(self, group_id: int) -> List[Dict[str, Any]]:
        return self._request("GET", f"/v1/server-plan/{group_id}")

    def list_templates(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/template")

    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/ssh-key")

    def get_ssh_key(self, key_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/v1/ssh-key/{key_id}")

    def create_ssh_key(self, name: str, public_key: str) -> Dict[str, Any]:
        return self._request("POST", "/v1/ssh-key", json={"name": name, "data": public_key})

    def update_ssh_key(self, key_id: int, name: str = None, public_key: str = None) -> Dict[str, Any]:
        body = {}
        if name:
            body["name"] = name
        if public_key:
            body["data"] = public_key
        return self._request("PUT", f"/v1/ssh-key/{key_id}", json=body)

    def delete_ssh_key(self, key_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"/v1/ssh-key/{key_id}")

    def list_servers(self) -> List[Dict[str, Any]]:
        result = self._request("GET", "/v1/server")
        return result if isinstance(result, list) else []

    def get_server(self, server_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/v1/server/{server_id}")

    def create_server(self, datacenter: int, server_plan: int, template: Optional[int] = None,
                      ssh_key: Optional[int] = None, name: Optional[str] = None, host: Optional[str] = None,
                      cpu: Optional[int] = None, ram: Optional[int] = None, disk: Optional[int] = None,
                      autoprolong: int = 1) -> Dict[str, Any]:
        body: Dict[str, Any] = {"datacenter": datacenter, "server-plan": server_plan, "autoprolong": autoprolong}
        if template is not None: body["template"] = template
        if ssh_key is not None: body["ssh-key"] = ssh_key
        if name: body["name"] = name
        if host: body["host"] = host
        if cpu is not None: body["cpu"] = cpu
        if ram is not None: body["ram"] = ram
        if disk is not None: body["disk"] = disk
        logger.info(f"Creating VDSina server: {body}")
        return self._request("POST", "/v1/server", json=body)

    def update_server(self, server_id: int, name: str = None, autoprolong: int = None) -> Dict[str, Any]:
        body = {}
        if name is not None: body["name"] = name
        if autoprolong is not None: body["autoprolong"] = autoprolong
        return self._request("PUT", f"/v1/server/{server_id}", json=body)

    def delete_server(self, server_id: int) -> Dict[str, Any]:
        logger.warning(f"Deleting VDSina server {server_id}")
        return self._request("DELETE", f"/v1/server/{server_id}")

    def reboot_server(self, server_id: int, reboot_type: str = "soft") -> Dict[str, Any]:
        return self._request("PUT", f"/v1/server.reboot/{server_id}", json={"type": reboot_type})

    def reinstall_server(self, server_id: int, template: Optional[int] = None,
                         ssh_key: Optional[int] = None, host: Optional[str] = None) -> Dict[str, Any]:
        body = {}
        if template is not None: body["template"] = template
        if ssh_key is not None: body["ssh-key"] = ssh_key
        if host: body["host"] = host
        return self._request("PUT", f"/v1/server.reinstall/{server_id}", json=body)

    def set_server_password(self, server_id: int, password: str) -> Dict[str, Any]:
        return self._request("PUT", f"/v1/server.password/{server_id}", json={"password": password})

    def get_server_vnc(self, server_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/v1/server.vnc/{server_id}")

    def get_server_stat(self, server_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/v1/server.stat/{server_id}")

    def list_backups(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/backup")

    def create_backup(self, server_id: int) -> Dict[str, Any]:
        return self._request("POST", f"/v1/server.backup/{server_id}")

    def restore_backup(self, server_id: int, backup_id: int) -> Dict[str, Any]:
        return self._request("PUT", f"/v1/server.backup/{server_id}", json={"backup": backup_id})
