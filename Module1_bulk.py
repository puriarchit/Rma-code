# -*- coding: utf-8 -*-
import json
import os
import pyodbc
import time
import argparse
import logging
import sys
from datetime import datetime

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    return parser.parse_args()

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

    try:
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")
        cursor.execute(f"ALTER DATABASE [{db['name']}] SET RECOVERY SIMPLE")
    except Exception:
        pass

    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 1: Bulk Ingestion (100%% FULL LOAD) [Started at %s] ===", start_time_str)
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

    try:
        for filename, tablename in files_list:
            filepath = os.path.join(paths["unzipped_folder"], filename)
            
            if os.path.exists(filepath):
                file_start = time.time()
                logging.info("Bulk Ingesting FULL: %s...", filename)
                
                try:
                    cursor.execute(f"TRUNCATE TABLE {tablename}")
                    
                    bulk_query = f"""
                        BULK INSERT {tablename}
                        FROM '{filepath}'
                        WITH (
                            FIELDTERMINATOR = '|',
                            ROWTERMINATOR = '0x0a',
                            FIRSTROW = 2,
                            CODEPAGE = '65001',
                            TABLOCK,
                            BATCHSIZE = 100000
                        );
                    """
                    cursor.execute(bulk_query)
                    
                    cursor.execute(f"SELECT COUNT(*) FROM {tablename}")
                    row_count = cursor.fetchone()[0]
                    
                    time_taken = time.time() - file_start
                    logging.info("  >> %s loaded (%d rows) in %.2f seconds.", tablename, row_count, time_taken)
                    
                except Exception as ex:
                    logging.error("Error loading %s: %s", filename, ex)
                    raise ex
            else:
                logging.warning("File not found, skipping: %s", filename)

    except KeyboardInterrupt:
        logging.warning("Execution interrupted by user (Ctrl+C). Releasing database transaction locks...")
        try:
            cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;")
        except Exception:
            pass
        logging.info("Database transaction locks released instantly. Safe to run again.")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

    elapsed_min = (time.time() - global_start) / 60
    logging.info("=== Module 1 (100%% FULL LOAD) completed in %.2f minutes! ===", elapsed_min)

if __name__ == "__main__":
    main()



