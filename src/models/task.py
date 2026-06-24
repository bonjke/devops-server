from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ActionType(str, Enum):
    """Типы действий"""
    DEPLOY = "deploy"
    SSH_COMMAND = "ssh_command"
    LOCAL_COMMAND = "local_command"

    # Jira actions
    JIRA_GET_ISSUE = "jira_get_issue"
    JIRA_CREATE_ISSUE = "jira_create_issue"
    JIRA_UPDATE_ISSUE = "jira_update_issue"
    JIRA_TRANSITION_ISSUE = "jira_transition_issue"
    JIRA_ADD_COMMENT = "jira_add_comment"
    JIRA_SEARCH = "jira_search"

    # Confluence actions
    CONFLUENCE_GET_PAGE = "confluence_get_page"
    CONFLUENCE_CREATE_PAGE = "confluence_create_page"
    CONFLUENCE_UPDATE_PAGE = "confluence_update_page"
    CONFLUENCE_DELETE_PAGE = "confluence_delete_page"
    CONFLUENCE_SEARCH = "confluence_search"
    CONFLUENCE_ADD_ATTACHMENT = "confluence_add_attachment"

    # Digital Ocean actions (disabled)
    DO_DROPLET_LIST = "do_droplet_list"
    DO_DROPLET_CREATE = "do_droplet_create"
    DO_DROPLET_ACTION = "do_droplet_action"
    DO_GET_SSH_KEYS = "do_get_ssh_keys"

    # VDSina actions
    VDSINA_LIST_SERVERS = "vdsina_list_servers"
    VDSINA_GET_SERVER = "vdsina_get_server"
    VDSINA_CREATE_SERVER = "vdsina_create_server"
    VDSINA_DELETE_SERVER = "vdsina_delete_server"
    VDSINA_REBOOT_SERVER = "vdsina_reboot_server"
    VDSINA_REINSTALL_SERVER = "vdsina_reinstall_server"
    VDSINA_SET_PASSWORD = "vdsina_set_password"
    VDSINA_GET_VNC = "vdsina_get_vnc"
    VDSINA_GET_STAT = "vdsina_get_stat"
    VDSINA_LIST_SSH_KEYS = "vdsina_list_ssh_keys"
    VDSINA_CREATE_SSH_KEY = "vdsina_create_ssh_key"
    VDSINA_DELETE_SSH_KEY = "vdsina_delete_ssh_key"
    VDSINA_LIST_TEMPLATES = "vdsina_list_templates"
    VDSINA_LIST_DATACENTERS = "vdsina_list_datacenters"
    VDSINA_LIST_PLANS = "vdsina_list_plans"
    VDSINA_GET_BALANCE = "vdsina_get_balance"
    VDSINA_CREATE_BACKUP = "vdsina_create_backup"
    VDSINA_RESTORE_BACKUP = "vdsina_restore_backup"

    # Server management
    SERVER_INSTALL_SOFTWARE = "server_install_software"
    SERVER_RUN_SCRIPT = "server_run_script"

    # Other
    CHAIN = "chain"


class TaskStatus(str, Enum):
    """Статусы задачи"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskMetadata(BaseModel):
    """Метаданные задачи"""
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Task(BaseModel):
    """Модель задачи"""
    task_id: str
    action: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    target: Optional[str] = None
    chain: Optional[List['Task']] = None
    metadata: TaskMetadata = Field(default_factory=TaskMetadata)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    class Config:
        use_enum_values = True


class TaskResult(BaseModel):
    """Результат выполнения задачи"""
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    execution_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


Task.model_rebuild()
