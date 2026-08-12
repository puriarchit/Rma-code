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
    cursor = conn.cursor()

    conn_insert = pyodbc.connect(conn_str)
    insert_cursor = conn_insert.cursor()
    insert_cursor.fast_executemany = True

    step1_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[1/2] Resetting target table EntitySourceItem_New at %s...", step1_start)
    step_start = time.time()
    cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
    cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL)")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
    conn.commit()
    logging.info("[1/2] Target table reset completed in %.2f seconds.", time.time() - step_start)

    step2_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[2/2] Started merging SourceURI records into EntitySourceItem_New at %s...", step2_start)
    step_start = time.time()

    cursor.execute("""
        SELECT EntityGUID, SourceURI 
        FROM EntitySourceItem WITH (INDEX(0))
        ORDER BY EntityGUID
    """)

    current_guid = None
    current_uris = []
    batch_to_insert = []
    batch_size = 100000
    processed_count = 0

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
            
        for guid, uri in rows:
            if guid != current_guid:
                if current_guid is not None:
                    unique_uris = list(dict.fromkeys(current_uris))
                    merged_links = "; ".join(unique_uris)
                    batch_to_insert.append((current_guid, merged_links))
                    processed_count += 1
                    
                    if len(batch_to_insert) >= batch_size:
                        insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 0, 0)])
                        insert_cursor.executemany("""
                            INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
                            VALUES (?, ?)
                        """, batch_to_insert)
                        conn_insert.commit()
                        logging.info("  Merged %d entity profiles...", processed_count)
                        batch_to_insert = []
                
                current_guid = guid
                current_uris = [uri] if uri else [""]
            else:
                if uri:
                    current_uris.append(uri)
                else:
                    current_uris.append("")

    if current_guid is not None:
        unique_uris = list(dict.fromkeys(current_uris))
        merged_links = "; ".join(unique_uris)
        batch_to_insert.append((current_guid, merged_links))
        processed_count += 1

    if batch_to_insert:
        insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 0, 0)])
        insert_cursor.executemany("""
            INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
            VALUES (?, ?)
        """, batch_to_insert)
        conn_insert.commit()

    conn_insert.close()

    logging.info("[2/2] SourceURI records merged in %.2f seconds.", time.time() - step_start)

    try:
        logging.info("Reclaiming raw EntitySourceItem space...")
        cursor.execute("TRUNCATE TABLE EntitySourceItem")
        conn.commit()
    except Exception as ex:
        logging.warning("Could not truncate EntitySourceItem: %s", ex)

    final_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New").fetchone()[0]
    cursor.close()
    conn.close()

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 2 completed in %.2f minutes [Finished at %s] (Total Merged Profiles: %d) ===", elapsed_min, end_time_str, final_count)

if __name__ == "__main__":
    main()



