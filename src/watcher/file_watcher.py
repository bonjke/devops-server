import json
import time
import logging
from pathlib import Path
from typing import Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from ..models import Task

logger = logging.getLogger(__name__)


class TaskFileHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы для задач"""
    
    def __init__(self, callback: Callable[[Task], None]):
        """
        Args:
            callback: Функция обработки задачи
        """
        self.callback = callback
        self.processed_files = set()
    
    def on_created(self, event):
        """Обработка создания файла"""
        if event.is_directory:
            return
        
        if not event.src_path.endswith('.json'):
            return
        
        # Избегаем двойной обработки
        if event.src_path in self.processed_files:
            return
        
        logger.info(f"New task file detected: {event.src_path}")
        
        # Небольшая задержка для завершения записи файла
        time.sleep(0.1)
        
        try:
            self._process_task_file(event.src_path)
        except Exception as e:
            logger.error(f"Error processing task file {event.src_path}: {e}")
    
    def _process_task_file(self, file_path: str):
        """
        Обработать файл задачи
        
        Args:
            file_path: Путь к файлу задачи
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Валидация и создание Task объекта
            task = Task(**data)
            
            logger.info(f"Task loaded: {task.task_id} - {task.action}")
            
            # Вызов callback для обработки
            self.callback(task)
            
            # Отметка файла как обработанного
            self.processed_files.add(file_path)
            
            # Опционально: удаление или перемещение обработанного файла
            # Path(file_path).unlink()  # Удаление
            # или перемещение в архив
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing task from {file_path}: {e}")


class FileWatcher:
    """Мониторинг директории с задачами"""
    
    def __init__(
        self,
        watch_dir: str,
        task_callback: Callable[[Task], None],
        watch_interval: int = 2
    ):
        """
        Args:
            watch_dir: Директория для мониторинга
            task_callback: Функция обработки задачи
            watch_interval: Интервал проверки в секундах
        """
        self.watch_dir = Path(watch_dir)
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        
        self.task_callback = task_callback
        self.watch_interval = watch_interval
        
        self.event_handler = TaskFileHandler(task_callback)
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(self.watch_dir),
            recursive=False
        )
        
        self.is_running = False
    
    def start(self):
        """Запустить мониторинг"""
        if self.is_running:
            logger.warning("FileWatcher already running")
            return
        
        logger.info(f"Starting FileWatcher on {self.watch_dir}")
        self.observer.start()
        self.is_running = True
        
        # Обработка существующих файлов при старте
        self._process_existing_files()
    
    def stop(self):
        """Остановить мониторинг"""
        if not self.is_running:
            return
        
        logger.info("Stopping FileWatcher")
        self.observer.stop()
        self.observer.join()
        self.is_running = False
    
    def _process_existing_files(self):
        """Обработать существующие файлы в директории"""
        logger.info("Processing existing task files")
        
        for file_path in self.watch_dir.glob("*.json"):
            if str(file_path) not in self.event_handler.processed_files:
                try:
                    logger.info(f"Processing existing file: {file_path}")
                    self.event_handler._process_task_file(str(file_path))
                except Exception as e:
                    logger.error(f"Error processing existing file {file_path}: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
