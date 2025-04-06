import threading
import random

# Logging function to write to output.txt
def log_event(text):
    with open("output.txt", "a") as f:
        f.write(text + "\n")

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
