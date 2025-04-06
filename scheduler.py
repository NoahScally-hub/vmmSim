import threading
from process_thread import ProcessThread
import time

class Scheduler(threading.Thread):
    def __init__(self, clock, memory_manager, processes, commands, max_cores):
        super().__init__()
        self.clock = clock
        self.memory_manager = memory_manager
        self.processes = processes
        self.commands = commands
        self.max_cores = max_cores
        self.queue = []
        self.active = []

    def run(self):
        process_threads = [
            (start * 1000, ProcessThread(pid=i+1, start=start, duration=duration,
                                         commands=self.commands, memory_manager=self.memory_manager,
                                         clock=self.clock))
            for i, (start, duration) in enumerate(self.processes)
        ]

        while process_threads or self.active:
            now = self.clock.get_time()

            # Start processes
            for i, (start_time, thread) in list(enumerate(process_threads)):
                if start_time <= now and len(self.active) < self.max_cores:
                    thread.start()
                    self.active.append(thread)
                    del process_threads[i]
                    break  # re-evaluate list after modification

            # Clean up finished processes
            self.active = [p for p in self.active if p.is_alive()]
            time.sleep(0.5)
