import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str = "devops-center",
    log_dir: str = "./logs",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Настройка логгера с ротацией файлов
    
    Args:
        name: Имя логгера
        log_dir: Директория для логов
        log_level: Уровень логирования
        max_bytes: Максимальный размер файла лога
        backup_count: Количество backup файлов
    """
    
    # Создание директории для логов
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Создание логгера
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Удаление существующих handlers чтобы избежать дублирования
    logger.handlers.clear()
    
    # Формат логов
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # File handler с ротацией
    log_file = log_path / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    # Error file handler - отдельный файл для ошибок
    error_log_file = log_path / f"{name}_error_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    logger.addHandler(error_handler)
    
    return logger


def get_task_logger(task_id: str, log_dir: str = "./logs/tasks") -> logging.Logger:
    """
    Создать отдельный логгер для конкретной задачи
    
    Args:
        task_id: ID задачи
        log_dir: Директория для логов задач
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(f"task_{task_id}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Task-specific file handler
    task_log_file = log_path / f"{task_id}.log"
    file_handler = logging.FileHandler(task_log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    return logger
