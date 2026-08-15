# -*- coding: utf-8 -*-
import json
import os
import pyodbc
import sys
import time
import logging
from collections import defaultdict

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
    logging.info("=== Starting Memory-Optimized Module 2: Merging duplicate web source links ===")

    config = load_config()
    db = config["database"]

    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    logging.info("[1/3] Resetting target table EntitySourceItem_New...")
    step_start = time.time()
    cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
    cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL) WITH (DATA_COMPRESSION = PAGE)")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
    cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
    conn.commit()
    logging.info("   Target table reset completed in %.2f seconds.", time.time() - step_start)

    logging.info("[2/3] Reading source links into memory...")
    step_start = time.time()
    cursor.execute("SELECT EntityGUID, SourceURI FROM EntitySourceItem WITH (NOLOCK)")

    groups = defaultdict(set)
    row_count = 0

    while True:
        rows = cursor.fetchmany(100000)
        if not rows:
            break
        for guid, uri in rows:
            if guid:
                if uri:
                    groups[guid].add(uri)
                else:
                    groups[guid].add("")
        row_count += len(rows)
        if row_count % 5000000 == 0:
            logging.info("   Read %s rows...", f"{row_count:,}")

    logging.info("   Loaded %s rows into %s unique profiles in %.2f seconds.", f"{row_count:,}", f"{len(groups):,}", time.time() - step_start)

    logging.info("[3/3] Inserting merged profiles into EntitySourceItem_New...")
    step_start = time.time()
    cursor.fast_executemany = True

    merged_data = []
    batch_size = 50000
    inserted_count = 0

    for guid, uris in groups.items():
        uris_list = list(uris)
        if len(uris_list) > 1 and "" in uris_list:
            uris_list.remove("")
        merged_links = "; ".join(uris_list)
        merged_data.append((guid, merged_links))
        
        if len(merged_data) >= batch_size:
            cursor.executemany("""
                INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
                VALUES (?, ?)
            """, merged_data)
            conn.commit()
            inserted_count += len(merged_data)
            logging.info("   Inserted %s profiles...", f"{inserted_count:,}")
            merged_data = []

    if merged_data:
        cursor.executemany("""
            INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
            VALUES (?, ?)
        """, merged_data)
        conn.commit()
        inserted_count += len(merged_data)
        logging.info("   Inserted %s profiles...", f"{inserted_count:,}")

    try:
        cursor.execute("TRUNCATE TABLE EntitySourceItem")
        conn.commit()
        logging.info("Reclaimed raw space: truncated EntitySourceItem.")
    except Exception as e:
        logging.warning("Could not truncate EntitySourceItem: %s", e)

    elapsed_min = (time.time() - global_start) / 60
    logging.info("=== Module 2 completed successfully in %.2f minutes (Total Merged Profiles: %s) ===", elapsed_min, f"{inserted_count:,}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
