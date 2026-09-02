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
    logging.info("   ETL PIPELINE ORCHESTRATOR - INCREMENTAL RUN MODE       ")
    logging.info("   Start Time: %s", start_time_str)
    logging.info("   Scope: 6 Automated Steps (with Module_MasterSync)      ")
    logging.info("=========================================================")

    steps = [
        ("Step 1: Delta Ingestion (Files_1, Files_2)", "Module1.py", []),
        ("Step 2: Pre-Delta Master Sync (NegativeList_Master)", "Module_MasterSync.py", []),
        ("Step 3: Source URI Merging (EntitySourceItem_1 to 5)", "Module2_SourceItem.py", []),
        ("Step 4: Field Formatting (EntityAddress, DOB, Citizenship, ID, Remark)", "Module3_Formatting.py", []),
        ("Step 5: Watchlist Consolidation (NegativeList_1_1 to 1_3)", "Module4_Consolidation.py", []),
        ("Step 6: Production Sync (NegativeList_2_1 to 4_5)", "Module5.py", ["--mode", "inc"])
    ]

    summary = []

    for name, script_name, args in steps:
        script_path = os.path.join(script_dir, script_name)
        mod_start = time.time()
        mod_time_str = datetime.now().strftime("%H:%M:%S")

        logging.info("")
        logging.info(">>> [%s] Launching %s...", mod_time_str, name)

        try:
            cmd = [sys.executable, script_path] + args
            subprocess.run(cmd, check=True)
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
    logging.info("   INCREMENTAL RUN PIPELINE EXECUTION SUMMARY            ")
    logging.info("   End Time: %s", end_time_str)
    logging.info("   Total Duration: %.2f minutes", pipeline_elapsed)
    logging.info("=========================================================")
    for name, status, duration in summary:
        logging.info(" - %-65s : %-10s (%s)", name, status, duration)
    logging.info("=========================================================")

if __name__ == "__main__":
    main()
