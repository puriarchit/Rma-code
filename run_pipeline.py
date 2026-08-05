import os
import sys
import subprocess
import time

scripts = {
    "module1": "Module1_Load.py",
    "module2": "Module2.py",
    "module3": "Module3_Formatting.py",
    "module4": "Module4_Consolidation.py"
}

def get_script_path(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def run_script_sequential(name, filename):
    filepath = get_script_path(filename)
    if not os.path.exists(filepath):
        print(f"error: {filename} not found at {filepath}")
        sys.exit(1)
        
    print(f"starting {name}...")
    start_time = time.time()
    
    result = subprocess.run([sys.executable, filepath], check=True)
    time_taken = (time.time() - start_time) / 60
    
    print(f"{name} finished, took {time_taken:.2f} minutes.\n")
    return time_taken

if __name__ == "__main__":
    print("starting pipeline orchestrator...")
    pipeline_start = time.time()
    
    t1 = run_script_sequential("module 1", scripts["module1"])
    t2 = run_script_sequential("module 2", scripts["module2"])
    t3 = run_script_sequential("module 3", scripts["module3"])
    t4 = run_script_sequential("module 4", scripts["module4"])
    
    total_pipeline_time = (time.time() - pipeline_start) / 60
    
    print("pipeline finished. summary:")
    print(f"module 1: {t1:.2f} minutes")
    print(f"module 2: {t2:.2f} minutes")
    print(f"module 3: {t3:.2f} minutes")
    print(f"module 4: {t4:.2f} minutes")
    print(f"total runtime: {total_pipeline_time:.2f} minutes")

