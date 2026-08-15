# -*- coding: utf-8 -*-
import json
import os
import pyodbc
import sys
import time
import argparse
import logging
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
    parser.add_argument("--sample-ratio", type=float, default=1.00, help="Ratio of source file rows to load (default: 1.00 for 100%% Full Dataset)")
    return parser.parse_args()

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

    try:
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")
        cursor.execute(f"ALTER DATABASE [{db['name']}] SET RECOVERY SIMPLE")
    except Exception:
        pass

    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 1: Bulk Ingestion [Started at %s] ===", start_time_str)
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

    total_files = len(files_list)
    try:
        for idx, (filename, tablename) in enumerate(files_list, 1):
            filepath = os.path.join(paths["unzipped_folder"], filename)
            
            if os.path.exists(filepath):
                file_start = time.time()
                
                if filename in KNOWN_50PCT_LASTROWS and args.sample_ratio < 1.0:
                    last_row = KNOWN_50PCT_LASTROWS[filename]
                    last_row_clause = f", LASTROW = {last_row}"
                    logging.info("[%d/%d] Ingesting %s into %s...", idx, total_files, filename, tablename)
                else:
                    last_row_clause = ""
                    logging.info("[%d/%d] Ingesting %s into %s...", idx, total_files, filename, tablename)
                
                try:
                    cursor.execute(f"""
                        DECLARE @sql NVARCHAR(MAX) = '';
                        SELECT @sql += 'DROP INDEX ' + QUOTENAME(i.name) + ' ON ' + QUOTENAME(SCHEMA_NAME(t.schema_id)) + '.' + QUOTENAME(t.name) + ';'
                        FROM sys.indexes i
                        INNER JOIN sys.tables t ON i.object_id = t.object_id
                        WHERE t.name = '{tablename}' AND i.type > 0 AND i.is_primary_key = 0;
                        IF @sql <> '' EXEC sp_executesql @sql;
                    """)
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
                    logging.info("[%d/%d] Table %s loaded (%s rows) in %.2f seconds.", idx, total_files, tablename, f"{row_count:,}", time_taken)
                    
                except Exception as ex:
                    logging.error("Error loading %s: %s", filename, ex)
                    raise ex
            else:
                logging.warning("[%d/%d] File not found, skipping: %s", idx, total_files, filename)

    except KeyboardInterrupt:
        logging.warning("Execution interrupted by user. Releasing database transaction locks...")
        try:
            cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;")
        except Exception:
            pass
        logging.info("Database transaction locks released.")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 1: Bulk Ingestion completed successfully in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)

if __name__ == "__main__":
    main()

