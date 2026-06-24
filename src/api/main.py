from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import List, Optional
import uuid

from ..models import Task, TaskResult, TaskStatus, Server, Service
from ..storage import JsonStore
from ..core import TaskProcessor, setup_logger
from ..watcher import FileWatcher

# Настройка логирования
logger = setup_logger(
    log_dir=os.getenv("LOGS_DIR", "./logs"),
    log_level=os.getenv("LOG_LEVEL", "INFO")
)

# 🔒 API KEY AUTH
API_KEY = os.getenv("API_KEY", "devops-secret-key-change-me")
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key

# Зависимость — применяется ко всем защищённым роутам
AuthDep = Depends(verify_api_key)

# 🔒 DIGITAL OCEAN DISABLED
DO_ENABLED = False

# Глобальные объекты
storage: Optional[JsonStore] = None
task_processor: Optional[TaskProcessor] = None
file_watcher: Optional[FileWatcher] = None


def process_task_callback(task: Task):
    if task_processor:
        logger.info(f"Processing task from file watcher: {task.task_id}")
        task_processor.process_task(task)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global storage, task_processor, file_watcher

    logger.info("Starting DevOps Center API")

    data_dir = os.getenv("DATA_DIR", "./data")
    encryption_key = os.getenv("ENCRYPTION_KEY") or None
    storage = JsonStore(data_dir=data_dir, encryption_key=encryption_key)
    logger.info("Storage initialized")

    results_dir = os.getenv("RESULTS_DIR", "./results")
    task_processor = TaskProcessor(storage=storage, results_dir=results_dir)
    logger.info("Task processor initialized")

    tasks_dir = os.getenv("TASKS_DIR", "./tasks")
    watch_interval = int(os.getenv("WATCH_INTERVAL", "2"))
    file_watcher = FileWatcher(
        watch_dir=tasks_dir,
        task_callback=process_task_callback,
        watch_interval=watch_interval
    )
    file_watcher.start()
    logger.info(f"File watcher started on {tasks_dir}")

    yield

    logger.info("Shutting down DevOps Center API")
    if file_watcher:
        file_watcher.stop()
    if task_processor:
        task_processor.executor.close_connections()


app = FastAPI(
    title="DevOps Center API",
    description="Infrastructure Management Service",
    version="1.0.0",
    lifespan=lifespan
)


# ============= HEALTH CHECK (публичный) =============

@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "devops-center", "version": "1.0.0"}


# ============= TASKS =============

@app.post("/api/tasks", response_model=Task, tags=["Tasks"], dependencies=[AuthDep])
async def create_task(task: Task, background_tasks: BackgroundTasks):
    if not task.task_id:
        task.task_id = str(uuid.uuid4())
    logger.info(f"Creating task: {task.task_id} - {task.action}")
    background_tasks.add_task(task_processor.process_task, task)
    return task


@app.get("/api/tasks", response_model=List[str], tags=["Tasks"], dependencies=[AuthDep])
async def list_tasks():
    results_dir = Path(os.getenv("RESULTS_DIR", "./results"))
    if not results_dir.exists():
        return []
    return sorted([f.stem for f in results_dir.glob("*.json")], reverse=True)


@app.get("/api/tasks/{task_id}", response_model=TaskResult, tags=["Tasks"], dependencies=[AuthDep])
async def get_task_status(task_id: str):
    result = task_processor.get_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return result


# ============= SERVERS =============

@app.get("/api/servers", response_model=List[Server], tags=["Servers"], dependencies=[AuthDep])
async def list_servers():
    return storage.get_servers()


@app.get("/api/servers/{server_id}", response_model=Server, tags=["Servers"], dependencies=[AuthDep])
async def get_server(server_id: str):
    server = storage.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server {server_id} not found")
    return server


@app.post("/api/servers", response_model=Server, tags=["Servers"], dependencies=[AuthDep])
async def create_server(server: Server):
    if not storage.add_server(server):
        raise HTTPException(status_code=400, detail=f"Server {server.id} already exists")
    return server


@app.put("/api/servers/{server_id}", response_model=Server, tags=["Servers"], dependencies=[AuthDep])
async def update_server(server_id: str, server: Server):
    if server.id != server_id:
        raise HTTPException(status_code=400, detail="Server ID mismatch")
    if not storage.update_server(server):
        raise HTTPException(status_code=404, detail=f"Server {server_id} not found")
    return server


@app.delete("/api/servers/{server_id}", tags=["Servers"], dependencies=[AuthDep])
async def delete_server(server_id: str):
    if not storage.delete_server(server_id):
        raise HTTPException(status_code=404, detail=f"Server {server_id} not found")
    return {"status": "deleted", "server_id": server_id}


# ============= SERVICES =============

@app.get("/api/services", response_model=List[Service], tags=["Services"], dependencies=[AuthDep])
async def list_services():
    return storage.get_services()


@app.get("/api/services/{service_id}", response_model=Service, tags=["Services"], dependencies=[AuthDep])
async def get_service(service_id: str):
    service = storage.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service {service_id} not found")
    return service


@app.post("/api/services", response_model=Service, tags=["Services"], dependencies=[AuthDep])
async def create_service(service: Service):
    if not storage.add_service(service):
        raise HTTPException(status_code=400, detail=f"Service {service.id} already exists")
    return service


@app.put("/api/services/{service_id}", response_model=Service, tags=["Services"], dependencies=[AuthDep])
async def update_service(service_id: str, service: Service):
    if service.id != service_id:
        raise HTTPException(status_code=400, detail="Service ID mismatch")
    if not storage.update_service(service):
        raise HTTPException(status_code=404, detail=f"Service {service_id} not found")
    return service


@app.delete("/api/services/{service_id}", tags=["Services"], dependencies=[AuthDep])
async def delete_service(service_id: str):
    if not storage.delete_service(service_id):
        raise HTTPException(status_code=404, detail=f"Service {service_id} not found")
    return {"status": "deleted", "service_id": service_id}


# ============= DIGITAL OCEAN — DISABLED =============

def _do_disabled():
    raise HTTPException(status_code=503, detail="Digital Ocean отключён")

@app.get("/api/do/droplets", tags=["Digital Ocean (disabled)"], dependencies=[AuthDep])
async def do_list_droplets(): _do_disabled()

@app.get("/api/do/droplets/{droplet_id}", tags=["Digital Ocean (disabled)"], dependencies=[AuthDep])
async def do_get_droplet(droplet_id: int): _do_disabled()

@app.get("/api/do/regions", tags=["Digital Ocean (disabled)"], dependencies=[AuthDep])
async def do_list_regions(): _do_disabled()

@app.get("/api/do/sizes", tags=["Digital Ocean (disabled)"], dependencies=[AuthDep])
async def do_list_sizes(): _do_disabled()

@app.get("/api/do/images", tags=["Digital Ocean (disabled)"], dependencies=[AuthDep])
async def do_list_images(): _do_disabled()

@app.get("/api/do/ssh-keys", tags=["Digital Ocean (disabled)"], dependencies=[AuthDep])
async def do_list_ssh_keys(): _do_disabled()


# ============= WEB UI =============

ui_dir = Path(__file__).parent.parent.parent / "ui"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return '<html><head><meta http-equiv="refresh" content="0; url=/ui/index.html"></head></html>'
