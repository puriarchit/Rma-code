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

def main():
    setup_logging()
    global_start = time.time()
    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 2: Source URI Merging [Started at %s] ===", start_time_str)

    config = load_config()
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
    
    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()

    step1_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[1/2] Resetting target table EntitySourceItem_New at %s...", step1_start)
    step_start = time.time()
    cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
    cursor.execute("""
        CREATE TABLE [dbo].[EntitySourceItem_New](
            [EntityGUID] [nvarchar](50) NULL,
            [SourceURI] [nvarchar](max) NULL
        ) WITH (DATA_COMPRESSION = PAGE)
    """)
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
    logging.info("[1/2] Target table reset completed in %.2f seconds.", time.time() - step_start)

    step2_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[2/2] Started merging SourceURI records into EntitySourceItem_New at %s (Ultra-Fast SQL Engine)...", step2_start)
    step_start = time.time()

    # Try ultra-fast set-based STRING_AGG first
    try:
        logging.info("Executing set-based parallel aggregation in SQL Server...")
        cursor.execute("""
            INSERT INTO EntitySourceItem_New WITH (TABLOCK) (EntityGUID, SourceURI)
            SELECT 
                EntityGUID,
                STRING_AGG(CAST(SourceURI AS NVARCHAR(MAX)), '; ') WITHIN GROUP (ORDER BY SourceURI) AS SourceURI
            FROM EntitySourceItem WITH (NOLOCK)
            WHERE SourceURI IS NOT NULL AND SourceURI <> ''
            GROUP BY EntityGUID
            OPTION (MAXDOP 8, RECOMPILE);
        """)
        logging.info("Set-based aggregation completed successfully.")
    except Exception as ex:
        logging.warning("Set-based aggregation fallback: %s. Using chunked merge...", ex)
        # Fallback XML STUFF chunked insert
        cursor.execute("""
            INSERT INTO EntitySourceItem_New WITH (TABLOCK) (EntityGUID, SourceURI)
            SELECT 
                EntityGUID,
                STUFF((
                    SELECT '; ' + SourceURI
                    FROM EntitySourceItem s WITH (NOLOCK)
                    WHERE s.EntityGUID = e.EntityGUID AND s.SourceURI IS NOT NULL AND s.SourceURI <> ''
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS SourceURI
            FROM EntitySourceItem e WITH (NOLOCK)
            GROUP BY EntityGUID
            OPTION (MAXDOP 8);
        """)

    cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New WITH (NOLOCK)")
    row_count = cursor.fetchone()[0]

    # Reclaim raw space immediately
    try:
        cursor.execute("TRUNCATE TABLE EntitySourceItem")
        logging.info("Reclaimed raw space: truncated EntitySourceItem.")
    except Exception as e:
        logging.warning("Could not truncate EntitySourceItem: %s", e)

    cursor.close()
    conn.close()

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 2 completed in %.2f minutes [Finished at %s] (Merged Unique Profiles: %d) ===", elapsed_min, end_time_str, row_count)

if __name__ == "__main__":
    main()


