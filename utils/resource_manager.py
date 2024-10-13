import sys
import psutil

if sys.platform != 'win32':
    import resource

class ResourceManager:
    def __init__(self, min_threads=2, max_threads=8):
        self.min_threads = min_threads
        self.max_threads = max_threads
        self.current_threads = min_threads
        if sys.platform != 'win32':
            self.set_resource_limits()

    def set_resource_limits(self):
        # CPUタイムを300秒に制限
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
        # メモリ使用量を8GBに制限
        #resource.setrlimit(resource.RLIMIT_AS, (8 * 1024 * 1024 * 1024, -1))

    def get_optimal_thread_count(self):
        cpu_usage = psutil.cpu_percent()
        if cpu_usage < 30:
            self.current_threads = max(self.min_threads, self.current_threads - 1)
        elif cpu_usage > 70:
            self.current_threads = min(self.max_threads, self.current_threads + 1)
        return self.current_threads

    def monitor_resources(self):
        while True:
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            print(f"CPU使用率: {cpu_percent}%, メモリ使用率: {memory_percent}%")
            time.sleep(5)  # 5秒ごとに更新

