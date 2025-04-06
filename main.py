import threading
from clock import Clock
from scheduler import Scheduler
from memory_manager import MemoryManager
from command_parser import load_mem_config, load_processes, load_commands

def log_event(text):
    with open("output.txt", "a") as f:
        f.write(text + "\n")

if __name__ == "__main__":
    # Clear previous output
    open("output.txt", "w").close()

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
