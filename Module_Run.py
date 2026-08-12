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
        ("Module 1: Bulk Ingestion", os.path.join(script_dir, "Module1.py")),
        ("Module 2: Source URI Merging", os.path.join(script_dir, "Module2.py")),
        ("Module 3: Field Formatting", os.path.join(script_dir, "Module3_Formatting.py")),
        ("Module 4: Watchlist Consolidation", os.path.join(script_dir, "Module4_Consolidation.py")),
        ("Module 5: Database Sync", os.path.join(script_dir, "Module5_Sync.py")),
    ]

    summary = []

    for name, script_path in modules:
        if not os.path.exists(script_path):
            # Fallback to current working directory if script path is relative
            script_path = os.path.basename(script_path)

        mod_start = time.time()
        mod_time_str = datetime.now().strftime("%H:%M:%S")
        logging.info("\n---------------------------------------------------------")
        logging.info(">>> [%s] Launching %s...", mod_time_str, name)
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

