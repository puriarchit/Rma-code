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
    
    # Try server fallback (db['server'], '.', 'localhost')
    conn = None
    for svr in [db["server"], ".", "localhost"]:
        try:
            conn_str = f"DRIVER={{{db['driver']}}};SERVER={svr};DATABASE={db['name']};Trusted_Connection={trusted};"
            conn = pyodbc.connect(conn_str, autocommit=True, timeout=5)
            break
        except Exception:
            continue

    if not conn:
        raise Exception("Could not connect to SQL Server on any server name.")

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
                logging.info("[%d/%d] Ingesting %s into %s...", idx, total_files, filename, tablename)
                
                try:
                    # Verify/Ensure exact column schema matching user script
                    cursor.execute(f"""
                        IF OBJECT_ID('{tablename}', 'U') IS NOT NULL AND '{tablename}' = 'EntityCountryAssociation'
                        BEGIN
                            IF (SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID('{tablename}')) < 7
                                DROP TABLE dbo.[EntityCountryAssociation];
                        END

                        IF OBJECT_ID('{tablename}', 'U') IS NULL
                        BEGIN
                            IF '{tablename}' = 'EntityCountryAssociation'
                                CREATE TABLE dbo.EntityCountryAssociation (EntityGUID NVARCHAR(50), EntityCountryAssociationGUID NVARCHAR(50), AssociationTypeDesc NVARCHAR(100), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), OwnershipPercentageCalc NVARCHAR(50), LastUpdated DATETIME);
                            ELSE IF '{tablename}' = 'EntityEnforcement'
                                CREATE TABLE dbo.EntityEnforcement (EntityGUID NVARCHAR(50), EntityEnforcementGUID NVARCHAR(50), EnforcementDesc NVARCHAR(50), SourceName NVARCHAR(500), SourceNameAbbrev NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);
                            ELSE IF '{tablename}' = 'EntitySanction'
                                CREATE TABLE dbo.EntitySanction (EntityGUID NVARCHAR(50), EntitySanctionGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), ConsolidatedSanctionGUID NVARCHAR(50), SourceName NVARCHAR(500), SourceNameAbbrev NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);
                        END
                    """)

                    cursor.execute(f"""
                        DECLARE @sql NVARCHAR(MAX) = '';
                        SELECT @sql += 'DROP INDEX ' + QUOTENAME(i.name) + ' ON ' + QUOTENAME(SCHEMA_NAME(t.schema_id)) + '.' + QUOTENAME(t.name) + ';'
                        FROM sys.indexes i
                        INNER JOIN sys.tables t ON i.object_id = t.object_id
                        WHERE t.name = '{tablename}' AND i.type > 0 AND i.is_primary_key = 0;
                        IF @sql <> '' EXEC sp_executesql @sql;
                    """)
                    
                    cursor.execute(f"IF OBJECT_ID('{tablename}', 'U') IS NOT NULL TRUNCATE TABLE [{tablename}]")
                    
                    bulk_query = f"""
                        BULK INSERT [{tablename}]
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
                    
                    cursor.execute(f"SELECT COUNT(*) FROM [{tablename}]")
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


