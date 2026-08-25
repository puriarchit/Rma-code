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

def reset_raw_tables_schema(cursor):
    logging.info("[0/16] Resetting, purging production objects & recreating clean raw staging tables...")
    
    # 1. Drop production target tables & views first to instantly reclaim disk space
    prod_cleanup_sql = """
    DROP VIEW IF EXISTS dbo.NegativeList_Master;
    DROP VIEW IF EXISTS dbo.NegativeListFilter;
    DROP TABLE IF EXISTS dbo.NegativeList;
    DROP TABLE IF EXISTS dbo.NegativeList_New1;
    DROP TABLE IF EXISTS dbo.NegativeList_History_Summary;
    DROP SEQUENCE IF EXISTS dbo.NegativeListVersionSeq;
    """
    for stmt in prod_cleanup_sql.split(";"):
        if stmt.strip():
            cursor.execute(stmt)
    logging.info("[0/16] Production target tables, views & sequences dropped (Disk space reclaimed).")

    # 2. Drop and recreate all 16 raw staging tables freshly from exact DDL script
    raw_ddl_sql = """
    DROP TABLE IF EXISTS AssociatedEntity;
    CREATE TABLE AssociatedEntity (EntityGUID NVARCHAR(50), AssociatedEntityGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), LastUpdated DATETIME, SourceName NVARCHAR(500));

    DROP TABLE IF EXISTS ConsolidatedSanction;
    CREATE TABLE ConsolidatedSanction (ConsolidatedSanctionGUID NVARCHAR(50), EntityGUID NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS Entity;
    CREATE TABLE Entity (EntityGUID NVARCHAR(50), EntityTypeDesc NVARCHAR(50), Gender NVARCHAR(50), Name NVARCHAR(500), FirstName NVARCHAR(200), MiddleName NVARCHAR(200), LastName NVARCHAR(500), Prefix NVARCHAR(100), Suffix NVARCHAR(50), Title NVARCHAR(500), IsDeceased NVARCHAR(10), DeceasedYear NVARCHAR(10), DeceasedMonth NVARCHAR(10), DeceasedDay NVARCHAR(10), IsRelatedEntity NVARCHAR(10), EntityID NVARCHAR(50), LookupID NVARCHAR(50), LastUpdated DATETIME, AssociatedPhoto NVARCHAR(10));

    DROP TABLE IF EXISTS EntityAddress;
    CREATE TABLE EntityAddress (EntityGUID NVARCHAR(50), EntityAddressGUID NVARCHAR(50), AddressTypeDesc NVARCHAR(100), Address1 NVARCHAR(500), Address2 NVARCHAR(500), City NVARCHAR(200), StateProvinceRegion NVARCHAR(200), PostalCode NVARCHAR(50), Country NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityAdverseMedia;
    CREATE TABLE EntityAdverseMedia (EntityGUID NVARCHAR(50), EntityAdverseMediaGUID NVARCHAR(50), AdverseMediaDesc NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityAdverseMediaSubCategory;
    CREATE TABLE EntityAdverseMediaSubCategory (EntityAdverseMediaGUID NVARCHAR(50), EntityAdverseMediaSubCategoryGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityAlias;
    CREATE TABLE EntityAlias (EntityGUID NVARCHAR(50), EntityAliasGUID NVARCHAR(50), AliasTypeDesc NVARCHAR(100), EnglishDescription NVARCHAR(100), Name NVARCHAR(500), FirstName NVARCHAR(200), MiddleName NVARCHAR(200), LastName NVARCHAR(500), Prefix NVARCHAR(100), Suffix NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityCountryAssociation;
    CREATE TABLE EntityCountryAssociation (EntityGUID NVARCHAR(50), EntityCountryAssociationGUID NVARCHAR(50), AssociationTypeDesc NVARCHAR(100), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), OwnershipPercentageCalc NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityDeletes;
    CREATE TABLE EntityDeletes (EntityGUID NVARCHAR(50), DateDeleted DATETIME);

    DROP TABLE IF EXISTS EntityDOB;
    CREATE TABLE EntityDOB (EntityGUID NVARCHAR(50), EntityDOBGUID NVARCHAR(50), BirthYear NVARCHAR(10), BirthMonth NVARCHAR(10), BirthDay NVARCHAR(10), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityEnforcement;
    CREATE TABLE EntityEnforcement (EntityGUID NVARCHAR(50), EntityEnforcementGUID NVARCHAR(50), EnforcementDesc NVARCHAR(50), SourceName NVARCHAR(500), SourceNameAbbrev NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityEnforcementSubCategory;
    CREATE TABLE EntityEnforcementSubCategory (EntityEnforcementGUID NVARCHAR(50), EntityEnforcementSubCategoryGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityIdentification;
    CREATE TABLE EntityIdentification (EntityGUID NVARCHAR(50), EntityIdentificationGUID NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), IdentificationIssuer NVARCHAR(500), IdentificationTypeDesc NVARCHAR(200), IdentificationNumber NVARCHAR(200), IssueYear NVARCHAR(10), IssueMonth NVARCHAR(10), IssueDay NVARCHAR(10), ExpirationYear NVARCHAR(10), ExpirationMonth NVARCHAR(10), ExpirationDay NVARCHAR(10), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntityRemark;
    CREATE TABLE EntityRemark (EntityGUID NVARCHAR(50), EntityRemarkGUID NVARCHAR(50), Remark NVARCHAR(MAX), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntitySanction;
    CREATE TABLE EntitySanction (EntityGUID NVARCHAR(50), EntitySanctionGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), ConsolidatedSanctionGUID NVARCHAR(50), SourceName NVARCHAR(500), SourceNameAbbrev NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);

    DROP TABLE IF EXISTS EntitySourceItem;
    CREATE TABLE EntitySourceItem (EntityGUID NVARCHAR(50), EntitySourceItemGUID NVARCHAR(50), SourceURI NVARCHAR(MAX), LastUpdated DATETIME);
    """
    for stmt in raw_ddl_sql.split(";"):
        if stmt.strip():
            cursor.execute(stmt)
    logging.info("[0/16] All 16 raw staging tables freshly dropped and recreated.")

def main():
    args = parse_args()
    setup_logging()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    db = config["database"]
    paths = config["paths"]

    trusted = "yes" if db["trusted_connection"] else "no"
    
    # 1. Connect to master first to ensure database exists
    for svr in [db["server"], ".", "localhost", "(local)"]:
        try:
            conn_m = pyodbc.connect(f"DRIVER={{{db['driver']}}};SERVER={svr};DATABASE=master;Trusted_Connection={trusted};", autocommit=True, timeout=2)
            cursor_m = conn_m.cursor()
            cursor_m.execute(f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{db['name']}') CREATE DATABASE [{db['name']}];")
            conn_m.close()
            break
        except Exception:
            continue

    # 2. Connect to database
    conn = None
    for svr in [db["server"], ".", "localhost", "(local)"]:
        try:
            conn_str = f"DRIVER={{{db['driver']}}};SERVER={svr};DATABASE={db['name']};Trusted_Connection={trusted};"
            conn = pyodbc.connect(conn_str, autocommit=True, timeout=2)
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

    # Drop and recreate all raw + production tables freshly at the start of Module 1
    reset_raw_tables_schema(cursor)

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
                    cursor.execute(f"""
                        DECLARE @sql NVARCHAR(MAX) = '';
                        SELECT @sql += 'DROP INDEX ' + QUOTENAME(i.name) + ' ON ' + QUOTENAME(SCHEMA_NAME(t.schema_id)) + '.' + QUOTENAME(t.name) + ';'
                        FROM sys.indexes i
                        INNER JOIN sys.tables t ON i.object_id = t.object_id
                        WHERE t.name = '{tablename}' AND i.type > 0 AND i.is_primary_key = 0;
                        IF @sql <> '' EXEC sp_executesql @sql;
                    """)
                    
                    cursor.execute(f"TRUNCATE TABLE [{tablename}]")
                    
                    bulk_query = f"""
                        BULK INSERT [{tablename}]
                        FROM '{filepath}'
                        WITH (
                            FIELDTERMINATOR = '|',
                            ROWTERMINATOR = '0x0a',
                            FIRSTROW = 2,
                            CODEPAGE = '1252',
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
