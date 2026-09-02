# -*- coding: utf-8 -*-
import json
import os
import pyodbc
import sys
import time
import logging
from datetime import datetime

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_connection(config: dict) -> pyodbc.Connection:
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    server_name = db["server"]
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={server_name};DATABASE={db['name']};Trusted_Connection={trusted};"
    try:
        return pyodbc.connect(conn_str, autocommit=True, timeout=3)
    except Exception:
        fallback_str = f"DRIVER={{{db['driver']}}};SERVER=.;DATABASE={db['name']};Trusted_Connection={trusted};"
        return pyodbc.connect(fallback_str, autocommit=True)

def main():
    setup_logging()
    global_start = time.time()
    start_time_str = datetime.now().strftime("%H:%M:%S")

    logging.info("=========================================================")
    logging.info("   MODULE 2: SOURCE URL AGGREGATION                      ")
    logging.info("   Start Time: %s", start_time_str)
    logging.info("=========================================================")

    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()

    cursor.execute("SET NOCOUNT ON; SET XACT_ABORT ON;")

    logging.info("[Step 1/2] Initializing target table dbo.EntitySourceItem_New...")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
    cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL) WITH (DATA_COMPRESSION = PAGE)")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
    logging.info("[Step 1/2] Target table ready.")

    logging.info("[Step 2/2] Merging and consolidating source website URLs...")
    step_start = time.time()
    cursor.execute("""
        INSERT INTO dbo.EntitySourceItem_New WITH (TABLOCK) (EntityGUID, SourceURI)
        SELECT
            EntityGUID,
            ISNULL(N' ' + STRING_AGG(REPLACE(REPLACE(CONVERT(NVARCHAR(MAX), SourceURI), N'&amp;', N'&'), N'&', N'&amp;'), N'; ') WITHIN GROUP (ORDER BY EntitySourceItemGUID ASC), N'')
        FROM dbo.EntitySourceItem WITH (NOLOCK)
        WHERE EntityGUID IS NOT NULL AND SourceURI IS NOT NULL AND SourceURI != N''
        GROUP BY EntityGUID;
    """)

    cursor.execute("SELECT COUNT(*) FROM dbo.EntitySourceItem_New")
    inserted_count = cursor.fetchone()[0]
    merge_time = time.time() - step_start

    logging.info("[Step 2/2] Aggregated %s entity URL profiles in %.2f seconds.", f"{inserted_count:,}", merge_time)

    cursor.close()
    conn.close()

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")

    logging.info("=========================================================")
    logging.info("   MODULE 2 COMPLETED SUCCESSFULLY                       ")
    logging.info("   End Time: %s | Duration: %.2f minutes", end_time_str, elapsed_min)
    logging.info("=========================================================")

if __name__ == "__main__":
    main()

