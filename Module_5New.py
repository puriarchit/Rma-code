# -*- coding: utf-8 -*-
import json
import os
import pyodbc
import sys
import time
import logging
import argparse
from datetime import datetime

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--mode", default="first", choices=["first", "inc"])
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()

def load_config(config_path: str) -> dict:
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_connection(config: dict) -> pyodbc.Connection:
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = (
        f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};"
        f"Trusted_Connection={trusted};"
    )
    return pyodbc.connect(conn_str, autocommit=True)

def set_recovery_model(config: dict, model: str = "SIMPLE"):
    db = config["database"]
    try:
        conn = get_connection(config)
        cur = conn.cursor()
        cur.execute(f"ALTER DATABASE [{db['name']}] SET RECOVERY {model};")
        cur.close()
        conn.close()
    except Exception as e:
        logging.warning("Note setting database recovery model: %s", e)

def get_target_version_id(cursor, mode: str) -> int:
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList' AND schema_id = SCHEMA_ID('dbo')")
    if cursor.fetchone()[0] == 0:
        return 1

    cursor.execute("SELECT MAX(ISNULL(VersionID, 0)) FROM dbo.NegativeList WITH (NOLOCK)")
    max_ver = cursor.fetchone()[0] or 0

    if mode == "first":
        return 1
    return max_ver + 1

def prepare_page_compressed_heap(cursor):
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'NegativeList' AND schema_id = SCHEMA_ID('dbo'))
        BEGIN
            CREATE TABLE dbo.NegativeList (
                ID int IDENTITY(1,1) NOT NULL,
                ReferenceID nvarchar(50) NULL,
                EntityType nvarchar(50) NULL,
                Gender nvarchar(50) NULL,
                FirstName nvarchar(4000) NULL,
                LastName nvarchar(250) NULL,
                SecondName nvarchar(500) NULL,
                Title nvarchar(500) NULL,
                DOB nvarchar(92) NULL,
                ALTDOB1 datetime NULL,
                ALTDOB2 datetime NULL,
                ALTDOB3 datetime NULL,
                AddressLine1 nvarchar(255) NULL,
                AddressLine2 nvarchar(255) NULL,
                City nvarchar(50) NULL,
                Country nvarchar(100) NULL,
                WLType nvarchar(200) NULL,
                OriginalSource nvarchar(4000) NULL,
                Remark nvarchar(4000) NULL,
                NationalIDInfo nvarchar(250) NULL,
                NationalIDNo nvarchar(50) NULL,
                IdOtherInfo1 nvarchar(250) NULL,
                IdNo1 nvarchar(250) NULL,
                IdOtherInfo2 nvarchar(250) NULL,
                IdNo2 nvarchar(250) NULL,
                IdOtherInfo3 nvarchar(250) NULL,
                IdNo3 nvarchar(250) NULL,
                IdOtherInfo4 nvarchar(250) NULL,
                IdNo4 nvarchar(250) NULL,
                IdOtherInfo5 nvarchar(250) NULL,
                IdNo5 nvarchar(250) NULL,
                EntityGUID nvarchar(50) NULL,
                EntityAliasGUID nvarchar(50) NULL,
                Nationality nvarchar(100) NULL,
                Citizenship nvarchar(100) NULL,
                POB nvarchar(50) NULL,
                Alias nvarchar(500) NULL,
                VersionID int NULL,
                Action nvarchar(10) NULL,
                FileName nvarchar(255) NULL,
                CreationDate nvarchar(50) NULL,
                LastUpdatedBy nvarchar(50) NULL,
                LastUpdatedDate datetime NULL
            ) WITH (DATA_COMPRESSION = PAGE);
        END
        """
    )

def ensure_indexes(cursor):
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList_New1' AND schema_id = SCHEMA_ID('dbo')")
    if cursor.fetchone()[0] == 0:
        return

    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_New1_EntityGUID' AND object_id = OBJECT_ID('dbo.NegativeList_New1'))
        BEGIN
            CREATE CLUSTERED INDEX IX_NegativeList_New1_EntityGUID
                ON dbo.NegativeList_New1(EntityGUID);
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_EntityAlias_EntityGUID' AND object_id = OBJECT_ID('dbo.EntityAlias'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_EntityAlias_EntityGUID
                ON dbo.EntityAlias(EntityGUID)
                INCLUDE (EntityAliasGUID, AliasTypeDesc, FirstName, MiddleName, LastName, Name)
                WITH (DATA_COMPRESSION = PAGE);
        END
        """
    )

def bulk_insert_base(cursor, run_version_id: int):
    cursor.execute(
        """
        INSERT INTO dbo.NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias,
            VersionID, Action, FileName, CreationDate
        )
        SELECT
            A.ReferenceID,
            CASE WHEN A.EntityType = 'Individual'   THEN '3'
                 WHEN A.EntityType = 'Country'      THEN '1'
                 WHEN A.EntityType = 'Organization' THEN '9'
                 WHEN A.EntityType = 'Vessel'       THEN '4'
                 ELSE '6' END,
            SUBSTRING(A.Gender, 1, 7),
            A.FirstName,
            A.LastName,
            A.SecondName,
            SUBSTRING(A.Title, 1, 255),
            A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3,
            SUBSTRING(A.AddressLine1, 1, 200), SUBSTRING(A.AddressLine2, 1, 200),
            A.City, A.Country,
            A.WLType, A.OriginalSource, A.Remark, A.NationalIDInfo, A.NationalIDNo,
            A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3, A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5,
            A.EntityGUID, NULL, A.Nationality, SUBSTRING(A.Citizenship, 1, 70), A.POB, NULL,
            ?, 'add', CONVERT(char(10), GETDATE(), 126), GETDATE()
        FROM dbo.NegativeList_New1 AS A WITH (NOLOCK);
        """,
        (run_version_id,)
    )
    inserted = cursor.rowcount
    if inserted < 0:
        cursor.execute("SELECT SUM(rows) FROM sys.partitions WHERE object_id = OBJECT_ID('dbo.NegativeList') AND index_id IN (0, 1)")
        inserted = cursor.fetchone()[0] or 0
    return inserted

def bulk_insert_alias(cursor, run_version_id, inserted_base):
    cursor.execute(
        """
        INSERT INTO dbo.NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action, FileName, CreationDate
        )
        SELECT
            A.ReferenceID,
            CASE WHEN A.EntityType='Individual'   THEN '3'
                 WHEN A.EntityType='Country'      THEN '1'
                 WHEN A.EntityType='Organization' THEN '9'
                 WHEN A.EntityType='Vessel'       THEN '4'
                 ELSE '6' END,
            SUBSTRING(A.Gender,1,7),
            CAST(SUBSTRING(
                CASE 
                    WHEN NULLIF(LTRIM(RTRIM(B.FirstName)), '') IS NULL AND NULLIF(LTRIM(RTRIM(B.LastName)), '') IS NOT NULL 
                    THEN LTRIM(RTRIM(B.LastName))
                    ELSE LTRIM(RTRIM(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,'')))
                END, 1, 300) AS NVARCHAR(300)),
            CAST(SUBSTRING(
                CASE 
                    WHEN NULLIF(LTRIM(RTRIM(B.FirstName)), '') IS NULL AND NULLIF(LTRIM(RTRIM(B.LastName)), '') IS NOT NULL 
                    THEN NULL
                    ELSE NULLIF(LTRIM(RTRIM(B.LastName)), '')
                END, 1, 255) AS NVARCHAR(255)),
            CAST(SUBSTRING(REPLACE(ISNULL(B.Name, ''), ',', ''), 1, 500) AS NVARCHAR(500)),
            SUBSTRING(A.Title,1,255),
            A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3,
            SUBSTRING(A.AddressLine1,1,200),
            SUBSTRING(A.AddressLine2,1,200),
            A.City, A.Country,
            A.WLType, A.OriginalSource, A.Remark,
            A.NationalIDInfo, A.NationalIDNo,
            A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2,
            A.IdOtherInfo3, A.IdNo3, A.IdOtherInfo4, A.IdNo4,
            A.IdOtherInfo5, A.IdNo5,
            A.EntityGUID,
            B.EntityAliasGUID,
            A.Nationality,
            SUBSTRING(A.Citizenship,1,70),
            A.POB,
            CAST(SUBSTRING(REPLACE(ISNULL(B.Name, ''), ',', ''), 1, 500) AS NVARCHAR(500)),
            ?,
            'add',
            CONVERT(char(10),GETDATE(),126),
            GETDATE()
        FROM dbo.NegativeList_New1 AS A WITH (NOLOCK)
        INNER JOIN dbo.EntityAlias B WITH (NOLOCK)
            ON A.EntityGUID = B.EntityGUID
        WHERE B.AliasTypeDesc NOT IN (
              'Acronym','Call Sign','Chinese Commercial Code (CCC)',
              'Native Script For Alias','Native Script For Entity');
        """,
        (run_version_id,)
    )
    inserted = cursor.rowcount
    if inserted < 0:
        cursor.execute("SELECT SUM(rows) FROM sys.partitions WHERE object_id = OBJECT_ID('dbo.NegativeList') AND index_id IN (0, 1)")
        total_rows = cursor.fetchone()[0] or 0
        inserted = total_rows - inserted_base
    return inserted

def build_post_load_indexes(cursor):
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_EntityGUID' AND object_id = OBJECT_ID('dbo.NegativeList'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_NegativeList_EntityGUID
                ON dbo.NegativeList(EntityGUID)
                INCLUDE (ReferenceID, FirstName, LastName, VersionID)
                WITH (DATA_COMPRESSION = PAGE);
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_ReferenceID' AND object_id = OBJECT_ID('dbo.NegativeList'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_NegativeList_ReferenceID
                ON dbo.NegativeList(ReferenceID)
                WITH (DATA_COMPRESSION = PAGE);
        END
        """
    )

def populate_master_and_filter(cursor):
    cursor.execute("DROP VIEW IF EXISTS dbo.NegativeList_Master;")
    cursor.execute("DROP VIEW IF EXISTS dbo.NegativeListFilter;")

    cursor.execute(
        """
        CREATE VIEW dbo.NegativeList_Master AS
        SELECT 
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark AS Remarks, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
            IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID AS Basis, Nationality, Citizenship, POB
        FROM dbo.NegativeList WITH (NOLOCK);
        """
    )

    cursor.execute(
        """
        CREATE VIEW dbo.NegativeListFilter AS
        SELECT
            i.ID,
            UPPER(ISNULL(i.FirstName,'')) + ' ' + UPPER(ISNULL(i.LastName,'')) AS FirstName,
            UPPER(ISNULL(i.LastName,'')) + ' ' + UPPER(ISNULL(i.FirstName,'')) AS LastName,
            i.Nationality
        FROM dbo.NegativeList i WITH (NOLOCK);
        """
    )

def post_sync_cleanup(cursor, config):
    try:
        cursor.execute("CHECKPOINT;")
        cursor.execute("DBCC SHRINKFILE (2, TRUNCATEONLY);")
    except Exception:
        pass
    set_recovery_model(config, "SIMPLE")

def run_production_sync(cursor, config, mode: str):
    logging.info("[Step 1/2] Synchronizing production table dbo.NegativeList...")
    ensure_indexes(cursor)

    run_version_id = get_target_version_id(cursor, mode)

    prepare_page_compressed_heap(cursor)
    set_recovery_model(config, 'SIMPLE')
    
    inserted_base = bulk_insert_base(cursor, run_version_id)
    inserted_alias = bulk_insert_alias(cursor, run_version_id, inserted_base)
    total_rows = inserted_base + inserted_alias
    
    logging.info("  Base Profiles: %s rows | Aliases: %s rows | VersionID: %s", f"{inserted_base:,}", f"{inserted_alias:,}", run_version_id)
    logging.info("[Step 1/2] Total Production Rows: %s rows populated.", f"{total_rows:,}")

    logging.info("[Step 2/2] Building post-load indexes and refreshing search views...")
    build_post_load_indexes(cursor)
    populate_master_and_filter(cursor)
    post_sync_cleanup(cursor, config)
    logging.info("[Step 2/2] Search views dbo.NegativeList_Master & dbo.NegativeListFilter active.")

def main():
    args = parse_args()
    setup_logging(args.log_level)
    start_time_str = datetime.now().strftime("%H:%M:%S")
    global_start = time.time()

    logging.info("=========================================================")
    logging.info("   MODULE 5: PRODUCTION SYNCHRONIZATION ENGINE           ")
    logging.info("   Start Time: %s | Mode: %s", start_time_str, args.mode.upper())
    logging.info("=========================================================")

    config = load_config(args.config)
    conn = get_connection(config)
    cursor = conn.cursor()

    try:
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")
        run_production_sync(cursor, config, args.mode)

        elapsed_min = (time.time() - global_start) / 60
        end_time_str = datetime.now().strftime("%H:%M:%S")

        logging.info("=========================================================")
        logging.info("   MODULE 5 COMPLETED SUCCESSFULLY                       ")
        logging.info("   End Time: %s | Duration: %.2f minutes", end_time_str, elapsed_min)
        logging.info("=========================================================")

    except Exception as e:
        logging.error("Execution failed in Module 5: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
