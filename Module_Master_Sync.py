# -*- coding: utf-8 -*-
import json
import os
import pyodbc
import sys
import time
import logging
import argparse
from datetime import datetime

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()

def load_config(config_path: str) -> dict:
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_connection(config: dict) -> pyodbc.Connection:
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = (
        f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};"
        f"Trusted_Connection={trusted};"
    )
    return pyodbc.connect(conn_str, autocommit=True)

def run_master_sync():
    args = parse_args()
    setup_logging(args.log_level)
    start_time_str = datetime.now().strftime("%H:%M:%S")
    global_start = time.time()

    logging.info("=========================================================")
    logging.info("   MODULE: MASTER DELTA SYNC (NegativeList_Master)       ")
    logging.info("   Start Time: %s", start_time_str)
    logging.info("=========================================================")

    config = load_config(args.config)
    conn = get_connection(config)
    cursor = conn.cursor()

    try:
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")

        logging.info("[Step 1/2] Verifying production database state...")
        cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList' AND schema_id = SCHEMA_ID('dbo')")
        if cursor.fetchone()[0] == 0:
            logging.info("[Step 1/2] Initial deployment state detected. Skipping pre-delta master filter.")
            return

        logging.info("[Step 1/2] Building NegativeList_Present tracking index...")
        cursor.execute("""
            DROP TABLE IF EXISTS #NegativeList_Present;
            SELECT DISTINCT EntityGUID, EntityAliasGUID
            INTO #NegativeList_Present
            FROM dbo.NegativeList WITH (NOLOCK)
            WHERE EntityGUID IS NOT NULL;
            CREATE CLUSTERED INDEX IX_NLP_EntityGUID ON #NegativeList_Present(EntityGUID);
        """)

        logging.info("[Step 2/2] Preparing staging workspace for daily delta ingestion...")
        cursor.execute("""
            IF OBJECT_ID('dbo.NegativeList_New1_Temp', 'U') IS NOT NULL 
                DROP TABLE dbo.NegativeList_New1_Temp;
        """)
        logging.info("[Step 2/2] Staging workspace ready for delta batch.")

        elapsed_min = (time.time() - global_start) / 60
        end_time_str = datetime.now().strftime("%H:%M:%S")

        logging.info("=========================================================")
        logging.info("   MASTER SYNC COMPLETED SUCCESSFULLY                    ")
        logging.info("   End Time: %s | Duration: %.2f minutes", end_time_str, elapsed_min)
        logging.info("=========================================================")

    except Exception as e:
        logging.error("Error during Module_MasterSync: %s", str(e), exc_info=True)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run_master_sync()

