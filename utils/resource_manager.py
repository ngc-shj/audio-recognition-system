import sys
import time
import threading
import psutil

class ResourceManager:
    def __init__(self, config_manager=None, min_threads: int = 2, max_threads: int = 8):
        if config_manager and hasattr(config_manager, 'resources'):
            res_config = config_manager.resources
            self.min_threads = res_config.min_threads
            self.max_threads = res_config.max_threads
        else:
            self.min_threads = min_threads
            self.max_threads = max_threads
        
        self.current_threads = self.min_threads

    def get_optimal_thread_count(self):
        cpu_usage = psutil.cpu_percent()
        if cpu_usage < 30:
            self.current_threads = max(self.min_threads, self.current_threads - 1)
        elif cpu_usage > 70:
            self.current_threads = min(self.max_threads, self.current_threads + 1)
        return self.current_threads

    def monitor_resources(self, stop_event: threading.Event = None, interval: int = 5):
        """
        Monitor system resources in a loop.

        Args:
            stop_event: threading.Event to signal when to stop monitoring
            interval: monitoring interval in seconds
        """
        if stop_event is None:
            stop_event = threading.Event()

        while not stop_event.is_set():
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            print(f"CPU使用率: {cpu_percent:.1f}% | "
                  f"メモリ使用率: {memory_percent:.1f}% "
                  f"({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")

            stop_event.wait(timeout=interval)

    def get_system_info(self) -> dict:
        memory = psutil.virtual_memory()
        
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(),
            'memory_total_gb': memory.total / (1024**3),
            'memory_available_gb': memory.available / (1024**3),
            'memory_percent': memory.percent,
            'platform': sys.platform,
            'current_threads': self.current_threads,
            'min_threads': self.min_threads,
            'max_threads': self.max_threads,
        }

    def print_system_info(self):
        """システム情報を表示"""
        info = self.get_system_info()
        print("\n" + "="*50)
        print("システム情報")
        print("="*50)
        print(f"プラットフォーム: {info['platform']}")
        print(f"CPUコア数: {info['cpu_count']}")
        print(f"CPU使用率: {info['cpu_percent']:.1f}%")
        print(f"メモリ合計: {info['memory_total_gb']:.1f} GB")
        print(f"メモリ利用可能: {info['memory_available_gb']:.1f} GB")
        print(f"メモリ使用率: {info['memory_percent']:.1f}%")
        print(f"スレッド設定: {info['min_threads']}-{info['max_threads']} (現在: {info['current_threads']})")
        print("="*50 + "\n")

