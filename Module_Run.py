# -*- coding: utf-8 -*-
import sys
import os
import time
import subprocess
import logging
from datetime import datetime

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

def resolve_script(script_dir: str, candidates: list) -> str:
    for name in candidates:
        p1 = os.path.join(script_dir, name)
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(os.getcwd(), name)
        if os.path.exists(p2):
            return p2
    return os.path.join(script_dir, candidates[0])

def main():
    setup_logging()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_start = time.time()
    start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logging.info("=========================================================")
    logging.info("   STARTING FULL LEXISNEXIS ETL PIPELINE (MODULES 1 to 5) ")
    logging.info("   Start Time: %s", start_time_str)
    logging.info("=========================================================")

    modules = [
        ("Module 1: Bulk Ingestion", ["Module1.py"]),
        ("Module 2: Source URI Merging", ["Module2_SourceItem.py", "Module2.py"]),
        ("Module 3: Field Formatting", ["Module3_Formatting.py", "Module3.py"]),
        ("Module 4: Watchlist Consolidation", ["Module4_Consolidation.py", "Module4.py"]),
        ("Module 5: Database Sync", ["Module5.py", "Module5_Sync.py"]),
    ]

    summary = []

    for name, candidates in modules:
        script_path = resolve_script(script_dir, candidates)
        mod_start = time.time()
        mod_time_str = datetime.now().strftime("%H:%M:%S")
        logging.info("\n---------------------------------------------------------")
        logging.info(">>> [%s] Launching %s (%s)...", mod_time_str, name, os.path.basename(script_path))
        logging.info("---------------------------------------------------------")

        try:
            res = subprocess.run([sys.executable, script_path], check=True)
            elapsed = (time.time() - mod_start) / 60
            summary.append((name, "SUCCESS", f"{elapsed:.2f} min"))
            logging.info(">>> %s completed successfully in %.2f minutes.\n", name, elapsed)
        except subprocess.CalledProcessError as err:
            elapsed = (time.time() - mod_start) / 60
            summary.append((name, "FAILED", f"{elapsed:.2f} min"))
            logging.error("!!! %s failed with exit code %d after %.2f minutes. Aborting pipeline.", name, err.returncode, elapsed)
            sys.exit(err.returncode)

    pipeline_elapsed = (time.time() - pipeline_start) / 60
    end_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logging.info("=========================================================")
    logging.info("   PIPELINE EXECUTION SUMMARY REPORT                     ")
    logging.info("   End Time: %s", end_time_str)
    logging.info("   Total Duration: %.2f minutes", pipeline_elapsed)
    logging.info("=========================================================")
    for name, status, duration in summary:
        logging.info(" - %-35s : %-10s (%s)", name, status, duration)
    logging.info("=========================================================")

if __name__ == "__main__":
    main()

