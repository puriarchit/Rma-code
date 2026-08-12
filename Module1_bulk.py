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
    conn_str = (
        f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};"
        f"Trusted_Connection={trusted};"
    )
    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    return conn

def optimize_db(cursor, db_name):
    try:
        logging.info("Setting database recovery model to SIMPLE & shrinking log...")
        cursor.execute(f"ALTER DATABASE [{db_name}] SET RECOVERY SIMPLE")
        cursor.execute(f"ALTER DATABASE [{db_name}] MODIFY FILE (NAME = [{db_name}], FILEGROWTH = 512MB)")
        cursor.execute(f"ALTER DATABASE [{db_name}] MODIFY FILE (NAME = [{db_name}_log], FILEGROWTH = 512MB, MAXSIZE = UNLIMITED)")
        cursor.execute(f"USE [{db_name}]")
        cursor.execute("CHECKPOINT")
        cursor.execute(f"DBCC SHRINKFILE ([{db_name}_log], 64)")
        
        raw_indexes = [
            ("IX_Entity_EntityGUID", "Entity"),
            ("IX_EntityEnforcement_EntityGUID", "EntityEnforcement"),
            ("IX_EntitySanction_EntityGUID", "EntitySanction"),
            ("IX_EntityRemark_EntityGUID", "EntityRemark")
        ]
        for idx_name, tbl_name in raw_indexes:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS [{idx_name}] ON [{tbl_name}]")
            except Exception:
                pass
        logging.info("Database maintenance completed.")
    except Exception as e:
        logging.warning("Database maintenance alert: %s", e)

def main():
    setup_logging()
    global_start = time.time()
    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 1: Bulk Ingestion [Started at %s] ===", start_time_str)

    config = load_config()
    db_name = config["database"]["name"]
    unzipped_folder = config["paths"]["unzipped_folder"]
    conn = get_connection(config)
    cursor = conn.cursor()

    optimize_db(cursor, db_name)

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

    total_files = len(files_list)
    for idx, (filename, tablename) in enumerate(files_list, 1):
        filepath = os.path.join(unzipped_folder, filename)
        if os.path.exists(filepath):
            file_start = time.time()
            file_start_str = datetime.now().strftime("%H:%M:%S")
            logging.info("[%d/%d] Started loading %s -> %s at %s...", idx, total_files, filename, tablename, file_start_str)
            try:
                cursor.execute(f"TRUNCATE TABLE [{tablename}]")
                bulk_query = f"""
                    BULK INSERT [{tablename}]
                    FROM '{filepath}'
                    WITH (
                        FIELDTERMINATOR = '|',
                        ROWTERMINATOR = '0x0a',
                        FIRSTROW = 2,
                        CODEPAGE = '65001',
                        TABLOCK,
                        BATCHSIZE = 200000
                    );
                """
                cursor.execute(bulk_query)
                cursor.execute(f"SELECT COUNT(*) FROM [{tablename}]")
                row_count = cursor.fetchone()[0]
                logging.info("[%d/%d] Completed %s (%d rows) in %.2f seconds.", idx, total_files, tablename, row_count, time.time() - file_start)
            except Exception as ex:
                logging.error("Failed to load %s: %s", filename, ex)
                cursor.close()
                conn.close()
                raise ex
        else:
            logging.warning("[%d/%d] File not found, skipping: %s", idx, total_files, filename)

    cursor.close()
    conn.close()
    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 1 completed in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)

if __name__ == "__main__":
    main()

