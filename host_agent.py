"""
DevOps Center - Host Agent v2.1
Агент для выполнения команд на Windows хосте с архивацией задач
"""
import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import sys
from collections import defaultdict
import shutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/host-agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('host-agent')


class TaskHistory:
    """Управление историей задач"""
    
    def __init__(self, history_file: str = "logs/host-agent-history.json"):
        self.history_file = Path(history_file)
        self.history: List[Dict[str, Any]] = []
        self.stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "total_execution_time": 0.0
        }
        self.load_history()
    
    def load_history(self):
        """Загрузить историю из файла"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
                    self.stats = data.get('stats', self.stats)
                logger.info(f"Loaded {len(self.history)} tasks from history")
            except Exception as e:
                logger.error(f"Error loading history: {e}")
                self.history = []
    
    def save_history(self):
        """Сохранить историю в файл"""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "history": self.history[-1000:],  # Хранить последние 1000 задач
                "stats": self.stats,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def add_task(self, task_data: Dict[str, Any]):
        """Добавить задачу в историю"""
        entry = {
            "task_id": task_data.get('task_id'),
            "status": task_data.get('status'),
            "timestamp": task_data.get('timestamp'),
            "execution_time": task_data.get('execution_time', 0),
            "return_code": task_data.get('result', {}).get('return_code'),
            "command": task_data.get('command', ''),
            "error": task_data.get('error')
        }
        
        self.history.append(entry)
        
        # Обновить статистику
        self.stats['total'] += 1
        if task_data.get('status') == 'completed':
            self.stats['completed'] += 1
        else:
            self.stats['failed'] += 1
        
        self.stats['total_execution_time'] += task_data.get('execution_time', 0)
        
        self.save_history()
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        return self.stats.copy()
    
    def get_recent_tasks(self, count: int = 10) -> List[Dict[str, Any]]:
        """Получить последние задачи"""
        return self.history[-count:]


class HostTaskExecutor:
    """Исполнитель задач на хост-машине Windows"""
    
    def __init__(
        self,
        tasks_dir: str = "host_tasks",
        results_dir: str = "host_results",
        archive_dir: str = "host_tasks_archive",
        watch_interval: int = 2,
        auto_archive: bool = True
    ):
        self.tasks_dir = Path(tasks_dir)
        self.results_dir = Path(results_dir)
        self.archive_dir = Path(archive_dir)
        self.watch_interval = watch_interval
        self.auto_archive = auto_archive
        
        # Создать директории если не существуют
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Создать поддиректории архива
        if self.auto_archive:
            (self.archive_dir / "completed").mkdir(parents=True, exist_ok=True)
            (self.archive_dir / "failed").mkdir(parents=True, exist_ok=True)
        
        # История задач
        self.history = TaskHistory()
        
        # Отслеживание обработанных файлов
        self.processed_files = set()
        
        # Загрузить список уже обработанных задач из результатов
        self._load_processed_tasks()
        
        logger.info(f"Host Agent v2.1 initialized")
        logger.info(f"Watching: {self.tasks_dir.absolute()}")
        logger.info(f"Results: {self.results_dir.absolute()}")
        logger.info(f"Archive: {self.archive_dir.absolute()}")
        logger.info(f"Auto-archive: {self.auto_archive}")
    
    def _load_processed_tasks(self):
        """Загрузить список уже обработанных задач"""
        try:
            for result_file in self.results_dir.glob("*.json"):
                task_id = result_file.stem
                # Найти соответствующий файл задачи в архиве
                completed_file = self.archive_dir / "completed" / f"{task_id}.json"
                failed_file = self.archive_dir / "failed" / f"{task_id}.json"
                
                if completed_file.exists():
                    self.processed_files.add(str(completed_file))
                elif failed_file.exists():
                    self.processed_files.add(str(failed_file))
            
            if self.processed_files:
                logger.info(f"Found {len(self.processed_files)} already processed tasks in archive")
        except Exception as e:
            logger.error(f"Error loading processed tasks: {e}")
    
    def archive_task(self, task_file: Path, status: str) -> bool:
        """
        Архивировать файл задачи
        
        Args:
            task_file: Путь к файлу задачи
            status: 'completed' или 'failed'
            
        Returns:
            True если успешно заархивировано
        """
        if not self.auto_archive:
            return False
        
        try:
            archive_subdir = self.archive_dir / status
            archive_subdir.mkdir(parents=True, exist_ok=True)
            
            dest_file = archive_subdir / task_file.name
            
            # Если файл уже существует в архиве, добавляем timestamp
            if dest_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = task_file.stem
                dest_file = archive_subdir / f"{stem}_{timestamp}.json"
            
            shutil.move(str(task_file), str(dest_file))
            logger.info(f"📦 Archived to: {status}/{dest_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error archiving task file: {e}")
            return False
    
    def execute_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        shell: bool = True
    ) -> tuple[int, str, str]:
        """
        Выполнить команду на Windows
        
        Args:
            command: Команда для выполнения
            cwd: Рабочая директория (Windows путь)
            env: Переменные окружения
            timeout: Таймаут в секундах
            shell: Использовать shell
            
        Returns:
            (return_code, stdout, stderr)
        """
        logger.info(f"Executing: {command}")
        if cwd:
            logger.info(f"Working directory: {cwd}")
        
        try:
            # Для .bat файлов используем cmd /c
            if command.endswith('.bat') or command.endswith('.cmd'):
                command = f'cmd /c "{command}"'
            
            result = subprocess.run(
                command,
                shell=shell,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            
            logger.info(f"Command completed with code: {result.returncode}")
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            error = f"Command timeout after {timeout}s"
            logger.error(error)
            return -1, "", error
            
        except Exception as e:
            error = f"Execution error: {str(e)}"
            logger.error(error)
            return -1, "", error
    
    def process_task_file(self, file_path: Path) -> bool:
        """
        Обработать файл задачи
        
        Returns:
            True если задача успешно обработана, False если нет
        """
        # Проверяем по task_id а не по пути файла
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            task_id = task_data.get('task_id')
            
            # Проверить существует ли результат
            result_file = self.results_dir / f"{task_id}.json"
            if result_file.exists():
                logger.info(f"⏭️  Task {task_id} already processed, skipping")
                # Архивируем если ещё не заархивирован
                if self.auto_archive and file_path.exists():
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    status = result.get('status', 'completed')
                    self.archive_task(file_path, status)
                return True
                
        except:
            pass
        
        logger.info(f"📋 Processing task file: {file_path.name}")
        
        task_data = None
        success = False
        status = "failed"
        
        try:
            # Читаем задачу
            with open(file_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            task_id = task_data.get('task_id')
            action = task_data.get('action')
            params = task_data.get('params', {})
            
            if not task_id or not action:
                raise ValueError("task_id and action are required")
            
            if action != 'host_command':
                logger.warning(f"Unsupported action: {action}. Only 'host_command' is supported.")
                return False
            
            # Извлекаем параметры
            command = params.get('command')
            if not command:
                raise ValueError("'command' parameter is required")
            
            cwd = params.get('cwd')
            env = params.get('env')
            timeout = params.get('timeout', 300)
            shell = params.get('shell', True)
            
            # Выполняем команду
            logger.info(f"⚙️  Executing task: {task_id}")
            start_time = time.time()
            return_code, stdout, stderr = self.execute_command(
                command=command,
                cwd=cwd,
                env=env,
                timeout=timeout,
                shell=shell
            )
            execution_time = time.time() - start_time
            
            # Формируем результат
            status = "completed" if return_code == 0 else "failed"
            result = {
                "task_id": task_id,
                "status": status,
                "result": {
                    "return_code": return_code,
                    "stdout": stdout,
                    "stderr": stderr
                },
                "execution_time": round(execution_time, 2),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "command": command,
                "error": stderr if return_code != 0 else None
            }
            
            # Сохраняем результат
            result_file = self.results_dir / f"{task_id}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Добавляем в историю
            self.history.add_task(result)
            
            # Логируем результат
            if status == "completed":
                logger.info(f"✅ Task completed: {task_id} (time: {execution_time:.2f}s)")
                success = True
            else:
                logger.error(f"❌ Task failed: {task_id} (code: {return_code})")
            
            logger.info(f"💾 Result saved: {result_file.name}")
            
            # Архивируем файл задачи
            if self.auto_archive:
                self.archive_task(file_path, status)
            
            return success
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in {file_path.name}: {e}")
            status = "failed"
        except Exception as e:
            logger.error(f"❌ Error processing {file_path.name}: {e}")
            status = "failed"
            
            # Сохраняем ошибку как результат
            try:
                if task_data:
                    task_id = task_data.get('task_id', file_path.stem)
                else:
                    task_id = file_path.stem
                    
                error_result = {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "command": task_data.get('params', {}).get('command', '') if task_data else ''
                }
                result_file = self.results_dir / f"{task_id}.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(error_result, f, indent=2, ensure_ascii=False)
                
                # Добавляем в историю
                self.history.add_task(error_result)
            except:
                pass
        
        # Архивируем даже если была ошибка
        if self.auto_archive and file_path.exists():
            self.archive_task(file_path, status)
        
        return False
    
    def process_queue(self) -> tuple[int, int]:
        """
        Обработать очередь задач
        
        Returns:
            (total_processed, successful)
        """
        tasks = sorted(self.tasks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        
        if not tasks:
            return 0, 0
        
        total = 0
        successful = 0
        
        logger.info(f"📦 Found {len(tasks)} task files in queue")
        
        for task_file in tasks:
            total += 1
            if self.process_task_file(task_file):
                successful += 1
            
            # Небольшая пауза между задачами
            time.sleep(0.1)
        
        return total, successful
    
    def scan_and_process(self):
        """Сканировать папку и обработать новые файлы"""
        try:
            new_tasks = list(self.tasks_dir.glob("*.json"))
            
            if new_tasks:
                logger.info(f"🔔 New tasks detected: {len(new_tasks)}")
                for task_file in sorted(new_tasks, key=lambda p: p.stat().st_mtime):
                    self.process_task_file(task_file)
                    time.sleep(0.1)  # Небольшая пауза между задачами
        except Exception as e:
            logger.error(f"Error scanning tasks directory: {e}")
    
    def print_startup_info(self):
        """Вывести информацию при запуске"""
        stats = self.history.get_stats()
        recent_tasks = self.history.get_recent_tasks(5)
        
        print("\n" + "=" * 80)
        print("🚀 HOST AGENT v2.1 - STARTED")
        print("=" * 80)
        print(f"📁 Tasks Directory:   {self.tasks_dir.absolute()}")
        print(f"📊 Results Directory: {self.results_dir.absolute()}")
        print(f"📦 Archive Directory: {self.archive_dir.absolute()}")
        print(f"⏱️  Watch Interval:    {self.watch_interval}s")
        print(f"📂 Auto-archive:      {self.auto_archive}")
        print("=" * 80)
        
        print("\n📈 STATISTICS:")
        print(f"   Total Tasks:       {stats['total']}")
        print(f"   ✅ Completed:       {stats['completed']}")
        print(f"   ❌ Failed:          {stats['failed']}")
        if stats['total'] > 0:
            success_rate = (stats['completed'] / stats['total']) * 100
            print(f"   Success Rate:      {success_rate:.1f}%")
            avg_time = stats['total_execution_time'] / stats['total']
            print(f"   Avg Exec Time:     {avg_time:.2f}s")
        
        if recent_tasks:
            print("\n📋 RECENT TASKS:")
            for task in recent_tasks[-5:]:
                status_icon = "✅" if task['status'] == 'completed' else "❌"
                timestamp = task['timestamp'][:19].replace('T', ' ')
                print(f"   {status_icon} {task['task_id'][:30]:30} | {timestamp} | {task['execution_time']:.2f}s")
        
        print("\n" + "=" * 80)
        print("✅ Ready to process tasks!")
        print("💡 Put JSON files in host_tasks/ folder")
        print("📦 Processed tasks will be moved to archive/")
        print("🛑 Press Ctrl+C to stop")
        print("=" * 80 + "\n")
    
    def run(self):
        """Запустить агент"""
        logger.info("=" * 80)
        logger.info("🚀 Host Agent v2.1 started")
        logger.info("=" * 80)
        
        # Вывести информацию при запуске
        self.print_startup_info()
        
        # Обработать очередь накопившихся задач
        logger.info("🔍 Checking for pending tasks...")
        total, successful = self.process_queue()
        
        if total > 0:
            logger.info(f"✅ Processed {successful}/{total} pending tasks")
            print(f"\n✅ Processed pending queue: {successful}/{total} successful")
            print(f"📦 Tasks moved to archive/{('completed' if successful > 0 else 'failed')}/\n")
        else:
            logger.info("✅ No pending tasks in queue")
        
        print("🔄 Watching for new tasks...\n")
        
        try:
            while True:
                self.scan_and_process()
                time.sleep(self.watch_interval)
        except KeyboardInterrupt:
            print("\n" + "=" * 80)
            logger.info("🛑 Host Agent stopped by user")
            
            # Финальная статистика
            stats = self.history.get_stats()
            print("📊 FINAL STATISTICS:")
            print(f"   Total Tasks:  {stats['total']}")
            print(f"   ✅ Completed:  {stats['completed']}")
            print(f"   ❌ Failed:     {stats['failed']}")
            print("=" * 80)


def main():
    """Главная функция"""
    # Создаем папку для логов если не существует
    Path('logs').mkdir(exist_ok=True)
    
    # Создаем и запускаем агент
    agent = HostTaskExecutor(
        tasks_dir="host_tasks",
        results_dir="host_results",
        archive_dir="host_tasks_archive",
        watch_interval=2,
        auto_archive=True  # Включить автоархивацию
    )
    
    agent.run()


if __name__ == "__main__":
    main()
