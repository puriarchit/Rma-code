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
    parser.add_argument("--sample-ratio", type=float, default=1.0, help="Ratio of source file rows to load")
    return parser.parse_args()

def free_disk_space(cursor):
    logging.info("Purging production objects to clear space...")
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
    logging.info("Production tables purged successfully.")

def ensure_staging_tables_exist(cursor):
    logging.info("Checking staging tables structure...")
    ddl_sqls = [
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AssociatedEntity]') AND type in (N'U')) CREATE TABLE AssociatedEntity (EntityGUID NVARCHAR(50), AssociatedEntityGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), LastUpdated DATETIME, SourceName NVARCHAR(500));",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[ConsolidatedSanction]') AND type in (N'U')) CREATE TABLE ConsolidatedSanction (ConsolidatedSanctionGUID NVARCHAR(50), EntityGUID NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Entity]') AND type in (N'U')) CREATE TABLE Entity (EntityGUID NVARCHAR(50), EntityTypeDesc NVARCHAR(50), Gender NVARCHAR(50), Name NVARCHAR(500), FirstName NVARCHAR(200), MiddleName NVARCHAR(200), LastName NVARCHAR(500), Prefix NVARCHAR(100), Suffix NVARCHAR(50), Title NVARCHAR(500), IsDeceased NVARCHAR(10), DeceasedYear NVARCHAR(10), DeceasedMonth NVARCHAR(10), DeceasedDay NVARCHAR(10), IsRelatedEntity NVARCHAR(10), EntityID NVARCHAR(50), LookupID NVARCHAR(50), LastUpdated DATETIME, AssociatedPhoto NVARCHAR(10));",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityAddress]') AND type in (N'U')) CREATE TABLE EntityAddress (EntityGUID NVARCHAR(50), EntityAddressGUID NVARCHAR(50), AddressTypeDesc NVARCHAR(100), Address1 NVARCHAR(500), Address2 NVARCHAR(500), City NVARCHAR(200), StateProvinceRegion NVARCHAR(200), PostalCode NVARCHAR(50), Country NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityAdverseMedia]') AND type in (N'U')) CREATE TABLE EntityAdverseMedia (EntityGUID NVARCHAR(50), EntityAdverseMediaGUID NVARCHAR(50), AdverseMediaDesc NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityAdverseMediaSubCategory]') AND type in (N'U')) CREATE TABLE EntityAdverseMediaSubCategory (EntityAdverseMediaGUID NVARCHAR(50), EntityAdverseMediaSubCategoryGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityAlias]') AND type in (N'U')) CREATE TABLE EntityAlias (EntityGUID NVARCHAR(50), EntityAliasGUID NVARCHAR(50), AliasTypeDesc NVARCHAR(100), EnglishDescription NVARCHAR(100), Name NVARCHAR(500), FirstName NVARCHAR(200), MiddleName NVARCHAR(200), LastName NVARCHAR(500), Prefix NVARCHAR(100), Suffix NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityCountryAssociation]') AND type in (N'U')) CREATE TABLE EntityCountryAssociation (EntityGUID NVARCHAR(50), EntityCountryAssociationGUID NVARCHAR(50), AssociationTypeDesc NVARCHAR(100), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), OwnershipPercentageCalc NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityDeletes]') AND type in (N'U')) CREATE TABLE EntityDeletes (EntityGUID NVARCHAR(50), DateDeleted DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityDOB]') AND type in (N'U')) CREATE TABLE EntityDOB (EntityGUID NVARCHAR(50), EntityDOBGUID NVARCHAR(50), BirthYear NVARCHAR(10), BirthMonth NVARCHAR(10), BirthDay NVARCHAR(10), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityEnforcement]') AND type in (N'U')) CREATE TABLE EntityEnforcement (EntityGUID NVARCHAR(50), EntityEnforcementGUID NVARCHAR(50), EnforcementDesc NVARCHAR(50), SourceName NVARCHAR(500), SourceNameAbbrev NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityEnforcementSubCategory]') AND type in (N'U')) CREATE TABLE EntityEnforcementSubCategory (EntityEnforcementGUID NVARCHAR(50), EntityEnforcementSubCategoryGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityIdentification]') AND type in (N'U')) CREATE TABLE EntityIdentification (EntityGUID NVARCHAR(50), EntityIdentificationGUID NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), IdentificationIssuer NVARCHAR(500), IdentificationTypeDesc NVARCHAR(200), IdentificationNumber NVARCHAR(200), IssueYear NVARCHAR(10), IssueMonth NVARCHAR(10), IssueDay NVARCHAR(10), ExpirationYear NVARCHAR(10), ExpirationMonth NVARCHAR(10), ExpirationDay NVARCHAR(10), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntityRemark]') AND type in (N'U')) CREATE TABLE EntityRemark (EntityGUID NVARCHAR(50), EntityRemarkGUID NVARCHAR(50), Remark NVARCHAR(MAX), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntitySanction]') AND type in (N'U')) CREATE TABLE EntitySanction (EntityGUID NVARCHAR(50), EntitySanctionGUID NVARCHAR(50), SubCategoryLabel NVARCHAR(100), ConsolidatedSanctionGUID NVARCHAR(50), SourceName NVARCHAR(500), SourceNameAbbrev NVARCHAR(50), AdministrativeUnitName NVARCHAR(200), ISOStandard NVARCHAR(50), LastUpdated DATETIME);",
        "IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EntitySourceItem]') AND type in (N'U')) CREATE TABLE EntitySourceItem (EntityGUID NVARCHAR(50), EntitySourceItemGUID NVARCHAR(50), SourceURI NVARCHAR(MAX), LastUpdated DATETIME);"
    ]
    for ddl in ddl_sqls:
        cursor.execute(ddl)
    logging.info("Staging tables checked successfully.")

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

    free_disk_space(cursor)
    ensure_staging_tables_exist(cursor)

    sample_pct = int(args.sample_ratio * 100)
    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 1: Bulk Ingestion (100%% Full Load Mode) [Started at %s] ===", start_time_str)
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
                logging.info("Bulk Ingesting: %s...", filename)
                
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
                            FIRSTROW = 2,
                            CODEPAGE = '65001',
                            TABLOCK,
                            BATCHSIZE = 100000
                        );
                    """
                    cursor.execute(bulk_query)
                    
                    cursor.execute(f"SELECT SUM(rows) FROM sys.partitions WHERE object_id = OBJECT_ID('dbo.{tablename}') AND index_id IN (0, 1)")
                    row_count = cursor.fetchone()[0] or 0
                    
                    time_taken = time.time() - file_start
                    logging.info("Success: %s loaded (%d rows) in %.2f seconds.", tablename, row_count, time_taken)
                    
                except Exception as ex:
                    logging.error("Error loading %s: %s", filename, ex)
                    raise ex
            else:
                logging.warning("File not found, skipping: %s", filename)

    except KeyboardInterrupt:
        logging.warning("Execution interrupted by user. Releasing transaction locks...")
        try:
            cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;")
        except Exception:
            pass
        logging.info("Database transaction locks released instantly.")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

    elapsed_min = (time.time() - global_start) / 60
    logging.info("=== Module 1 (100%% Full Load Mode) completed in %.2f minutes! ===", elapsed_min)

if __name__ == "__main__":
    main()
