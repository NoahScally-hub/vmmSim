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
