import threading
import time
import random
from threading import Semaphore, Thread
from collections import deque


################################################################################################################################################

# FILE USAGE
def log_event(text):
    with open("output.txt", "a") as f:
        f.write(text + "\n")

def load_mem_config(file_path):
    with open(file_path) as f:
        return int(f.read().strip())

def load_processes(file_path):
    with open(file_path) as f:
        lines = f.readlines()
        num_cores = int(lines[0])
        num_processes = int(lines[1])
        processes = [tuple(map(int, line.split())) for line in lines[2:]]
        return processes, num_cores

def load_commands(file_path):
    with open(file_path) as f:
        return [line.strip() for line in f.readlines()]
    
################################################################################################################################################

# CLOCK FUNCTION
class Clock(Thread):
    def __init__(self):
        super().__init__()
        self.time = 0  # Clock time in ms
        self.running = True
        self.lock = Semaphore(1)  # Used as a mutex

    def run(self):
        while self.running:
            time.sleep(1)  # Wait for 1000ms
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

################################################################################################################################################

# PROCESS THREADING
class ProcessThread(threading.Thread):
    def __init__(self, pid, start, duration, commands, memory_manager, clock):
        super().__init__()
        self.pid = pid
        self.start_time = start * 1000  # Convert to ms
        self.duration = duration * 1000  # Convert to ms
        self.commands = commands
        self.mem = memory_manager
        self.clock = clock
        self.index = 0  # Tracks current command index

    def run(self):
        # Wait until the simulated clock reaches the process's start time
        while self.clock.get_time() < self.start_time:
            self.clock.tick(10)  # Advance time in small chunks

        log_event(f"Clock: {self.clock.get_time()}, Process {self.pid}: Started.")
        start_clock = self.clock.get_time()

        while self.clock.get_time() < start_clock + self.duration:
            command = self.commands[self.index % len(self.commands)]
            parts = command.strip().split()
            action = parts[0]
            args = parts[1:]

            # Call memory manager API
            result = self.mem.api(action, *args)

            # Log the command execution
            if action == "Store":
                log_event(f"Clock: {self.clock.get_time()}, Process {self.pid}, Store: Variable {args[0]}, Value: {args[1]}")
            elif action == "Release":
                log_event(f"Clock: {self.clock.get_time()}, Process {self.pid}, Release: Variable {args[0]}")
            elif action == "Lookup":
                log_event(f"Clock: {self.clock.get_time()}, Process {self.pid}, Lookup: Variable {args[0]}, Value: {result}")

            # Tick clock to simulate work between commands
            tick_amount = random.randint(10, 500)  # ms
            self.clock.tick(tick_amount)

            self.index += 1

        log_event(f"Clock: {self.clock.get_time()}, Process {self.pid}: Finished.")

################################################################################################################################################

# SCHEDULER
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
################################################################################################################################################

# MEMORYMANAGER
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
        self.running = True

    def run(self):
        while self.running or self.queue:
            self.request_ready.acquire()
            if not self.running and not self.queue:
                break
            self.queue_mutex.acquire()
            if self.queue:
                command, args, response = self.queue.popleft()
                self.queue_mutex.release()
                result = self._handle_command(command, *args)
                response.append(result)
            else:
                self.queue_mutex.release()


    def stop(self):
        self.running = False
        self.request_ready.release()  # In case it's waiting

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

################################################################################################################################################

# MAIN FUNCTION
def main():
    # Clear previous output and disk
    open("output.txt", "w").close()
    open("vm.txt", "w").close() 

    # Load configs
    memory_size = load_mem_config("memconfig.txt")
    processes, num_cores = load_processes("processes.txt")
    commands = load_commands("commands.txt")

    # Initialize components
    clock = Clock()
    memory_manager = MemoryManager(memory_size, "vm.txt", clock)
    scheduler = Scheduler(clock, memory_manager, processes, commands, num_cores)

    # Start threads
    clock.start()
    memory_manager.start()
    scheduler.start()

    print("Simulation running... check output.txt after completion.")

    # Wait for scheduler to finish
    scheduler.join()

    # Stop and wait for clock
    clock.stop()
    clock.join()

    memory_manager.stop()
    memory_manager.join()

if __name__ == "__main__":
   main()