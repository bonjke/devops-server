#!/usr/bin/env python3
"""
DevOps Center - Linux Host Agent
Следит за папкой host_tasks/, выполняет local_command локально,
всё остальное проксирует в API контейнера.
"""

import json
import time
import logging
import subprocess
import os
import sys
import signal
import shutil
import requests
from pathlib import Path
from datetime import datetime

# ============= CONFIG =============

TASKS_DIR = Path(os.getenv("HOST_TASKS_DIR", "/opt/projects/devops-center/host_tasks"))
RESULTS_DIR = Path(os.getenv("HOST_RESULTS_DIR", "/opt/projects/devops-center/host_results"))
ARCHIVE_DIR = Path(os.getenv("HOST_ARCHIVE_DIR", "/opt/projects/devops-center/host_tasks_archive"))
LOG_FILE = Path(os.getenv("HOST_LOG_FILE", "/opt/projects/devops-center/logs/host-agent.log"))
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "devops-2match-secret-2026")
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "2"))
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "300"))

# ============= LOGGING =============

def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - host-agent - %(levelname)s - %(message)s',
        handlers=handlers
    )

logger = logging.getLogger("host-agent")

# ============= DIRS =============

def ensure_dirs():
    for d in [TASKS_DIR, RESULTS_DIR, ARCHIVE_DIR / "completed", ARCHIVE_DIR / "failed"]:
        d.mkdir(parents=True, exist_ok=True)

# ============= TASK EXECUTION =============

def execute_local_command(params: dict) -> dict:
    """Выполнить команду локально на Linux хосте"""
    command = params.get("command")
    if not command:
        raise ValueError("'command' is required")

    cwd = params.get("cwd")
    timeout = params.get("timeout", TASK_TIMEOUT)
    env = params.get("env")

    logger.info(f"Executing local command: {command}")

    result = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (code {result.returncode}): {result.stderr[:500]}"
        )

    return {
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


def proxy_to_api(task: dict) -> dict:
    """Отправить задачу в API контейнера и дождаться результата"""
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    timeout = task.get("params", {}).get("timeout", TASK_TIMEOUT)

    # Отправляем задачу
    resp = requests.post(
        f"{API_URL}/api/tasks",
        json=task,
        headers=headers,
        timeout=30
    )
    resp.raise_for_status()

    task_id = task["task_id"]
    logger.info(f"Task {task_id} sent to API, waiting for result...")

    # Ждём результат (polling)
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(2)
        try:
            r = requests.get(
                f"{API_URL}/api/tasks/{task_id}",
                headers=headers,
                timeout=10
            )
            if r.status_code == 200:
                result = r.json()
                status = result.get("status")
                if status in ("completed", "failed"):
                    if status == "failed":
                        raise RuntimeError(f"API task failed: {result.get('error')}")
                    return result.get("result", {})
        except requests.RequestException:
            pass  # Ещё не готово, продолжаем ждать

    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")


def process_task(task_file: Path):
    """Обработать одну задачу"""
    task_id = task_file.stem
    logger.info(f"Processing task: {task_id}")

    start_time = time.time()
    status = "completed"
    result = {}
    error = None

    try:
        with open(task_file, "r", encoding="utf-8") as f:
            task = json.load(f)

        action = task.get("action")

        if action == "local_command":
            # Выполняем локально
            result = execute_local_command(task.get("params", {}))
        else:
            # Всё остальное — в API
            result = proxy_to_api(task)

    except Exception as e:
        status = "failed"
        error = str(e)
        logger.error(f"Task {task_id} failed: {e}")

    execution_time = time.time() - start_time

    # Сохраняем результат
    result_data = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "error": error,
        "execution_time": round(execution_time, 2),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    result_file = RESULTS_DIR / f"{task_id}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    # Архивируем задачу
    archive_subdir = ARCHIVE_DIR / ("completed" if status == "completed" else "failed")
    shutil.move(str(task_file), str(archive_subdir / task_file.name))

    logger.info(f"Task {task_id} {status} in {execution_time:.2f}s")
    return status


# ============= MAIN LOOP =============

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutting down host agent...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    setup_logging()
    ensure_dirs()

    logger.info("=" * 50)
    logger.info("🚀 DevOps Center Linux Host Agent STARTED")
    logger.info(f"   Tasks dir:  {TASKS_DIR}")
    logger.info(f"   Results:    {RESULTS_DIR}")
    logger.info(f"   API URL:    {API_URL}")
    logger.info(f"   Interval:   {WATCH_INTERVAL}s")
    logger.info("=" * 50)

    # Проверяем доступность API
    try:
        r = requests.get(f"{API_URL}/api/health", timeout=5)
        if r.status_code == 200:
            logger.info("✅ API is available")
        else:
            logger.warning(f"⚠️  API returned {r.status_code}")
    except Exception as e:
        logger.warning(f"⚠️  API not available yet: {e}")

    while running:
        try:
            task_files = sorted(TASKS_DIR.glob("*.json"))

            if task_files:
                logger.info(f"🔔 Found {len(task_files)} task(s)")
                for task_file in task_files:
                    if not running:
                        break
                    process_task(task_file)

        except Exception as e:
            logger.error(f"Watcher error: {e}")

        time.sleep(WATCH_INTERVAL)

    logger.info("Host agent stopped.")


if __name__ == "__main__":
    main()
