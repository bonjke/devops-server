import json
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from ..models import Task, TaskResult, TaskStatus, ActionType
from ..storage import JsonStore
from .executor import CommandExecutor
from .logger import get_task_logger
from ..providers.digitalocean import DigitalOceanProvider
from ..providers.vdsina import VDSinaProvider
from ..providers.jira_client import JiraClient
from ..providers.confluence_client import ConfluenceClient

logger = logging.getLogger(__name__)

# 🔒 DIGITAL OCEAN DISABLED — set to True to re-enable
DO_ENABLED = False


class TaskProcessor:
    """Обработчик задач"""

    def __init__(self, storage: JsonStore, results_dir: str = "./results"):
        self.storage = storage
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.executor = CommandExecutor(storage)

        credentials = storage.get_credentials()

        # Digital Ocean — DISABLED
        self.do_provider = None
        if DO_ENABLED and credentials and credentials.digitalocean and credentials.digitalocean.get('api_token'):
            self.do_provider = DigitalOceanProvider(credentials.digitalocean['api_token'])
            logger.info("Digital Ocean provider initialized")
        elif not DO_ENABLED:
            logger.info("Digital Ocean provider DISABLED (DO_ENABLED=False)")

        # VDSina Provider
        self.vdsina_provider = None
        if credentials and hasattr(credentials, 'vdsina') and credentials.vdsina and credentials.vdsina.get('api_token'):
            self.vdsina_provider = VDSinaProvider(credentials.vdsina['api_token'])
            logger.info("VDSina provider initialized")
        else:
            logger.info("VDSina provider not configured (no api_token in credentials.vdsina)")

        # Jira Client
        self.jira_client = None
        if credentials and credentials.jira and all(k in credentials.jira for k in ['url', 'email', 'api_token']):
            self.jira_client = JiraClient(
                url=credentials.jira['url'],
                email=credentials.jira['email'],
                api_token=credentials.jira['api_token']
            )
            logger.info("Jira client initialized")

        # Confluence Client
        self.confluence_client = None
        if credentials and credentials.confluence and all(k in credentials.confluence for k in ['url', 'email', 'api_token', 'space_key']):
            self.confluence_client = ConfluenceClient(
                url=credentials.confluence['url'],
                email=credentials.confluence['email'],
                api_token=credentials.confluence['api_token'],
                space_key=credentials.confluence['space_key']
            )
            logger.info("Confluence client initialized")

        self.action_handlers = {
            ActionType.LOCAL_COMMAND: self._handle_local_command,
            ActionType.SSH_COMMAND: self._handle_ssh_command,
            ActionType.CHAIN: self._handle_chain,
            # Digital Ocean — DISABLED
            ActionType.DO_DROPLET_LIST: self._handle_do_disabled,
            ActionType.DO_DROPLET_CREATE: self._handle_do_disabled,
            ActionType.DO_DROPLET_ACTION: self._handle_do_disabled,
            ActionType.DO_GET_SSH_KEYS: self._handle_do_disabled,
            # VDSina
            ActionType.VDSINA_LIST_SERVERS: self._handle_vdsina_list_servers,
            ActionType.VDSINA_GET_SERVER: self._handle_vdsina_get_server,
            ActionType.VDSINA_CREATE_SERVER: self._handle_vdsina_create_server,
            ActionType.VDSINA_DELETE_SERVER: self._handle_vdsina_delete_server,
            ActionType.VDSINA_REBOOT_SERVER: self._handle_vdsina_reboot_server,
            ActionType.VDSINA_REINSTALL_SERVER: self._handle_vdsina_reinstall_server,
            ActionType.VDSINA_SET_PASSWORD: self._handle_vdsina_set_password,
            ActionType.VDSINA_GET_VNC: self._handle_vdsina_get_vnc,
            ActionType.VDSINA_GET_STAT: self._handle_vdsina_get_stat,
            ActionType.VDSINA_LIST_SSH_KEYS: self._handle_vdsina_list_ssh_keys,
            ActionType.VDSINA_CREATE_SSH_KEY: self._handle_vdsina_create_ssh_key,
            ActionType.VDSINA_DELETE_SSH_KEY: self._handle_vdsina_delete_ssh_key,
            ActionType.VDSINA_LIST_TEMPLATES: self._handle_vdsina_list_templates,
            ActionType.VDSINA_LIST_DATACENTERS: self._handle_vdsina_list_datacenters,
            ActionType.VDSINA_LIST_PLANS: self._handle_vdsina_list_plans,
            ActionType.VDSINA_GET_BALANCE: self._handle_vdsina_get_balance,
            ActionType.VDSINA_CREATE_BACKUP: self._handle_vdsina_create_backup,
            ActionType.VDSINA_RESTORE_BACKUP: self._handle_vdsina_restore_backup,
            # Server Management
            ActionType.SERVER_INSTALL_SOFTWARE: self._handle_server_install_software,
            ActionType.SERVER_RUN_SCRIPT: self._handle_server_run_script,
            # Jira
            ActionType.JIRA_GET_ISSUE: self._handle_jira_get_issue,
            ActionType.JIRA_CREATE_ISSUE: self._handle_jira_create_issue,
            ActionType.JIRA_UPDATE_ISSUE: self._handle_jira_update_issue,
            ActionType.JIRA_TRANSITION_ISSUE: self._handle_jira_transition_issue,
            ActionType.JIRA_ADD_COMMENT: self._handle_jira_add_comment,
            ActionType.JIRA_SEARCH: self._handle_jira_search,
            # Confluence
            ActionType.CONFLUENCE_GET_PAGE: self._handle_confluence_get_page,
            ActionType.CONFLUENCE_CREATE_PAGE: self._handle_confluence_create_page,
            ActionType.CONFLUENCE_UPDATE_PAGE: self._handle_confluence_update_page,
            ActionType.CONFLUENCE_DELETE_PAGE: self._handle_confluence_delete_page,
            ActionType.CONFLUENCE_SEARCH: self._handle_confluence_search,
            ActionType.CONFLUENCE_ADD_ATTACHMENT: self._handle_confluence_add_attachment,
        }

    def process_task(self, task: Task) -> TaskResult:
        task_logger = get_task_logger(task.task_id)
        task_logger.info(f"Starting task {task.task_id}: {task.action}")
        logger.info(f"Processing task {task.task_id}: {task.action}")
        start_time = time.time()
        task.status = TaskStatus.PROCESSING
        try:
            handler = self.action_handlers.get(task.action)
            if not handler:
                raise NotImplementedError(f"Action '{task.action}' not implemented yet")
            result_data = handler(task, task_logger)
            execution_time = time.time() - start_time
            result = TaskResult(
                task_id=task.task_id, status=TaskStatus.COMPLETED,
                result=result_data, execution_time=execution_time, timestamp=datetime.utcnow()
            )
            task_logger.info(f"Task completed in {execution_time:.2f}s")
        except Exception as e:
            execution_time = time.time() - start_time
            result = TaskResult(
                task_id=task.task_id, status=TaskStatus.FAILED,
                error=str(e), execution_time=execution_time, timestamp=datetime.utcnow()
            )
            task_logger.error(f"Task failed: {e}")
            logger.error(f"Task {task.task_id} failed: {e}")
        self._save_result(result)
        return result

    # ========== LOCAL / SSH ==========

    def _handle_local_command(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        command = task.params.get('command')
        if not command:
            raise ValueError("Parameter 'command' is required")
        return_code, stdout, stderr = self.executor.execute_local(
            command=command, cwd=task.params.get('cwd'),
            env=task.params.get('env'), timeout=task.params.get('timeout', 300)
        )
        if return_code != 0:
            raise RuntimeError(f"Command failed with code {return_code}: {stderr}")
        return {"return_code": return_code, "stdout": stdout, "stderr": stderr}

    def _handle_ssh_command(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.target
        if not server_id:
            raise ValueError("'target' (server_id) is required")
        command = task.params.get('command')
        if not command:
            raise ValueError("'command' is required")
        return_code, stdout, stderr = self.executor.execute_ssh(
            server_id=server_id, command=command, timeout=task.params.get('timeout', 300)
        )
        if return_code != 0:
            raise RuntimeError(f"Command failed with code {return_code}: {stderr}")
        return {"server_id": server_id, "return_code": return_code, "stdout": stdout, "stderr": stderr}

    # ========== CHAIN ==========

    def _handle_chain(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not task.chain:
            raise ValueError("'chain' is required")
        task_logger.info(f"Processing chain of {len(task.chain)} tasks")
        results = []
        context = {}
        for i, sub_task in enumerate(task.chain):
            task_logger.info(f"Chain task {i+1}/{len(task.chain)}: {sub_task.action}")
            sub_task.task_id = f"{task.task_id}_chain_{i+1}"
            sub_task = self._resolve_placeholders(sub_task, context, task_logger)
            if i > 0 and sub_task.action in [ActionType.SERVER_INSTALL_SOFTWARE, ActionType.SERVER_RUN_SCRIPT, ActionType.SSH_COMMAND]:
                if 'server_id' in context and context.get('wait_for_ssh', True):
                    self._wait_for_ssh(context['server_id'], task_logger)
                    context['wait_for_ssh'] = False
            sub_result = self.process_task(sub_task)
            results.append(sub_result.model_dump())
            if sub_result.status == TaskStatus.COMPLETED and sub_result.result:
                if 'server_id' in sub_result.result:
                    context['server_id'] = sub_result.result['server_id']
                    context['wait_for_ssh'] = True
            if sub_result.status == TaskStatus.FAILED:
                raise RuntimeError(f"Chain task {i+1} failed: {sub_result.error}")
        return {"chain_length": len(results), "results": results, "context": context}

    def _resolve_placeholders(self, task: Task, context: Dict[str, Any], task_logger: logging.Logger) -> Task:
        if task.target:
            for key, value in context.items():
                task.target = task.target.replace(f"{{{{{key}}}}}", str(value))

        def replace_in_dict(d: dict) -> dict:
            result = {}
            for k, v in d.items():
                if isinstance(v, str):
                    for ctx_key, ctx_value in context.items():
                        v = v.replace(f"{{{{{ctx_key}}}}}", str(ctx_value))
                elif isinstance(v, dict):
                    v = replace_in_dict(v)
                elif isinstance(v, list):
                    v = [replace_in_dict(item) if isinstance(item, dict) else item for item in v]
                result[k] = v
            return result

        task.params = replace_in_dict(task.params)
        return task

    def _wait_for_ssh(self, server_id: str, task_logger: logging.Logger, max_attempts: int = 30, delay: int = 10):
        task_logger.info(f"Waiting for SSH on {server_id}...")
        for attempt in range(1, max_attempts + 1):
            try:
                rc, _, _ = self.executor.execute_ssh(server_id=server_id, command="echo ok", timeout=10)
                if rc == 0:
                    task_logger.info(f"✅ SSH ready on {server_id} (attempt {attempt})")
                    return
            except Exception:
                pass
            if attempt < max_attempts:
                time.sleep(delay)
        raise RuntimeError(f"SSH timeout for server {server_id}")

    # ========== DIGITAL OCEAN — DISABLED ==========

    def _handle_do_disabled(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        raise RuntimeError("Digital Ocean отключён. Установите DO_ENABLED=True чтобы включить.")

    # ========== VDSINA HANDLERS ==========

    def _vdsina(self):
        if not self.vdsina_provider:
            raise RuntimeError(
                "VDSina не настроен. Добавьте в credentials.json: "
                '{"vdsina": {"api_token": "ВАШ_ТОКЕН"}}'
            )
        return self.vdsina_provider

    def _handle_vdsina_list_servers(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        task_logger.info("VDSina: listing servers")
        servers = self._vdsina().list_servers()
        return {"servers": servers, "count": len(servers)}

    def _handle_vdsina_get_server(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        task_logger.info(f"VDSina: get server {server_id}")
        return {"server": self._vdsina().get_server(int(server_id))}

    def _handle_vdsina_create_server(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        p = task.params
        required = ['datacenter', 'server_plan']
        for r in required:
            if not p.get(r):
                raise ValueError(f"'{r}' is required")
        task_logger.info(f"VDSina: creating server plan={p['server_plan']} dc={p['datacenter']}")
        result = self._vdsina().create_server(
            datacenter=int(p['datacenter']),
            server_plan=int(p['server_plan']),
            template=int(p['template']) if p.get('template') else None,
            ssh_key=int(p['ssh_key']) if p.get('ssh_key') else None,
            name=p.get('name'),
            host=p.get('host'),
            cpu=p.get('cpu'),
            ram=p.get('ram'),
            disk=p.get('disk'),
            autoprolong=p.get('autoprolong', 1),
        )
        task_logger.info(f"VDSina: server created: {result}")
        # Если результат содержит ID — добавляем в servers.json
        if isinstance(result, dict) and result.get('id'):
            self._register_vdsina_server(result, p, task_logger)
        return {"server": result}

    def _register_vdsina_server(self, server_data: dict, params: dict, task_logger: logging.Logger):
        """Автоматически добавляем созданный сервер в servers.json"""
        from ..models import Server
        try:
            # IP может появиться не сразу — берём что есть
            ip_list = server_data.get('ip', [])
            ip = ip_list[0]['ip'] if ip_list else 'pending'
            server = Server(
                id=f"vdsina-{server_data['id']}",
                name=params.get('name', f"vdsina-{server_data['id']}"),
                provider="vdsina",
                ip=ip,
                ssh_port=22,
                ssh_user="root",
                ssh_key_name=params.get('ssh_key_name', ''),
                tags=["vdsina", "auto-created"],
                metadata={
                    "provider": "vdsina",
                    "vdsina_id": server_data['id'],
                    "datacenter": params.get('datacenter'),
                    "server_plan": params.get('server_plan'),
                }
            )
            self.storage.add_server(server)
            task_logger.info(f"Server registered in servers.json: {server.id}")
        except Exception as e:
            task_logger.warning(f"Could not register server: {e}")

    def _handle_vdsina_delete_server(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        task_logger.warning(f"VDSina: DELETING server {server_id}")
        self._vdsina().delete_server(int(server_id))
        return {"deleted": True, "server_id": server_id}

    def _handle_vdsina_reboot_server(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        reboot_type = task.params.get('type', 'soft')
        task_logger.info(f"VDSina: reboot server {server_id} ({reboot_type})")
        result = self._vdsina().reboot_server(int(server_id), reboot_type)
        return {"result": result}

    def _handle_vdsina_reinstall_server(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        task_logger.info(f"VDSina: reinstall server {server_id}")
        result = self._vdsina().reinstall_server(
            server_id=int(server_id),
            template=task.params.get('template'),
            ssh_key=task.params.get('ssh_key'),
            host=task.params.get('host'),
        )
        return {"result": result}

    def _handle_vdsina_set_password(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        password = task.params.get('password')
        if not server_id or not password:
            raise ValueError("'server_id' and 'password' are required")
        task_logger.info(f"VDSina: set password for server {server_id}")
        self._vdsina().set_server_password(int(server_id), password)
        return {"done": True}

    def _handle_vdsina_get_vnc(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        task_logger.info(f"VDSina: get VNC for server {server_id}")
        return {"vnc": self._vdsina().get_server_vnc(int(server_id))}

    def _handle_vdsina_get_stat(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        task_logger.info(f"VDSina: get stat for server {server_id}")
        return {"stat": self._vdsina().get_server_stat(int(server_id))}

    def _handle_vdsina_list_ssh_keys(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        task_logger.info("VDSina: list SSH keys")
        keys = self._vdsina().list_ssh_keys()
        return {"ssh_keys": keys, "count": len(keys)}

    def _handle_vdsina_create_ssh_key(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        name = task.params.get('name')
        public_key = task.params.get('public_key')
        if not name or not public_key:
            raise ValueError("'name' and 'public_key' are required")
        task_logger.info(f"VDSina: create SSH key '{name}'")
        result = self._vdsina().create_ssh_key(name, public_key)
        return {"ssh_key": result}

    def _handle_vdsina_delete_ssh_key(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        key_id = task.params.get('key_id')
        if not key_id:
            raise ValueError("'key_id' is required")
        task_logger.info(f"VDSina: delete SSH key {key_id}")
        self._vdsina().delete_ssh_key(int(key_id))
        return {"deleted": True, "key_id": key_id}

    def _handle_vdsina_list_templates(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        task_logger.info("VDSina: list OS templates")
        templates = self._vdsina().list_templates()
        return {"templates": templates, "count": len(templates)}

    def _handle_vdsina_list_datacenters(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        task_logger.info("VDSina: list datacenters")
        dcs = self._vdsina().list_datacenters()
        return {"datacenters": dcs}

    def _handle_vdsina_list_plans(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        group_id = task.params.get('group_id', 1)
        task_logger.info(f"VDSina: list plans for group {group_id}")
        plans = self._vdsina().list_server_plans(int(group_id))
        return {"plans": plans, "count": len(plans)}

    def _handle_vdsina_get_balance(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        task_logger.info("VDSina: get balance")
        return {"balance": self._vdsina().get_balance()}

    def _handle_vdsina_create_backup(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        if not server_id:
            raise ValueError("'server_id' is required")
        task_logger.info(f"VDSina: create backup for server {server_id}")
        result = self._vdsina().create_backup(int(server_id))
        return {"backup": result}

    def _handle_vdsina_restore_backup(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.params.get('server_id') or task.target
        backup_id = task.params.get('backup_id')
        if not server_id or not backup_id:
            raise ValueError("'server_id' and 'backup_id' are required")
        task_logger.info(f"VDSina: restore backup {backup_id} to server {server_id}")
        result = self._vdsina().restore_backup(int(server_id), int(backup_id))
        return {"result": result}

    # ========== SERVER MANAGEMENT ==========

    def _handle_server_install_software(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.target
        if not server_id:
            raise ValueError("'target' (server_id) is required")
        packages = task.params.get('software') or task.params.get('packages')
        if not packages:
            raise ValueError("'software' or 'packages' is required")
        task_logger.info(f"Installing {packages} on {server_id}")
        results = []
        for cmd in ["apt-get update -y", f"apt-get install -y {' '.join(packages)}"]:
            rc, stdout, stderr = self.executor.execute_ssh(server_id=server_id, command=cmd, timeout=600)
            results.append({"command": cmd, "return_code": rc, "stdout": stdout[:500], "stderr": stderr[:500]})
            if rc != 0:
                raise RuntimeError(f"Install failed: {stderr}")
        return {"server_id": server_id, "installed": packages, "steps": results}

    def _handle_server_run_script(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        server_id = task.target
        if not server_id:
            raise ValueError("'target' (server_id) is required")
        script = task.params.get('script')
        script_url = task.params.get('script_url')
        if not script and not script_url:
            raise ValueError("'script' or 'script_url' is required")
        if script_url:
            commands = [f"curl -fsSL {script_url} -o /tmp/script.sh", "chmod +x /tmp/script.sh", "/tmp/script.sh"]
        else:
            import base64
            b64 = base64.b64encode(script.encode()).decode()
            commands = [f"echo '{b64}' | base64 -d > /tmp/script.sh", "chmod +x /tmp/script.sh", "/tmp/script.sh", "rm -f /tmp/script.sh"]
        results = []
        for i, cmd in enumerate(commands, 1):
            rc, stdout, stderr = self.executor.execute_ssh(server_id=server_id, command=cmd, timeout=task.params.get('timeout', 600))
            results.append({"step": i, "return_code": rc, "stdout": stdout, "stderr": stderr})
            if rc != 0 and i < len(commands):
                raise RuntimeError(f"Script failed at step {i}: {stderr}")
        return {"server_id": server_id, "steps": results}

    # ========== JIRA ==========

    def _handle_jira_get_issue(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.jira_client:
            raise RuntimeError("Jira not configured")
        issue_key = task.params.get('issue_key')
        if not issue_key:
            raise ValueError("'issue_key' is required")
        return {"issue": self.jira_client.get_issue(issue_key)}

    def _handle_jira_create_issue(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.jira_client:
            raise RuntimeError("Jira not configured")
        p = task.params
        if not all([p.get('project_key'), p.get('summary'), p.get('description')]):
            raise ValueError("'project_key', 'summary', 'description' are required")
        issue = self.jira_client.create_issue(
            project_key=p['project_key'], summary=p['summary'], description=p['description'],
            issue_type=p.get('issue_type', 'Task'), priority=p.get('priority'),
            labels=p.get('labels', []), assignee=p.get('assignee')
        )
        return {"issue": issue}

    def _handle_jira_update_issue(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.jira_client:
            raise RuntimeError("Jira not configured")
        issue_key = task.params.get('issue_key')
        if not issue_key:
            raise ValueError("'issue_key' is required")
        self.jira_client.update_issue(issue_key, task.params.get('fields', {}))
        return {"issue_key": issue_key, "updated": True}

    def _handle_jira_transition_issue(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.jira_client:
            raise RuntimeError("Jira not configured")
        issue_key = task.params.get('issue_key')
        transition = task.params.get('transition')
        if not issue_key or not transition:
            raise ValueError("'issue_key' and 'transition' are required")
        self.jira_client.transition_issue(issue_key, transition)
        return {"issue_key": issue_key, "transition": transition, "completed": True}

    def _handle_jira_add_comment(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.jira_client:
            raise RuntimeError("Jira not configured")
        issue_key = task.params.get('issue_key')
        comment = task.params.get('comment')
        if not issue_key or not comment:
            raise ValueError("'issue_key' and 'comment' are required")
        return {"comment": self.jira_client.add_comment(issue_key, comment)}

    def _handle_jira_search(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.jira_client:
            raise RuntimeError("Jira not configured")
        jql = task.params.get('jql')
        if not jql:
            raise ValueError("'jql' is required")
        issues = self.jira_client.search_issues(jql, max_results=task.params.get('max_results', 50))
        return {"count": len(issues), "issues": issues}

    # ========== CONFLUENCE ==========

    def _handle_confluence_get_page(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.confluence_client:
            raise RuntimeError("Confluence not configured")
        page = self.confluence_client.get_page(
            page_id=task.params.get('page_id'), title=task.params.get('title'),
            space_key=task.params.get('space_key')
        )
        if not page:
            raise RuntimeError("Page not found")
        return {"page": page}

    def _handle_confluence_create_page(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.confluence_client:
            raise RuntimeError("Confluence not configured")
        p = task.params
        if not p.get('title') or not p.get('body'):
            raise ValueError("'title' and 'body' are required")
        return {"page": self.confluence_client.create_page(
            title=p['title'], body=p['body'], space_key=p.get('space_key'), parent_id=p.get('parent_id')
        )}

    def _handle_confluence_update_page(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.confluence_client:
            raise RuntimeError("Confluence not configured")
        p = task.params
        if not all([p.get('page_id'), p.get('title'), p.get('body')]):
            raise ValueError("'page_id', 'title', 'body' are required")
        return {"page": self.confluence_client.update_page(page_id=p['page_id'], title=p['title'], body=p['body'])}

    def _handle_confluence_delete_page(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.confluence_client:
            raise RuntimeError("Confluence not configured")
        page_id = task.params.get('page_id')
        if not page_id:
            raise ValueError("'page_id' is required")
        self.confluence_client.delete_page(page_id)
        return {"page_id": page_id, "deleted": True}

    def _handle_confluence_search(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.confluence_client:
            raise RuntimeError("Confluence not configured")
        cql = task.params.get('cql')
        if not cql:
            raise ValueError("'cql' is required")
        pages = self.confluence_client.search_pages(cql, limit=task.params.get('limit', 25))
        return {"count": len(pages), "pages": pages}

    def _handle_confluence_add_attachment(self, task: Task, task_logger: logging.Logger) -> Dict[str, Any]:
        if not self.confluence_client:
            raise RuntimeError("Confluence not configured")
        page_id = task.params.get('page_id')
        file_path = task.params.get('file_path')
        if not page_id or not file_path:
            raise ValueError("'page_id' and 'file_path' are required")
        return {"attachment": self.confluence_client.add_attachment(
            page_id=page_id, file_path=file_path, comment=task.params.get('comment')
        )}

    # ========== UTILS ==========

    def _save_result(self, result: TaskResult):
        result_file = self.results_dir / f"{result.task_id}.json"
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save result: {e}")

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        result_file = self.results_dir / f"{task_id}.json"
        if not result_file.exists():
            return None
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                return TaskResult(**json.load(f))
        except Exception as e:
            logger.error(f"Failed to load result {task_id}: {e}")
            return None
