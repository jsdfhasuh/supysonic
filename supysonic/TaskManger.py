"""
后台任务管理模块
提供线程池和任务队列功能
"""
import logging
import time
from threading import Thread, Lock
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict, Optional


class TaskManager:
    """后台任务管理器"""
    
    def __init__(self, max_workers: int = 5,):
        """
        初始化任务管理器
        
        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self.task_queue = Queue()
        self.task_results: Dict[str, Dict[str, Any]] = {}
        self.results_lock = Lock()
        self.is_running = True
        self.logger = logging.getLogger(__name__)
        
        # 启动后台工作线程
        self.worker_thread = Thread(target=self._background_worker, daemon=True)
        self.worker_thread.start()
        self.logger.info("Background worker thread started")
    
    def _background_worker(self):
        """后台工作线程，不断从队列中取任务执行"""
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:
                    break
                
                task_id, func, args, kwargs = task
                try:
                    result = func(*args, **kwargs)
                    self.logger.info(f"Task {task_id} completed successfully")
                    with self.results_lock:
                        self.task_results[task_id] = {
                            'status': 'completed',
                            'result': result,
                            'timestamp': time.time()
                        }
                except Exception as e:
                    with self.results_lock:
                        self.task_results[task_id] = {
                            'status': 'failed',
                            'error': str(e),
                            'timestamp': time.time()
                        }
                finally:
                    self.task_queue.task_done()
            except:
                continue
    
    def submit_task(self, task_id: str, func: Callable, *args, **kwargs) -> str:
        """
        提交后台任务到队列
        
        Args:
            task_id: 任务唯一标识
            func: 要执行的函数
            *args: 函数位置参数
            **kwargs: 函数关键字参数
        
        Returns:
            任务ID
        """
        with self.results_lock:
            self.task_results[task_id] = {
                'status': 'pending',
                'timestamp': time.time()
            }
        
        self.task_queue.put((task_id, func, args, kwargs))
        self.logger.info(f"Submitted task {task_id} to the queue")
        return task_id
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务结果字典，如果任务不存在返回 None
        """
        with self.results_lock:
            return self.task_results.get(task_id)
    
    def clean_old_results(self, max_age: int = 3600):
        """
        清理超过指定时间的旧结果
        
        Args:
            max_age: 最大保留时间（秒），默认1小时
        """
        current_time = time.time()
        with self.results_lock:
            to_delete = [
                task_id for task_id, result in self.task_results.items()
                if current_time - result['timestamp'] > max_age
            ]
            for task_id in to_delete:
                del self.task_results[task_id]
    
    def shutdown(self):
        """关闭任务管理器"""
        self.is_running = False
        self.task_queue.put(None)
        self.worker_thread.join(timeout=5)


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器实例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(max_workers=5)
    return _task_manager


def submit_background_task(task_id: str, func: Callable, *args, **kwargs) -> str:
    """便捷函数：提交后台任务"""
    return get_task_manager().submit_task(task_id, func, *args, **kwargs)


def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """便捷函数：获取任务结果"""
    return get_task_manager().get_task_result(task_id)


def clean_old_task_results(max_age: int = 3600):
    """便捷函数：清理旧任务结果"""
    get_task_manager().clean_old_results(max_age)