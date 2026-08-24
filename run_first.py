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
    logging.info("   ETL PIPELINE ORCHESTRATOR - FIRST RUN MODE           ")
    logging.info("   Start Time: %s", start_time_str)
    logging.info("   Flow matches: PackageExecutionList_First             ")
    logging.info("=========================================================")

    # SSIS First Run flow mapping:
    # 1. Files_1 & Files_2 -> Module1.py
    # 2. EntitySourceItem_1 to 5 -> Module2_SourceItem.py
    # 3. Entity_Citizenship, EntityAddress, EntityCountryAssociation, EntityDOB, EntityIdentification, EntityRemark -> Module3_Formatting.py
    # 4. NegativeList_1_1, NegativeList_1_2, NegativeList_1_3 -> Module4_Consolidation.py
    # (Note: Module 5 is NOT executed in First Run)

    steps = [
        ("Module 1: Ingestion (Files_1, Files_2)", "Module1.py", []),
        ("Module 2: Source URI Merging (EntitySourceItem_1 to 5)", "Module2_SourceItem.py", []),
        ("Module 3: Field Formatting (EntityAddress, DOB, Citizenship, ID, Remark)", "Module3_Formatting.py", []),
        ("Module 4: Watchlist Consolidation (NegativeList_1_1 to 1_3)", "Module4_Consolidation.py", [])
    ]

    summary = []

    for name, script_name, args in steps:
        script_path = os.path.join(script_dir, script_name)
        mod_start = time.time()
        mod_time_str = datetime.now().strftime("%H:%M:%S")
        logging.info("\n---------------------------------------------------------")
        logging.info(">>> [%s] Launching %s...", mod_time_str, name)
        logging.info("---------------------------------------------------------")

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
    logging.info("   FIRST RUN PIPELINE EXECUTION SUMMARY                  ")
    logging.info("   End Time: %s", end_time_str)
    logging.info("   Total Duration: %.2f minutes", pipeline_elapsed)
    logging.info("=========================================================")
    for name, status, duration in summary:
        logging.info(" - %-55s : %-10s (%s)", name, status, duration)
    logging.info("=========================================================")

if __name__ == "__main__":
    main()
