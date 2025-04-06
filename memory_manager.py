from threading import Thread, Semaphore
from collections import deque

# Logger to write to output.txt
def log_event(text):
    with open("output.txt", "a") as f:
        f.write(text + "\n")

class MemoryManager(Thread):
    def __init__(self, size, disk_file, clock):
        super().__init__()
        self.main_memory = {}  # {var_id: (value, last_access_time)}
        self.main_mem_order = deque(maxlen=size)  # LRU tracking: var_ids
        self.memory_mutex = Semaphore(1)
        self.queue_mutex = Semaphore(1)
        self.clock = clock
        self.disk_file = disk_file

        self.queue = deque()
        self.request_ready = Semaphore(0)

    def run(self):
        while True:
            self.request_ready.acquire()
            self.queue_mutex.acquire()
            command, args, response = self.queue.popleft()
            self.queue_mutex.release()

            result = self._handle_command(command, *args)
            response.append(result)

    def api(self, command, *args):
        response = []
        self.queue_mutex.acquire()
        self.queue.append((command, args, response))
        self.queue_mutex.release()
        self.request_ready.release()

        while not response:
            pass
        return response[0]

    def _handle_command(self, command, *args):
        if command == "Store":
            return self._store(*args)
        elif command == "Release":
            return self._release(*args)
        elif command == "Lookup":
            return self._lookup(*args)

    def _store(self, var_id, value):
        self.memory_mutex.acquire()
        time = self.clock.get_time()

        # Already in memory: update
        if var_id in self.main_memory:
            self.main_memory[var_id] = (value, time)
            if var_id in self.main_mem_order:
                self.main_mem_order.remove(var_id)
            self.main_mem_order.append(var_id)

        # Room in memory: store directly
        elif self.main_mem_order.maxlen is None or len(self.main_memory) < self.main_mem_order.maxlen:
            self.main_memory[var_id] = (value, time)
            self.main_mem_order.append(var_id)

        # Memory full: send least recently used to disk, then store new
        else:
            lru_var = self.main_mem_order.popleft()
            lru_val, _ = self.main_memory[lru_var]
            self._store_to_disk(lru_var, lru_val)
            del self.main_memory[lru_var]

            log_event(f"Clock: {time}, Memory Manager, SWAP: Variable {var_id} with Variable {lru_var}")

            self.main_memory[var_id] = (value, time)
            self.main_mem_order.append(var_id)

        self.memory_mutex.release()
        return f"Stored: {var_id} = {value}"

    def _release(self, var_id):
        self.memory_mutex.acquire()

        if var_id in self.main_memory:
            del self.main_memory[var_id]
            if var_id in self.main_mem_order:
                self.main_mem_order.remove(var_id)
        else:
            self._remove_from_disk(var_id)

        self.memory_mutex.release()
        return f"Released: {var_id}"

    def _lookup(self, var_id):
        self.memory_mutex.acquire()
        time = self.clock.get_time()

        # Found in memory
        if var_id in self.main_memory:
            value, _ = self.main_memory[var_id]
            self.main_memory[var_id] = (value, time)
            if var_id in self.main_mem_order:
                self.main_mem_order.remove(var_id)
            self.main_mem_order.append(var_id)
            self.memory_mutex.release()
            return value

        # Not in memory: check disk
        value = self._read_from_disk(var_id)
        if value is None:
            self.memory_mutex.release()
            return -1

        # Swap needed: memory is full
        if self.main_mem_order.maxlen is not None and len(self.main_memory) >= self.main_mem_order.maxlen:
            lru_var = self.main_mem_order.popleft()
            lru_val, _ = self.main_memory[lru_var]
            self._store_to_disk(lru_var, lru_val)
            del self.main_memory[lru_var]

            log_event(f"Clock: {time}, Memory Manager, SWAP: Variable {var_id} with Variable {lru_var}")

        self.main_memory[var_id] = (value, time)
        self.main_mem_order.append(var_id)
        self.memory_mutex.release()
        return value

    def _store_to_disk(self, var_id, value):
        with open(self.disk_file, 'a') as f:
            f.write(f"{var_id} {value}\n")

    def _read_from_disk(self, var_id):
        value = None
        new_lines = []

        with open(self.disk_file, 'r') as f:
            lines = f.readlines()

        for line in lines:
            vid, val = line.strip().split()
            if vid == var_id:
                value = int(val)
            else:
                new_lines.append(line)

        with open(self.disk_file, 'w') as f:
            f.writelines(new_lines)

        return value

    def _remove_from_disk(self, var_id):
        new_lines = []

        with open(self.disk_file, 'r') as f:
            lines = f.readlines()

        for line in lines:
            if not line.startswith(f"{var_id} "):
                new_lines.append(line)

        with open(self.disk_file, 'w') as f:
            f.writelines(new_lines)
