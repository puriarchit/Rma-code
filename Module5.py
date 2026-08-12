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
    return pyodbc.connect(conn_str, autocommit=False)

def ensure_indexes(cursor):
    logging.info("Verifying persistent indexes on source tables...")
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList_New1' AND schema_id = SCHEMA_ID('dbo')")
    if cursor.fetchone()[0] == 0:
        raise RuntimeError(
            "NegativeList_New1 does not exist. "
            "Please run Module4_Consolidation.py first to build the source table."
        )

    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_New1_EntityGUID_ReferenceID'
                       AND object_id = OBJECT_ID('dbo.NegativeList_New1'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_NegativeList_New1_EntityGUID_ReferenceID
                ON dbo.NegativeList_New1(EntityGUID, ReferenceID);
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_EntityAlias_EntityGUID_Filter'
                       AND object_id = OBJECT_ID('EntityAlias'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_EntityAlias_EntityGUID_Filter
                ON EntityAlias(EntityGUID, AliasTypeDesc)
                INCLUDE (EntityAliasGUID, FirstName, MiddleName, LastName, Name);
        END
        """
    )

def build_basekeys(cursor):
    start = time.time()
    logging.info("Building narrow #BaseKeys (MAXDOP 8 parallel)...")
    cursor.execute("DROP TABLE IF EXISTS #BaseKeys")
    cursor.execute(
        """
        CREATE TABLE #BaseKeys (
            EntityGUID NVARCHAR(50) NOT NULL,
            ReferenceID NVARCHAR(50) NULL,
            RowRID VARBINARY(8) NOT NULL
        );
        """
    )
    cursor.execute(
        """
        ;WITH KeyRows AS (
            SELECT
                EntityGUID,
                ReferenceID,
                CONVERT(VARBINARY(8), %%physloc%%) AS RowRID,
                ROW_NUMBER() OVER (PARTITION BY EntityGUID ORDER BY ReferenceID,
                    CONVERT(VARBINARY(8), %%physloc%%)) AS rn
            FROM dbo.NegativeList_New1 WITH (READUNCOMMITTED)
        )
        INSERT INTO #BaseKeys (EntityGUID, ReferenceID, RowRID)
        SELECT EntityGUID, ReferenceID, RowRID
        FROM KeyRows
        WHERE rn = 1
        OPTION (MAXDOP 8);
        """
    )
    cursor.execute("CREATE UNIQUE CLUSTERED INDEX CX_BaseKeys_EntityGUID ON #BaseKeys(EntityGUID);")
    cursor.connection.commit()
    logging.info("#BaseKeys created in %.2f seconds.", time.time() - start)
    return time.time() - start

def build_basesource(cursor, is_initial_load):
    if is_initial_load:
        logging.info("Initial load - #BaseSource not required (full scan will use #BaseKeys).")
        return 0
    start = time.time()
    logging.info("Building #BaseSource for incremental sync (MAXDOP 8)...")
    cursor.execute("DROP TABLE IF EXISTS #BaseSource")
    cursor.execute(
        """
        SELECT
            A.ReferenceID, A.EntityType, A.Gender, A.FirstName, A.LastName, A.SecondName, A.Title,
            A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, A.AddressLine1, A.AddressLine2,
            A.City, A.Country, A.WLType, A.OriginalSource, A.Remark,
            A.NationalIDInfo, A.NationalIDNo,
            A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3,
            A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5,
            A.EntityGUID, A.Nationality, A.Citizenship, A.POB
        INTO #BaseSource
        FROM dbo.NegativeList_New1 AS A WITH (READUNCOMMITTED)
        INNER JOIN #BaseKeys AS K
            ON K.EntityGUID = A.EntityGUID
           AND K.RowRID = CONVERT(VARBINARY(8), A.%%physloc%%)
        OPTION (MAXDOP 8);
        """
    )
    cursor.connection.commit()
    logging.info("#BaseSource created in %.2f seconds.", time.time() - start)
    return time.time() - start

def recreate_negativelist_with_pk(cursor):
    start = time.time()
    step1_time = datetime.now().strftime("%H:%M:%S")
    logging.info("[1/6] Recreating NegativeList table WITH PRIMARY KEY at %s (0-cost PK!)...", step1_time)

    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList'")
    table_exists = cursor.fetchone()[0] > 0

    if table_exists:
        cursor.execute("""
            DECLARE @sql NVARCHAR(MAX) = '';
            SELECT @sql = @sql + 'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + '.' +
                   QUOTENAME(OBJECT_NAME(parent_object_id)) + ' DROP CONSTRAINT ' + QUOTENAME(name) + ';'
            FROM sys.foreign_keys WHERE referenced_object_id = OBJECT_ID('NegativeList');
            IF @sql <> '' EXEC sp_executesql @sql;
        """)
        cursor.execute("DROP TABLE IF EXISTS dbo.NegativeList")
        cursor.connection.commit()

    cursor.execute("""
        CREATE TABLE dbo.NegativeList (
            ID                  INT IDENTITY(1,1) NOT NULL,
            ReferenceID         NVARCHAR(255)  NULL,
            EntityType          NVARCHAR(50)   NULL,
            Gender              NVARCHAR(10)   NULL,
            FirstName           NVARCHAR(300)  NULL,
            LastName            NVARCHAR(255)  NULL,
            SecondName          NVARCHAR(500)  NULL,
            Title               NVARCHAR(255)  NULL,
            DOB                 NVARCHAR(100)  NULL,
            ALTDOB1             DATETIME       NULL,
            ALTDOB2             DATETIME       NULL,
            ALTDOB3             DATETIME       NULL,
            AddressLine1        NVARCHAR(500)  NULL,
            AddressLine2        NVARCHAR(500)  NULL,
            City                NVARCHAR(255)  NULL,
            Country             NVARCHAR(255)  NULL,
            WLType              NVARCHAR(100)  NULL,
            OriginalSource      NVARCHAR(MAX)  NULL,
            Remark              NVARCHAR(MAX)  NULL,
            NationalIDInfo      NVARCHAR(MAX)  NULL,
            NationalIDNo        NVARCHAR(255)  NULL,
            IdOtherInfo1        NVARCHAR(MAX)  NULL,
            IdNo1               NVARCHAR(255)  NULL,
            IdOtherInfo2        NVARCHAR(MAX)  NULL,
            IdNo2               NVARCHAR(255)  NULL,
            IdOtherInfo3        NVARCHAR(MAX)  NULL,
            IdNo3               NVARCHAR(255)  NULL,
            IdOtherInfo4        NVARCHAR(MAX)  NULL,
            IdNo4               NVARCHAR(255)  NULL,
            IdOtherInfo5        NVARCHAR(MAX)  NULL,
            IdNo5               NVARCHAR(255)  NULL,
            EntityGUID          NVARCHAR(50)   NULL,
            EntityAliasGUID     NVARCHAR(50)   NULL,
            Nationality         NVARCHAR(255)  NULL,
            Citizenship         NVARCHAR(100)  NULL,
            POB                 NVARCHAR(500)  NULL,
            Alias               NVARCHAR(500)  NULL,
            VersionID           NVARCHAR(50)   NULL,
            Action              NVARCHAR(10)   NULL,
            FileName            NVARCHAR(100)  NULL,
            CreationDate        DATETIME       NULL,
            LastUpdatedBy       INT            NULL,
            LastUpdatedDate     DATETIME       NULL,
            CONSTRAINT PK_NegativeList PRIMARY KEY CLUSTERED (ID)
        );
    """)
    cursor.connection.commit()
    logging.info("[1/6] NegativeList recreated WITH PK in %.2f seconds.", time.time() - start)
    return time.time() - start

def set_recovery_model(config: dict, model: str):
    try:
        db = config["database"]
        trusted = "yes" if db["trusted_connection"] else "no"
        admin_conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=master;Trusted_Connection={trusted};"
        admin_conn = pyodbc.connect(admin_conn_str, autocommit=True)
        admin_conn.cursor().execute(f"ALTER DATABASE [{db['name']}] SET RECOVERY {model}")
        admin_conn.close()
        logging.info("Recovery model set to %s.", model)
    except Exception as e:
        logging.warning("Could not set recovery model to %s: %s", model, e)

def bulk_insert_base(cursor, run_version_id):
    start = time.time()
    step2_time = datetime.now().strftime("%H:%M:%S")
    logging.info("[2/6] Started inserting Base records into NegativeList at %s (MAXDOP 8 parallel)...", step2_time)
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
            CASE WHEN A.EntityType='Individual' THEN 3 WHEN A.EntityType='Country' THEN 1 WHEN A.EntityType='Organization' THEN 9 WHEN A.EntityType='Vessel' THEN 4 ELSE 6 END,
            SUBSTRING(A.Gender, 1, 7),
            A.FirstName,
            SUBSTRING(A.LastName, 1, 150),
            SUBSTRING(A.SecondName, 1, 300),
            SUBSTRING(A.Title, 1, 255),
            A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3,
            SUBSTRING(A.AddressLine1, 1, 200), SUBSTRING(A.AddressLine2, 1, 200),
            A.City, A.Country,
            A.WLType, A.OriginalSource, A.Remark, A.NationalIDInfo, A.NationalIDNo,
            A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3, A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5,
            A.EntityGUID, NULL, A.Nationality, SUBSTRING(A.Citizenship, 1, 70), A.POB, NULL,
            ?, 'add', CONVERT(char(10), GETDATE(), 126), GETDATE()
        FROM dbo.NegativeList_New1 AS A WITH (READUNCOMMITTED)
        INNER JOIN #BaseKeys AS K
            ON K.EntityGUID = A.EntityGUID
           AND K.RowRID = CONVERT(VARBINARY(8), A.%%physloc%%)
        OPTION (MAXDOP 8);
        """,
        (run_version_id,)
    )
    inserted = cursor.rowcount
    cursor.connection.commit()
    logging.info("[2/6] Completed loading %d base records in %.2f seconds.", inserted, time.time() - start)
    return inserted, time.time() - start

def bulk_insert_alias(cursor, run_version_id):
    start = time.time()
    step3_time = datetime.now().strftime("%H:%M:%S")
    logging.info("[3/6] Started inserting ALL Alias records into NegativeList at %s (MAXDOP 8 parallel)...", step3_time)

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
            CASE WHEN A.EntityType='Individual'  THEN 3
                 WHEN A.EntityType='Country'      THEN 1
                 WHEN A.EntityType='Organization' THEN 9
                 WHEN A.EntityType='Vessel'       THEN 4
                 ELSE 6 END,
            SUBSTRING(A.Gender,1,7),
            CAST(SUBSTRING(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,''),1,300) AS NVARCHAR(300)),
            CAST(SUBSTRING(B.LastName,1,255) AS NVARCHAR(255)),
            CAST(SUBSTRING(B.Name,1,500)     AS NVARCHAR(500)),
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
            SUBSTRING(B.Name,1,500),
            ?,
            'add',
            CONVERT(char(10),GETDATE(),126),
            GETDATE()
        FROM dbo.NegativeList_New1 AS A WITH (READUNCOMMITTED)
        INNER JOIN dbo.EntityAlias B WITH (READUNCOMMITTED)
            ON A.EntityGUID = B.EntityGUID
        WHERE B.AliasTypeDesc NOT IN (
              'Acronym','Call Sign','Chinese Commercial Code (CCC)',
              'Native Script For Alias','Native Script For Entity')
        OPTION (MAXDOP 8);
        """,
        (run_version_id,)
    )
    inserted = cursor.rowcount
    if inserted < 0:
        cursor.execute("SELECT COUNT(*) FROM dbo.NegativeList WHERE EntityAliasGUID IS NOT NULL")
        inserted = cursor.fetchone()[0]

    cursor.connection.commit()
    logging.info("[3/6] Completed loading %d alias records in %.2f seconds.", inserted, time.time() - start)
    return inserted, time.time() - start

def create_nonclustered_indexes(cursor):
    start = time.time()
    step4_time = datetime.now().strftime("%H:%M:%S")
    logging.info("[4/6] Started creating Non-Clustered Indexes at %s (MAXDOP 8 parallel)...", step4_time)
    cursor.execute("CREATE NONCLUSTERED INDEX IX_NegativeList_EntityGUID ON NegativeList(EntityGUID) WITH (MAXDOP = 8, SORT_IN_TEMPDB = ON)")
    cursor.connection.commit()
    logging.info("  IX_NegativeList_EntityGUID created in %.2f sec", time.time() - start)

    t2 = time.time()
    cursor.execute("CREATE NONCLUSTERED INDEX IX_NegativeList_EntityAliasGUID ON NegativeList(EntityAliasGUID) WITH (MAXDOP = 8, SORT_IN_TEMPDB = ON)")
    cursor.connection.commit()
    logging.info("  IX_NegativeList_EntityAliasGUID created in %.2f sec", time.time() - t2)

    t3 = time.time()
    cursor.execute("CREATE NONCLUSTERED INDEX IX_NegativeList_SyncKey ON NegativeList(EntityGUID, EntityAliasGUID) WITH (MAXDOP = 8, SORT_IN_TEMPDB = ON)")
    cursor.connection.commit()
    logging.info("  IX_NegativeList_SyncKey created in %.2f sec", time.time() - t3)

    logging.info("[4/6] Completed non-clustered indexes in %.2f seconds.", time.time() - start)
    return time.time() - start

def populate_master_and_filter(cursor, inserted_total):
    start = time.time()
    step5_time = datetime.now().strftime("%H:%M:%S")
    logging.info("[5/6] Started populating NegativeList_Master & Filter at %s (MAXDOP 8 parallel)...", step5_time)
    cursor.execute("TRUNCATE TABLE NegativeList_Master")
    cursor.execute(
        """
        INSERT INTO NegativeList_Master WITH (TABLOCK) (
            ID, ReferenceID, WLType, FileName, VersionID, EntityType, Source, OriginalSource, Action, Gender,
            LastName, FirstName, SecondName, POB, DOB, ALTDOB1, ALTDOB2, ALTDOB3, Nationality, Citizenship,
            Alias, Title, AddressLine1, AddressLine2, City, IdNo1, IdOtherInfo1, IdNo2, IdOtherInfo2, IdNo3,
            IdOtherInfo3, IdNo4, IdOtherInfo4, IdNo5, IdOtherInfo5, NationalIDNo, NationalIDInfo, Basis, Remarks,
            Country, CreationDate, LastUpdatedBy, LastUpdatedDate
        )
        SELECT
            A.ID, A.ReferenceID, A.WLType, A.FileName, A.VersionID,
            CASE WHEN ISNUMERIC(A.EntityType)=1 THEN CAST(A.EntityType AS NUMERIC(2,0))
                 WHEN A.EntityType='Individual' THEN 3
                 WHEN A.EntityType='Country' THEN 1
                 WHEN A.EntityType='Organization' THEN 9
                 WHEN A.EntityType='Vessel' THEN 4
                 ELSE 6 END,
            NULL, A.OriginalSource, A.Action,
            CAST(SUBSTRING(A.Gender,1,7) AS NVARCHAR(7)),
            CAST(SUBSTRING(A.LastName,1,150) AS NVARCHAR(150)),
            A.FirstName,
            CAST(SUBSTRING(A.SecondName,1,300) AS NVARCHAR(300)),
            A.POB, A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3,
            A.Nationality,
            CAST(SUBSTRING(A.Citizenship,1,70) AS NVARCHAR(70)),
            A.Alias,
            CAST(SUBSTRING(A.Title,1,255) AS NVARCHAR(255)),
            CAST(SUBSTRING(A.AddressLine1,1,200) AS NVARCHAR(200)),
            CAST(SUBSTRING(A.AddressLine2,1,200) AS NVARCHAR(200)),
            A.City,
            A.IdNo1, A.IdOtherInfo1, A.IdNo2, A.IdOtherInfo2, A.IdNo3, A.IdOtherInfo3,
            A.IdNo4, A.IdOtherInfo4, A.IdNo5, A.IdOtherInfo5,
            A.NationalIDNo, A.NationalIDInfo,
            A.EntityGUID, A.Remark, A.Country,
            A.CreationDate, A.LastUpdatedBy, A.LastUpdatedDate
        FROM NegativeList A
        OPTION (MAXDOP 8);
        """
    )
    cursor.connection.commit()
    logging.info("  NegativeList_Master populated in %.2f sec", time.time() - start)

    t2 = time.time()
    cursor.execute("TRUNCATE TABLE NegativeListFilter")
    cursor.execute(
        """
        INSERT INTO NegativeListFilter WITH (TABLOCK) (ID, FirstName, LastName, Nationality)
        SELECT
            i.ID,
            UPPER(RTRIM(LTRIM(ISNULL(i.FirstName,'')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(i.LastName,'')))),
            UPPER(RTRIM(LTRIM(ISNULL(i.LastName,'')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(i.FirstName,'')))),
            i.Nationality
        FROM NegativeList i
        OPTION (MAXDOP 8);
        """
    )
    cursor.connection.commit()
    logging.info("  NegativeListFilter populated in %.2f sec", time.time() - t2)

    cursor.execute("IF OBJECT_ID('NegativeList_History_Summary','U') IS NULL CREATE TABLE NegativeList_History_Summary ([Type] varchar(29), [Count] int, [RunDate] datetime)")
    cursor.execute("TRUNCATE TABLE NegativeList_History_Summary")
    cursor.execute(
        """
        INSERT INTO NegativeList_History_Summary WITH (TABLOCK) (Type, Count, RunDate)
        VALUES
            ('New Negative List Records', ?, GETDATE()),
            ('Updated Negative List Records', 0, GETDATE()),
            ('Total Negative List Records', ?, GETDATE());
        """,
        (inserted_total, inserted_total),
    )
    cursor.connection.commit()
    logging.info("[5/6] Master & Filter populated in %.2f seconds.", time.time() - start)
    return time.time() - start

def detect_changes(cursor):
    start = time.time()
    logging.info("Detecting changes between source and target...")
    cursor.execute("DROP TABLE IF EXISTS #ChangeSet")
    cursor.execute(
        """
        CREATE TABLE #ChangeSet (
            ID INT NOT NULL PRIMARY KEY,
            ChangeType CHAR(3) NOT NULL
        );
        """
    )
    cursor.execute(
        """
        INSERT INTO #ChangeSet (ID, ChangeType)
        SELECT N.ID, 'chg'
        FROM NegativeList N
        INNER JOIN #BaseSource NT ON N.EntityGUID = NT.EntityGUID
        WHERE N.EntityAliasGUID IS NULL
          AND (
            ISNULL(N.ReferenceID,'') <> ISNULL(NT.ReferenceID,'') OR
            ISNULL(N.EntityType,0) <> CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END OR
            ISNULL(N.Gender,'') <> CAST(SUBSTRING(ISNULL(NT.Gender,''),1,7) AS NVARCHAR(7)) OR
            ISNULL(N.FirstName,'') <> ISNULL(NT.FirstName,'') OR
            ISNULL(N.LastName,'') <> CAST(SUBSTRING(ISNULL(NT.LastName,''),1,150) AS NVARCHAR(150)) OR
            ISNULL(N.SecondName,'') <> CAST(SUBSTRING(ISNULL(NT.SecondName,''),1,300) AS NVARCHAR(300)) OR
            ISNULL(N.Title,'') <> CAST(SUBSTRING(ISNULL(NT.Title,''),1,255) AS NVARCHAR(255)) OR
            ISNULL(N.DOB,'') <> ISNULL(NT.DOB,'') OR
            ISNULL(N.ALTDOB1,'1900-01-01') <> ISNULL(NT.ALTDOB1,'1900-01-01') OR
            ISNULL(N.ALTDOB2,'1900-01-01') <> ISNULL(NT.ALTDOB2,'1900-01-01') OR
            ISNULL(N.ALTDOB3,'1900-01-01') <> ISNULL(NT.ALTDOB3,'1900-01-01') OR
            ISNULL(N.AddressLine1,'') <> CAST(SUBSTRING(ISNULL(NT.AddressLine1,''),1,200) AS NVARCHAR(200)) OR
            ISNULL(N.AddressLine2,'') <> CAST(SUBSTRING(ISNULL(NT.AddressLine2,''),1,200) AS NVARCHAR(200)) OR
            ISNULL(N.City,'') <> ISNULL(NT.City,'') OR
            ISNULL(N.Country,'') <> ISNULL(NT.Country,'') OR
            ISNULL(N.WLType,'') <> ISNULL(NT.WLType,'') OR
            ISNULL(N.OriginalSource,'') <> ISNULL(NT.OriginalSource,'') OR
            ISNULL(N.Remark,'') <> ISNULL(NT.Remark,'') OR
            ISNULL(N.NationalIDInfo,'') <> ISNULL(NT.NationalIDInfo,'') OR
            ISNULL(N.NationalIDNo,'') <> ISNULL(NT.NationalIDNo,'') OR
            ISNULL(N.IdOtherInfo1,'') <> ISNULL(NT.IdOtherInfo1,'') OR
            ISNULL(N.IdNo1,'') <> ISNULL(NT.IdNo1,'') OR
            ISNULL(N.IdOtherInfo2,'') <> ISNULL(NT.IdOtherInfo2,'') OR
            ISNULL(N.IdNo2,'') <> ISNULL(NT.IdNo2,'') OR
            ISNULL(N.IdOtherInfo3,'') <> ISNULL(NT.IdOtherInfo3,'') OR
            ISNULL(N.IdNo3,'') <> ISNULL(NT.IdNo3,'') OR
            ISNULL(N.IdOtherInfo4,'') <> ISNULL(NT.IdOtherInfo4,'') OR
            ISNULL(N.IdNo4,'') <> ISNULL(NT.IdNo4,'') OR
            ISNULL(N.IdOtherInfo5,'') <> ISNULL(NT.IdOtherInfo5,'') OR
            ISNULL(N.IdNo5,'') <> ISNULL(NT.IdNo5,'') OR
            ISNULL(N.Nationality,'') <> ISNULL(NT.Nationality,'') OR
            ISNULL(N.Citizenship,'') <> CAST(SUBSTRING(ISNULL(NT.Citizenship,''),1,70) AS NVARCHAR(70)) OR
            ISNULL(N.POB,'') <> ISNULL(NT.POB,'') OR
            N.Alias IS NOT NULL
          );
        """
    )
    cursor.execute(
        """
        INSERT INTO #ChangeSet (ID, ChangeType)
        SELECT N.ID, 'chg'
        FROM NegativeList N
        INNER JOIN #BaseSource A ON N.EntityGUID = A.EntityGUID
        INNER JOIN EntityAlias B WITH (READUNCOMMITTED) ON A.EntityGUID = B.EntityGUID AND N.EntityAliasGUID = B.EntityAliasGUID
        WHERE N.EntityAliasGUID IS NOT NULL
          AND B.AliasTypeDesc NOT IN ('Acronym','Call Sign','Chinese Commercial Code (CCC)','Native Script For Alias','Native Script For Entity')
          AND NOT EXISTS (SELECT 1 FROM #ChangeSet C WHERE C.ID = N.ID)
          AND (
            ISNULL(N.ReferenceID,'') <> ISNULL(A.ReferenceID,'') OR
            ISNULL(N.EntityType,0) <> CASE WHEN A.EntityType='Individual' THEN 3 WHEN A.EntityType='Country' THEN 1 WHEN A.EntityType='Organization' THEN 9 WHEN A.EntityType='Vessel' THEN 4 ELSE 6 END OR
            ISNULL(N.Gender,'') <> CAST(SUBSTRING(ISNULL(A.Gender,''),1,7) AS NVARCHAR(7)) OR
            ISNULL(N.FirstName,'') <> CAST(SUBSTRING(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,''),1,300) AS NVARCHAR(300)) OR
            ISNULL(N.LastName,'') <> CAST(SUBSTRING(B.LastName,1,255) AS NVARCHAR(255)) OR
            ISNULL(N.SecondName,'') <> CAST(SUBSTRING(B.Name,1,500) AS NVARCHAR(500)) OR
            ISNULL(N.Title,'') <> CAST(SUBSTRING(ISNULL(A.Title,''),1,255) AS NVARCHAR(255)) OR
            ISNULL(N.DOB,'') <> ISNULL(A.DOB,'') OR
            ISNULL(N.ALTDOB1,'1900-01-01') <> ISNULL(A.ALTDOB1,'1900-01-01') OR
            ISNULL(N.ALTDOB2,'1900-01-01') <> ISNULL(A.ALTDOB2,'1900-01-01') OR
            ISNULL(N.ALTDOB3,'1900-01-01') <> ISNULL(A.ALTDOB3,'1900-01-01') OR
            ISNULL(N.AddressLine1,'') <> CAST(SUBSTRING(ISNULL(A.AddressLine1,''),1,200) AS NVARCHAR(200)) OR
            ISNULL(N.AddressLine2,'') <> CAST(SUBSTRING(ISNULL(A.AddressLine2,''),1,200) AS NVARCHAR(200)) OR
            ISNULL(N.City,'') <> ISNULL(A.City,'') OR
            ISNULL(N.Country,'') <> ISNULL(A.Country,'') OR
            ISNULL(N.WLType,'') <> ISNULL(A.WLType,'') OR
            ISNULL(N.OriginalSource,'') <> ISNULL(A.OriginalSource,'') OR
            ISNULL(N.Remark,'') <> ISNULL(A.Remark,'') OR
            ISNULL(N.NationalIDInfo,'') <> ISNULL(A.NationalIDInfo,'') OR
            ISNULL(N.NationalIDNo,'') <> ISNULL(A.NationalIDNo,'') OR
            ISNULL(N.IdOtherInfo1,'') <> ISNULL(A.IdOtherInfo1,'') OR
            ISNULL(N.IdNo1,'') <> ISNULL(A.IdNo1,'') OR
            ISNULL(N.IdOtherInfo2,'') <> ISNULL(A.IdOtherInfo2,'') OR
            ISNULL(N.IdNo2,'') <> ISNULL(A.IdNo2,'') OR
            ISNULL(N.IdOtherInfo3,'') <> ISNULL(A.IdOtherInfo3,'') OR
            ISNULL(N.IdNo3,'') <> ISNULL(A.IdNo3,'') OR
            ISNULL(N.IdOtherInfo4,'') <> ISNULL(A.IdOtherInfo4,'') OR
            ISNULL(N.IdNo4,'') <> ISNULL(A.IdNo4,'') OR
            ISNULL(N.IdOtherInfo5,'') <> ISNULL(A.IdOtherInfo5,'') OR
            ISNULL(N.IdNo5,'') <> ISNULL(A.IdNo5,'') OR
            ISNULL(N.Nationality,'') <> ISNULL(A.Nationality,'') OR
            ISNULL(N.Citizenship,'') <> CAST(SUBSTRING(ISNULL(A.Citizenship,''),1,70) AS NVARCHAR(70)) OR
            ISNULL(N.POB,'') <> ISNULL(A.POB,'') OR
            ISNULL(N.Alias,'') <> ISNULL(B.Name,'')
          );
        """
    )
    cursor.connection.commit()
    cnt = cursor.execute("SELECT COUNT(*) FROM #ChangeSet").fetchone()[0]
    logging.info("Change detection completed in %.2f seconds (changeset rows: %d).", time.time() - start, cnt)
    return time.time() - start

def cleanup(cursor):
    start = time.time()
    logging.info("Dropping temporary tables...")
    cursor.execute("DROP TABLE IF EXISTS #BaseSource")
    cursor.execute("DROP TABLE IF EXISTS #ChangeSet")
    cursor.execute("DROP TABLE IF EXISTS #NewIDs")
    cursor.execute("DROP TABLE IF EXISTS #AffectedIDs")
    cursor.connection.commit()
    logging.info("Cleanup finished in %.2f seconds.", time.time() - start)
    return time.time() - start

def pre_sync_cleanup(cursor):
    start = time.time()
    logging.info("Pre-sync cleanup: removing unreferenced temp staging tables...")
    tables_to_drop = [
        "NegativeList_Staging",
        "AssociatedEntity",
        "ConsolidatedSanction",
        "EntityAdverseMedia",
        "EntityAdverseMediaSubCategory",
    ]
    for table in tables_to_drop:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS dbo.[{table}]")
            cursor.connection.commit()
        except Exception:
            pass
    logging.info("Pre-sync cleanup completed in %.2f seconds.", time.time() - start)

def post_sync_cleanup(cursor, config):
    start = time.time()
    step6_time = datetime.now().strftime("%H:%M:%S")
    logging.info("[6/6] Started post-sync cleanup & DB shrink at %s...", step6_time)
    try:
        cursor.execute("DROP TABLE IF EXISTS dbo.[NegativeList_New1]")
        cursor.connection.commit()
        logging.info("  Reclaimed space: dropped consumed source table NegativeList_New1.")
    except Exception as ex:
        logging.warning("Could not drop NegativeList_New1: %s", ex)

    try:
        db_name = config["database"]["name"]
        set_recovery_model(config, "SIMPLE")
        admin_conn_str = f"DRIVER={{{config['database']['driver']}}};SERVER={config['database']['server']};DATABASE={db_name};Trusted_Connection=yes;"
        admin_conn = pyodbc.connect(admin_conn_str, autocommit=True)
        admin_cursor = admin_conn.cursor()
        admin_cursor.execute("CHECKPOINT")
        admin_cursor.execute(f"DBCC SHRINKFILE ([{db_name}_log], 512)")
        admin_cursor.execute(f"DBCC SHRINKDATABASE ([{db_name}])")
        admin_conn.close()
        logging.info("  Database file & log shrink completed. Space released to OS!")
    except Exception as ex:
        logging.warning("Shrink warning: %s", ex)

    logging.info("[6/6] Completed post-sync cleanup in %.2f seconds.", time.time() - start)

def main():
    args = parse_args()
    setup_logging(args.log_level)
    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 5: Database Sync [Started at %s] ===", start_time_str)
    global_start = time.time()

    config = load_config(args.config)
    conn = get_connection(config)
    cursor = conn.cursor()

    try:
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList_LoadState'")
        state_table_exists = cursor.fetchone()[0] > 0
        is_initial_load = True
        if state_table_exists:
            cursor.execute("SELECT TOP 1 LoadState FROM NegativeList_LoadState ORDER BY UpdatedDate DESC")
            row = cursor.fetchone()
            if row and row[0] == 'COMPLETED':
                cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList'")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("SELECT TOP 1 1 FROM NegativeList WITH (NOLOCK)")
                    if cursor.fetchone():
                        is_initial_load = False
        logging.info("Load state: %s", "INITIAL" if is_initial_load else "INCREMENTAL")

        pre_sync_cleanup(cursor)
        ensure_indexes(cursor)
        build_basekeys(cursor)
        build_basesource(cursor, is_initial_load)

        if is_initial_load:
            cursor.execute("SELECT NEXT VALUE FOR dbo.NegativeListVersionSeq")
            run_version_id = str(cursor.fetchone()[0])

            # STEP 1: Recreate NegativeList WITH PK clustered from start
            recreate_negativelist_with_pk(cursor)

            # STEP 2: Switch to SIMPLE recovery model
            set_recovery_model(config, 'SIMPLE')

            # STEP 3: Insert base + alias directly into pre-indexed table
            inserted_base, _ = bulk_insert_base(cursor, run_version_id)
            inserted_alias, _ = bulk_insert_alias(cursor, run_version_id)

            # STEP 4: PK already exists! 0-cost PK
            logging.info("Primary Key clustered index pre-indexed - SKIPPED ALTER TABLE (0.00 seconds!).")

            # STEP 5: Create non-clustered indexes (MAXDOP 8)
            create_nonclustered_indexes(cursor)

            # STEP 6: Populate master & filter (MAXDOP 8)
            populate_master_and_filter(cursor, inserted_base + inserted_alias)
        else:
            detect_changes(cursor)
            cleanup(cursor)

        post_sync_cleanup(cursor, config)
        elapsed_min = (time.time() - global_start) / 60
        end_time_str = datetime.now().strftime("%H:%M:%S")
        logging.info("=== Module 5 completed in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)
    except Exception as e:
        logging.error("Execution failed: %s", e)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()


