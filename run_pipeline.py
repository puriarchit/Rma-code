import os
import sys
import subprocess
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
    # Using check=True so that if any step fails, the orchestrator stops immediately
    result = subprocess.run([sys.executable, filepath], check=True)
    time_taken = (time.time() - start_time) / 60
    
    print(f"\n✅ {name.upper()} finished! - Time taken: {time_taken:.2f} minutes\n")
    return time_taken

if __name__ == "__main__":
    print("============================================================")
    print("🌟 LexisNexis Staging Pipeline Orchestrator (Sequential) 🌟")
    print("============================================================")
    
    pipeline_start = time.time()
    
    # Step 1: Run Module 1 Ingestion (Sequential)
    t1 = run_script_sequential("Module 1 (Ingestion)", scripts["module1"])
    
    # Step 2: Run Module 2 Web Links Merge (Sequential - Standalone to prevent I/O thrashing)
    t2 = run_script_sequential("Module 2 (Web Links Merge)", scripts["module2"])
    
    # Step 3: Run Module 3 Pivoting & Formatting (Sequential - Standalone to prevent I/O thrashing)
    t3 = run_script_sequential("Module 3 (Pivoting & Formatting)", scripts["module3"])
    
    total_pipeline_time = (time.time() - pipeline_start) / 60
    
    print("============================================================")
    print("🏁 Pipeline Execution Completed Successfully! Summary:")
    print(f"  - Module 1 (Ingestion): {t1:.2f} minutes")
    print(f"  - Module 2 (Web Links): {t2:.2f} minutes")
    print(f"  - Module 3 (Formatting): {t3:.2f} minutes")
    print(f"  - Total Run Time: {total_pipeline_time:.2f} minutes")
    print("============================================================")
