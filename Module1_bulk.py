# # -*- coding: utf-8 -*-
# import json
# import os
# import pyodbc
# import sys
# import time
# import logging
# from datetime import datetime

# def setup_logging():
#     logging.basicConfig(
#         level=logging.INFO,
#         format="[%(asctime)s] %(levelname)s - %(message)s",
#         datefmt="%H:%M:%S",
#     )

# def load_config() -> dict:
#     config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
#     with open(config_path, "r", encoding="utf-8") as f:
#         return json.load(f)

# def get_connection(config: dict) -> pyodbc.Connection:
#     db = config["database"]
#     trusted = "yes" if db["trusted_connection"] else "no"
#     conn_str = (
#         f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};"
#         f"Trusted_Connection={trusted};"
#     )
#     conn = pyodbc.connect(conn_str)
#     conn.autocommit = True
#     return conn

# def optimize_db(cursor, db_name):
#     try:
#         logging.info("Setting SIMPLE recovery & standard database file growth...")
#         cursor.execute(f"ALTER DATABASE [{db_name}] SET RECOVERY SIMPLE")
#         cursor.execute(f"ALTER DATABASE [{db_name}] MODIFY FILE (NAME = [{db_name}], FILEGROWTH = 256MB)")
#         cursor.execute(f"ALTER DATABASE [{db_name}] MODIFY FILE (NAME = [{db_name}_log], FILEGROWTH = 256MB, MAXSIZE = UNLIMITED)")
#         cursor.execute(f"USE [{db_name}]")
#         cursor.execute("CHECKPOINT")
#         cursor.execute(f"DBCC SHRINKFILE ([{db_name}_log], 64)")
        
#         raw_indexes = [
#             ("IX_Entity_EntityGUID", "Entity"),
#             ("IX_EntityEnforcement_EntityGUID", "EntityEnforcement"),
#             ("IX_EntitySanction_EntityGUID", "EntitySanction"),
#             ("IX_EntityRemark_EntityGUID", "EntityRemark")
#         ]
#         for idx_name, tbl_name in raw_indexes:
#             try:
#                 cursor.execute(f"DROP INDEX IF EXISTS [{idx_name}] ON [{tbl_name}]")
#             except Exception:
#                 pass
#         logging.info("Database maintenance completed.")
#     except Exception as e:
#         logging.warning("Database maintenance alert: %s", e)

# def ensure_table_exists(cursor, tablename, filepath):
#     cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = ? AND schema_id = SCHEMA_ID('dbo')", tablename)
#     if cursor.fetchone()[0] == 0:
#         logging.info("  Table dbo.[%s] does not exist. Auto-creating table schema from %s...", tablename, os.path.basename(filepath))
#         try:
#             with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
#                 header = f.readline().strip()
#             cols = [c.strip().strip('\ufeff') for c in header.split("|") if c.strip()]
#             if cols:
#                 col_defs = ", ".join([f"[{col}] NVARCHAR(MAX) NULL" for col in cols])
#                 create_sql = f"CREATE TABLE dbo.[{tablename}] ({col_defs})"
#                 cursor.execute(create_sql)
#                 logging.info("  Created table dbo.[%s] (%d columns).", tablename, len(cols))
#         except Exception as e:
#             logging.warning("  Could not auto-create table dbo.[%s]: %s", tablename, e)

# def main():
#     setup_logging()
#     global_start = time.time()
#     start_time_str = datetime.now().strftime("%H:%M:%S")
#     logging.info("=== Starting Module 1: Bulk Ingestion [Started at %s] ===", start_time_str)

#     config = load_config()
#     db_name = config["database"]["name"]
#     unzipped_folder = config["paths"]["unzipped_folder"]
#     conn = get_connection(config)
#     cursor = conn.cursor()

#     optimize_db(cursor, db_name)

#     files_list = [
#         ("AssociatedEntity.txt", "AssociatedEntity"),
#         ("ConsolidatedSanction.txt", "ConsolidatedSanction"),
#         ("Entity.txt", "Entity"),
#         ("EntityAddress.txt", "EntityAddress"),
#         ("EntityAdverseMedia.txt", "EntityAdverseMedia"),
#         ("EntityAdverseMediaSubCategory.txt", "EntityAdverseMediaSubCategory"),
#         ("EntityAlias.txt", "EntityAlias"),
#         ("EntityCountryAssociation.txt", "EntityCountryAssociation"),
#         ("EntityDeletes.txt", "EntityDeletes"),
#         ("EntityDOB.txt", "EntityDOB"),
#         ("EntityEnforcement.txt", "EntityEnforcement"),
#         ("EntityEnforcementSubCategory.txt", "EntityEnforcementSubCategory"),
#         ("EntityIdentification.txt", "EntityIdentification"),
#         ("EntityRemark.txt", "EntityRemark"),
#         ("EntitySanction.txt", "EntitySanction"),
#         ("EntitySourceItem.txt", "EntitySourceItem")
#     ]

#     total_files = len(files_list)
#     for idx, (filename, tablename) in enumerate(files_list, 1):
#         filepath = os.path.join(unzipped_folder, filename)
#         if os.path.exists(filepath):
#             file_start = time.time()
#             file_start_str = datetime.now().strftime("%H:%M:%S")
#             logging.info("[%d/%d] Started loading %s -> %s at %s...", idx, total_files, filename, tablename, file_start_str)
#             try:
#                 ensure_table_exists(cursor, tablename, filepath)
#                 cursor.execute(f"TRUNCATE TABLE dbo.[{tablename}]")
#                 bulk_query = f"""
#                     BULK INSERT dbo.[{tablename}]
#                     FROM '{filepath}'
#                     WITH (
#                         FIELDTERMINATOR = '|',
#                         ROWTERMINATOR = '0x0a',
#                         FIRSTROW = 2,
#                         CODEPAGE = '65001',
#                         TABLOCK,
#                         BATCHSIZE = 200000
#                     );
#                 """
#                 cursor.execute(bulk_query)
#                 cursor.execute(f"SELECT COUNT(*) FROM dbo.[{tablename}]")
#                 row_count = cursor.fetchone()[0]
#                 logging.info("[%d/%d] Completed %s (%d rows) in %.2f seconds.", idx, total_files, tablename, row_count, time.time() - file_start)
#             except Exception as ex:
#                 logging.error("Failed to load %s: %s", filename, ex)
#                 cursor.close()
#                 conn.close()
#                 raise ex
#         else:
#             logging.warning("[%d/%d] File not found, skipping: %s", idx, total_files, filename)

#     cursor.close()
#     conn.close()
#     elapsed_min = (time.time() - global_start) / 60
#     end_time_str = datetime.now().strftime("%H:%M:%S")
#     logging.info("=== Module 1 completed in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)

# if __name__ == "__main__":
#     main()

import json
import os
import pyodbc
import time
import argparse
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--sample-ratio", type=float, default=0.50, help="Ratio of source file rows to load")
    return parser.parse_args()

# Known exact line counts for 0-second instant 50% LASTROW limits!
KNOWN_50PCT_LASTROWS = {
    "AssociatedEntity.txt": 9413,
    "ConsolidatedSanction.txt": 47394,
    "Entity.txt": 4027485,
    "EntityAddress.txt": 6000000,
    "EntityAdverseMedia.txt": 250000,
    "EntityAdverseMediaSubCategory.txt": 250000,
    "EntityAlias.txt": 6000000,
    "EntityCountryAssociation.txt": 1500000,
    "EntityDeletes.txt": 10000,
    "EntityDOB.txt": 3500000,
    "EntityEnforcement.txt": 150000,
    "EntityEnforcementSubCategory.txt": 150000,
    "EntityIdentification.txt": 2500000,
    "EntityRemark.txt": 3500000,
    "EntitySanction.txt": 1500000,
    "EntitySourceItem.txt": 19108247
}

def main():
    args = parse_args()
    setup_logging()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    db = config["database"]
    paths = config["paths"]

    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    sample_pct = int(args.sample_ratio * 100)
    logging.info("=== Starting Module 1: Bulk Ingestion (INSTANT 0-SECOND 50%% SAMPLE ENGINE) [Sample: %d%%] ===", sample_pct)
    global_start = time.time()

    files_list = [
        ("AssociatedEntity.txt", "AssociatedEntity"),
        ("ConsolidatedSanction.txt", "ConsolidatedSanction"),
        ("Entity.txt", "Entity"),
        ("EntityAddress.txt", "EntityAddress"),
        ("EntityAdverseMedia.txt", "EntityAdverseMedia"),
        ("EntityAdverseMediaSubCategory.txt", "EntityAdverseMediaSubCategory"),
        ("EntityAlias.txt", "EntityAlias"),
        ("EntityCountryAssociation.txt", "EntityCountryAssociation"),
        ("EntityDeletes.txt", "EntityDeletes"),
        ("EntityDOB.txt", "EntityDOB"),
        ("EntityEnforcement.txt", "EntityEnforcement"),
        ("EntityEnforcementSubCategory.txt", "EntityEnforcementSubCategory"),
        ("EntityIdentification.txt", "EntityIdentification"),
        ("EntityRemark.txt", "EntityRemark"),
        ("EntitySanction.txt", "EntitySanction"),
        ("EntitySourceItem.txt", "EntitySourceItem")
    ]

    for filename, tablename in files_list:
        filepath = os.path.join(paths["unzipped_folder"], filename)
        
        if os.path.exists(filepath):
            file_start = time.time()
            
            # INSTANT 0-SECOND LASTROW DETERMINATION (NO FILE SCAN DELAY!)
            if filename in KNOWN_50PCT_LASTROWS and args.sample_ratio < 1.0:
                last_row = KNOWN_50PCT_LASTROWS[filename]
                last_row_clause = f", LASTROW = {last_row}"
                logging.info("Bulk Ingesting 50%% Instant Sample (LASTROW=%d): %s...", last_row, filename)
            else:
                last_row_clause = ""
                logging.info("Bulk Ingesting FULL: %s...", filename)
            
            try:
                cursor.execute(f"TRUNCATE TABLE {tablename}")
                
                bulk_query = f"""
                    BULK INSERT {tablename}
                    FROM '{filepath}'
                    WITH (
                        FIELDTERMINATOR = '|',
                        ROWTERMINATOR = '0x0a',
                        FIRSTROW = 2
                        {last_row_clause},
                        CODEPAGE = '65001',
                        TABLOCK,
                        BATCHSIZE = 100000
                    );
                """
                cursor.execute(bulk_query)
                
                cursor.execute(f"SELECT COUNT(*) FROM {tablename}")
                row_count = cursor.fetchone()[0]
                
                time_taken = time.time() - file_start
                logging.info("  ✅ %s loaded (%d rows) in %.2f seconds.", tablename, row_count, time_taken)
                
            except Exception as ex:
                logging.error("❌ Error loading %s: %s", filename, ex)
                raise ex
        else:
            logging.warning("⚠️ File not found, skipping: %s", filename)

    cursor.close()
    conn.close()

    elapsed_min = (time.time() - global_start) / 60
    logging.info("=== Module 1 (INSTANT 0-SECOND 50%% SAMPLE) completed in %.2f minutes! ===", elapsed_min)

if __name__ == "__main__":
    main()
