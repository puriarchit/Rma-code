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
    logging.info("=== Starting Module 2: Source URI Merging [Started at %s] ===", start_time_str)

    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()

    cursor.execute("SET NOCOUNT ON; SET XACT_ABORT ON;")

    logging.info("[1/3] Resetting target table EntitySourceItem_New...")
    step_start = time.time()
    cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
    cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New](<[EntityGUID] [nvarchar](50>) NULL, [SourceURI] [nvarchar](max) NULL) WITH (DATA_COMPRESSION = PAGE)")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
    logging.info("[1/3] Target table reset completed in %.2f seconds.", time.time() - step_start)

    logging.info("[2/3] Merging source links into EntitySourceItem_New...")
    step_start = time.time()

    cursor.execute("""
        INSERT INTO dbo.EntitySourceItem_New WITH (TABLOCK) (EntityGUID, SourceURI)
        SELECT
            D.EntityGUID,
            COALESCE(
                STRING_AGG(
                    CONVERT(NVARCHAR(MAX), D.SourceURI),
                    N'; '
                ),
                N''
            ) AS SourceURI
        FROM
        (
            SELECT DISTINCT
                EntityGUID,
                NULLIF(SourceURI, N'') AS SourceURI
            FROM dbo.EntitySourceItem WITH (NOLOCK)
            WHERE EntityGUID IS NOT NULL
        ) AS D
        GROUP BY
            D.EntityGUID;
    """)

    merge_time = time.time() - step_start

    cursor.execute("SELECT SUM(rows) FROM sys.partitions WHERE object_id = OBJECT_ID('dbo.EntitySourceItem_New') AND index_id IN (0, 1)")
    inserted_count = cursor.fetchone()[0] or 0

    logging.info("[2/3] Source URI merging completed in %.2f seconds (%.2f mins). Total Profiles: %s.", merge_time, merge_time / 60, f"{inserted_count:,}")

    logging.info("[3/3] Cleaning up raw staging tables...")
    try:
        cursor.execute("TRUNCATE TABLE EntitySourceItem")
        logging.info("  Reclaimed space: truncated staging table EntitySourceItem.")
    except Exception as e:
        logging.warning("Could not truncate EntitySourceItem: %s", e)

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 2: Source URI Merging completed successfully in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
