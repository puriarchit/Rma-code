import os
import sys
import subprocess
import threading
import time

# Script configuration matching the exact file names on VM VS Code tabs
scripts = {
    "module1": "Module1.py",
    "module2": "Module2_Sourceitem.py",
    "module3": "Module3_Formatting.py"
}

def get_script_path(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def run_script_sequential(name, filename):
    filepath = get_script_path(filename)
    if not os.path.exists(filepath):
        print(f"❌ Error: {filename} not found at {filepath}")
        sys.exit(1)
        
    print(f"\n============================================================")
    print(f"🚀 Starting {name.upper()} ({filename})...")
    print(f"============================================================\n")
    
    start_time = time.time()
    # Runs the script and streams output directly to console
    result = subprocess.run([sys.executable, filepath], check=True)
    time_taken = (time.time() - start_time) / 60
    
    print(f"\n✅ {name.upper()} finished! - Time taken: {time_taken:.2f} minutes\n")
    return time_taken

def stream_output(process, prefix):
    # Streams stdout of parallel processes line-by-line with a prefix
    for line in iter(process.stdout.readline, b''):
        decoded = line.decode('utf-8', errors='ignore').strip()
        if decoded:
            print(f"{prefix} {decoded}")
            sys.stdout.flush()

def run_parallel_modules(mod2_file, mod3_file):
    path2 = get_script_path(mod2_file)
    path3 = get_script_path(mod3_file)
    
    if not os.path.exists(path2):
        print(f"❌ Error: {mod2_file} not found at {path2}")
        sys.exit(1)
    if not os.path.exists(path3):
        print(f"❌ Error: {mod3_file} not found at {path3}")
        sys.exit(1)
        
    print(f"\n============================================================")
    print(f"🚀 Starting MODULE 2 & MODULE 3 in Parallel...")
    print(f"   - Running: {mod2_file}")
    print(f"   - Running: {mod3_file}")
    print(f"============================================================\n")
    
    start_time = time.time()
    
    # Launch both subprocesses concurrently
    p2 = subprocess.Popen([sys.executable, path2], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    p3 = subprocess.Popen([sys.executable, path3], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    
    # Create threads to read and prefix outputs concurrently
    t2 = threading.Thread(target=stream_output, args=(p2, "[Module 2]"))
    t3 = threading.Thread(target=stream_output, args=(p3, "[Module 3]"))
    
    t2.start()
    t3.start()
    
    # Wait for both processes to complete
    p2.wait()
    p3.wait()
    
    t2.join()
    t3.join()
    
    time_taken = (time.time() - start_time) / 60
    
    if p2.returncode != 0 or p3.returncode != 0:
        print(f"\n❌ Error: Parallel execution failed! Module 2 Code: {p2.returncode}, Module 3 Code: {p3.returncode}")
        sys.exit(1)
        
    print(f"\n✅ Parallel execution of Module 2 & 3 completed successfully! - Time taken: {time_taken:.2f} minutes\n")
    return time_taken

if __name__ == "__main__":
    print("============================================================")
    print("🌟 LexisNexis Staging Pipeline Orchestrator (Single-Run) 🌟")
    print("============================================================")
    
    pipeline_start = time.time()
    
    # Step 1: Run Module 1 Ingestion Sequentially
    t1 = run_script_sequential("Module 1 (Ingestion)", scripts["module1"])
    
    # Step 2: Run Module 2 & Module 3 in Parallel
    t2_3 = run_parallel_modules(scripts["module2"], scripts["module3"])
    
    total_pipeline_time = (time.time() - pipeline_start) / 60
    
    print("============================================================")
    print("🏁 Pipeline Execution Completed Successfully! Summary:")
    print(f"  - Module 1 (Ingestion): {t1:.2f} minutes")
    print(f"  - Module 2 & 3 (Parallel): {t2_3:.2f} minutes")
    print(f"  - Total Run Time: {total_pipeline_time:.2f} minutes")
    print("============================================================")
