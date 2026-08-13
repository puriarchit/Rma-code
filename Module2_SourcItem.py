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

    # Open a separate independent connection for inserts to prevent "Connection is busy" conflicts
    conn_insert = pyodbc.connect(conn_str)
    insert_cursor = conn_insert.cursor()
    insert_cursor.fast_executemany = True

    step1_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[1/3] Recreating target table and dropping helper tables at %s...", step1_start)
    step_start = time.time()
    cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
    cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL)")

    cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
    conn.commit()
    logging.info("[1/3] Target table reset completed in %.2f seconds.", time.time() - step_start)

    logging.info("Ensuring Non-Clustered Index on source table (EntitySourceItem)...")
    step_start = time.time()
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sys.indexes 
            WHERE object_id = OBJECT_ID('EntitySourceItem') AND name = 'IX_EntitySourceItem_EntityGUID'
        )
        CREATE NONCLUSTERED INDEX IX_EntitySourceItem_EntityGUID ON EntitySourceItem(EntityGUID)
    """)
    conn.commit()
    logging.info("Non-Clustered Index verified in %.2f seconds.", time.time() - step_start)

    step2_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[2/3] Identifying & loading unique records (no duplicates) at %s...", step2_start)
    step_start = time.time()
    cursor.execute("IF OBJECT_ID('tempdb..#UniqGUIDs', 'U') IS NOT NULL DROP TABLE #UniqGUIDs")
    cursor.execute("CREATE TABLE #UniqGUIDs (EntityGUID NVARCHAR(50))")
    cursor.execute("""
        INSERT INTO #UniqGUIDs (EntityGUID)
        SELECT EntityGUID
        FROM EntitySourceItem WITH (INDEX(IX_EntitySourceItem_EntityGUID))
        GROUP BY EntityGUID
        HAVING COUNT(*) = 1
    """)
    conn.commit()
    uniq_count = cursor.execute("SELECT COUNT(*) FROM #UniqGUIDs").fetchone()[0]
    logging.info("Identified %d unique records.", uniq_count)

    cursor.execute("""
        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
        SELECT e.EntityGUID, e.SourceURI
        FROM EntitySourceItem e WITH (INDEX(IX_EntitySourceItem_EntityGUID))
        INNER JOIN #UniqGUIDs u ON e.EntityGUID = u.EntityGUID
    """)
    conn.commit()
    logging.info("[2/3] Loaded %d unique records directly to target in %.2f seconds.", uniq_count, time.time() - step_start)

    step3_start = datetime.now().strftime("%H:%M:%S")
    logging.info("[3/3] Streaming, merging, and loading duplicate records at %s...", step3_start)
    step_start = time.time()

    cursor.execute("""
        SELECT e.EntityGUID, e.SourceURI
        FROM EntitySourceItem e
        INNER JOIN (
            SELECT EntityGUID 
            FROM EntitySourceItem
            GROUP BY EntityGUID 
            HAVING COUNT(*) > 1
        ) d ON e.EntityGUID = d.EntityGUID
        ORDER BY e.EntityGUID
    """)

    current_guid = None
    current_uris = []
    batch_to_insert = []
    batch_size = 50000
    processed_groups = 0

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for guid, uri in rows:
            if guid != current_guid:
                if current_guid is not None:
                    # Merge current GUID's URIs
                    clean_uris = [u for u in current_uris if u and u.strip()]
                    if not clean_uris and current_uris:
                        clean_uris = [""]
                    merged_uri = "; ".join(sorted(list(set(clean_uris))))
                    batch_to_insert.append((current_guid, merged_uri))
                    processed_groups += 1

                    if processed_groups % 50000 == 0:
                        logging.info("   Loaded %d merged duplicate profiles...", processed_groups)

                    if len(batch_to_insert) >= batch_size:
                        insert_cursor.executemany("""
                            INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
                            VALUES (?, ?)
                        """, batch_to_insert)
                        conn_insert.commit()
                        batch_to_insert = []

                current_guid = guid
                current_uris = [uri] if uri else []
            else:
                if uri:
                    current_uris.append(uri)

    # Insert remaining last group
    if current_guid is not None:
        clean_uris = [u for u in current_uris if u and u.strip()]
        if not clean_uris and current_uris:
            clean_uris = [""]
        merged_uri = "; ".join(sorted(list(set(clean_uris))))
        batch_to_insert.append((current_guid, merged_uri))
        processed_groups += 1

    if batch_to_insert:
        insert_cursor.executemany("""
            INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
            VALUES (?, ?)
        """, batch_to_insert)
        conn_insert.commit()

    logging.info("[3/3] All %d duplicate profiles merged and loaded in %.2f seconds.", processed_groups, time.time() - step_start)

    # Verify final row count
    cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New WITH (NOLOCK)")
    final_count = cursor.fetchone()[0]

    # Reclaim raw space immediately
    try:
        cursor.execute("TRUNCATE TABLE EntitySourceItem")
        logging.info("Reclaimed raw space: truncated EntitySourceItem.")
    except Exception as e:
        logging.warning("Could not truncate EntitySourceItem: %s", e)

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 2 completed in %.2f minutes [Finished at %s] (Total Merged Profiles: %d) ===", elapsed_min, end_time_str, final_count)

    cursor.close()
    conn.close()
    insert_cursor.close()
    conn_insert.close()

if __name__ == "__main__":
    main()



