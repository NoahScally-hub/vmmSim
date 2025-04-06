from threading import Semaphore, Thread
import time

class Clock(Thread):
    def __init__(self):
        super().__init__()
        self.time = 0  # Clock time in ms
        self.running = True
        self.lock = Semaphore(1)  # Used as a mutex

    def run(self):
        while self.running:
            time.sleep(1)  # Wait 1 second (1000ms)
            self.lock.acquire()
            self.time += 1000
            self.lock.release()

    def get_time(self):
        self.lock.acquire()
        current = self.time
        self.lock.release()
        return current

    def tick(self, ms):
        self.lock.acquire()
        self.time += ms
        self.lock.release()

    def stop(self):
        self.running = False
