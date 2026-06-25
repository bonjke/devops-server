"""
DevOps Center MCP Server
Exposes DevOps Center API as MCP tools for Claude Desktop / Claude Code.

Transport: Streamable HTTP
Port: 8001

Подключение в Claude Desktop (claude_desktop_config.json):
{
  "mcpServers": {
    "devops-center": {
      "type": "http",
      "url": "http://87.199.198.120:8001/mcp"
    }
  }
}
"""

import os
import json
import time
import requests
from mcp.server.fastmcp import FastMCP

DEVOPS_API_URL = os.getenv("DEVOPS_API_URL", "http://localhost:8000")
DEVOPS_API_KEY = os.getenv("DEVOPS_API_KEY", "devops-2match-secret-2026")
POLL_TIMEOUT   = int(os.getenv("POLL_TIMEOUT", "300"))
POLL_INTERVAL  = float(os.getenv("POLL_INTERVAL", "2"))
MCP_HOST       = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT       = int(os.getenv("MCP_PORT", "8001"))

mcp = FastMCP("DevOps Center", host=MCP_HOST, port=MCP_PORT)

# ============= HELPERS =============

def _headers():
    return {"X-API-Key": DEVOPS_API_KEY, "Content-Type": "application/json"}

def _post_task(task: dict) -> dict:
    r = requests.post(f"{DEVOPS_API_URL}/api/tasks", json=task, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def _poll_result(task_id: str, timeout: int = POLL_TIMEOUT) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        r = requests.get(f"{DEVOPS_API_URL}/api/tasks/{task_id}", headers=_headers(), timeout=10)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status")
            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"Task failed: {data.get('error')}")
    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

def _run(task: dict, timeout: int = POLL_TIMEOUT) -> str:
    task_id = task["task_id"]
    _post_task(task)
    result = _poll_result(task_id, timeout)
    return json.dumps(result.get("result") or {}, indent=2, ensure_ascii=False)

def _task_id(prefix: str) -> str:
    return f"mcp-{prefix}-{int(time.time())}"

# ============= TOOLS: COMMANDS =============

@mcp.tool()
def run_local_command(command: str, cwd: str = "", timeout: int = 60) -> str:
    """Run a shell command on the VDS (inside DevOps Center container). Use for: docker ps, ls, git, etc."""
    task = {"task_id": _task_id("local"), "action": "local_command", "params": {"command": command, "timeout": timeout}}
    if cwd:
        task["params"]["cwd"] = cwd
    return _run(task, timeout + 10)

@mcp.tool()
def run_ssh_command(server_id: str, command: str, timeout: int = 60) -> str:
    """Run a command on a remote server via SSH. server_id e.g. 'vdsina-875675'"""
    task = {"task_id": _task_id("ssh"), "action": "ssh_command", "target": server_id, "params": {"command": command, "timeout": timeout}}
    return _run(task, timeout + 10)

@mcp.tool()
def run_chain(steps: list, description: str = "") -> str:
    """Run a chain of tasks sequentially. steps = list of task dicts with action/params/target."""
    task = {"task_id": _task_id("chain"), "action": "chain", "params": {}, "chain": steps}
    total = sum(s.get("params", {}).get("timeout", 60) for s in steps) + 60
    return _run(task, total)

# ============= TOOLS: VDSINA =============

@mcp.tool()
def vdsina_get_balance() -> str:
    """Get VDSina account balance"""
    return _run({"task_id": _task_id("vds-balance"), "action": "vdsina_get_balance", "params": {}})

@mcp.tool()
def vdsina_list_servers() -> str:
    """List all VDSina servers"""
    return _run({"task_id": _task_id("vds-servers"), "action": "vdsina_list_servers", "params": {}})

@mcp.tool()
def vdsina_get_server(server_id: int) -> str:
    """Get info about a specific VDSina server by numeric ID"""
    return _run({"task_id": _task_id("vds-get"), "action": "vdsina_get_server", "params": {"server_id": server_id}})

@mcp.tool()
def vdsina_create_server(name: str, datacenter: int, server_plan: int, template: int, ssh_key: int) -> str:
    """Create a new VDSina server. datacenter: 4=Amsterdam1. server_plan: 36=1CPU/1GB. template: 38=CentOS10. ssh_key: 22248"""
    return _run({"task_id": _task_id("vds-create"), "action": "vdsina_create_server",
                 "params": {"name": name, "datacenter": datacenter, "server_plan": server_plan, "template": template, "ssh_key": ssh_key}}, 60)

@mcp.tool()
def vdsina_reboot_server(server_id: int, reboot_type: str = "soft") -> str:
    """Reboot a VDSina server. reboot_type: 'soft' or 'hard'"""
    return _run({"task_id": _task_id("vds-reboot"), "action": "vdsina_reboot_server", "params": {"server_id": server_id, "type": reboot_type}})

@mcp.tool()
def vdsina_list_templates() -> str:
    """List available OS templates on VDSina"""
    return _run({"task_id": _task_id("vds-tpl"), "action": "vdsina_list_templates", "params": {}})

@mcp.tool()
def vdsina_list_plans(group_id: int = 2) -> str:
    """List VDSina server plans. group_id: 2=Standard"""
    return _run({"task_id": _task_id("vds-plans"), "action": "vdsina_list_plans", "params": {"group_id": group_id}})

# ============= TOOLS: JIRA =============

@mcp.tool()
def jira_create_issue(project_key: str, summary: str, description: str, issue_type: str = "Task") -> str:
    """Create a Jira issue. project_key e.g. 'SCRUM'"""
    return _run({"task_id": _task_id("jira-create"), "action": "jira_create_issue",
                 "params": {"project_key": project_key, "summary": summary, "description": description, "issue_type": issue_type}})

@mcp.tool()
def jira_get_issue(issue_key: str) -> str:
    """Get Jira issue by key, e.g. 'SCRUM-5'"""
    return _run({"task_id": _task_id("jira-get"), "action": "jira_get_issue", "params": {"issue_key": issue_key}})

@mcp.tool()
def jira_search(jql: str, max_results: int = 20) -> str:
    """Search Jira with JQL query"""
    return _run({"task_id": _task_id("jira-search"), "action": "jira_search", "params": {"jql": jql, "max_results": max_results}})

@mcp.tool()
def jira_add_comment(issue_key: str, comment: str) -> str:
    """Add a comment to a Jira issue"""
    return _run({"task_id": _task_id("jira-comment"), "action": "jira_add_comment", "params": {"issue_key": issue_key, "comment": comment}})

@mcp.tool()
def jira_transition_issue(issue_key: str, transition: str) -> str:
    """Change Jira issue status. transition: 'In Progress', 'Done', 'To Do', 'In Review'"""
    return _run({"task_id": _task_id("jira-trans"), "action": "jira_transition_issue", "params": {"issue_key": issue_key, "transition": transition}})

# ============= TOOLS: MANAGEMENT =============

@mcp.tool()
def list_servers() -> str:
    """List all servers registered in DevOps Center"""
    r = requests.get(f"{DEVOPS_API_URL}/api/servers", headers=_headers(), timeout=10)
    r.raise_for_status()
    return json.dumps(r.json(), indent=2, ensure_ascii=False)

@mcp.tool()
def list_recent_tasks(limit: int = 20) -> str:
    """List recent task IDs from DevOps Center"""
    r = requests.get(f"{DEVOPS_API_URL}/api/tasks", headers=_headers(), timeout=10)
    r.raise_for_status()
    return json.dumps(r.json()[:limit], indent=2)

@mcp.tool()
def get_task_result(task_id: str) -> str:
    """Get result of a specific task by ID"""
    r = requests.get(f"{DEVOPS_API_URL}/api/tasks/{task_id}", headers=_headers(), timeout=10)
    r.raise_for_status()
    return json.dumps(r.json(), indent=2, ensure_ascii=False)

@mcp.tool()
def deploy_update(repo_path: str = "/opt/projects/devops-center") -> str:
    """Pull latest git changes and restart DevOps Center container on VDS"""
    task = {
        "task_id": _task_id("deploy"),
        "action": "chain",
        "params": {},
        "chain": [
            {"task_id": "deploy-pull", "action": "ssh_command", "target": "vdsina-875675",
             "params": {"command": f"cd {repo_path} && git pull", "timeout": 30}},
            {"task_id": "deploy-restart", "action": "ssh_command", "target": "vdsina-875675",
             "params": {"command": f"cd {repo_path} && docker compose restart", "timeout": 30}},
            {"task_id": "deploy-health", "action": "ssh_command", "target": "vdsina-875675",
             "params": {"command": "sleep 3 && curl -s http://localhost:8000/api/health", "timeout": 15}},
        ]
    }
    return _run(task, 120)

# ============= ENTRY POINT =============

if __name__ == "__main__":
    import sys
    print(f"Starting DevOps Center MCP Server on {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    print(f"DevOps API: {DEVOPS_API_URL}", file=sys.stderr)
    print(f"Connect Claude Desktop to: http://87.199.198.120:{MCP_PORT}/mcp", file=sys.stderr)
    mcp.run(transport="streamable-http")
