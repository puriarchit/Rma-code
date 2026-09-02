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
    parser.add_argument("--mode", default="auto", choices=["auto", "first", "inc"],
                        help="Execution mode: 'first' (VersionID=1), 'inc' (VersionID=max+1), or 'auto'")
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

def run_pep_consolidation(cursor, config):
    logging.info("[Step 1/3] Consolidating PEP watchlists...")
    ROW_LIMIT = config.get("benchmark_row_limit", None)
    step_start = time.time()

    cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
    cursor.execute("""
        SELECT A.EntityGUID, B.tCountry AS Nationality
        INTO #TempNationalities
        FROM EntityCountryAssociation A WITH (NOLOCK)
        LEFT JOIN Country B WITH (NOLOCK) ON A.ISOStandard = B.tISO
        WHERE A.AssociationTypeDesc = 'Nationality'
    """)
    cursor.execute("CREATE CLUSTERED INDEX IX_TempNationalities_EntityGUID ON #TempNationalities(EntityGUID)")

    cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
    cursor.execute("""
        SELECT DISTINCT EntityGUID
        INTO #PEP_GUIDs
        FROM EntityCountryAssociation WITH (NOLOCK)
        WHERE AssociationTypeDesc = 'PEP'
    """)
    cursor.execute("CREATE CLUSTERED INDEX IX_PEP_GUIDs_EntityGUID ON #PEP_GUIDs(EntityGUID)")

    if ROW_LIMIT is not None:
        cte_prefix = f"""
        ;WITH Batch AS (
            SELECT TOP ({ROW_LIMIT}) EntityGUID
            FROM Entity WITH (NOLOCK)
            ORDER BY EntityGUID
        )
        """
        from_clause = "FROM Batch bt INNER JOIN Entity A WITH (NOLOCK) ON bt.EntityGUID = A.EntityGUID"
    else:
        cte_prefix = ""
        from_clause = "FROM Entity A WITH (NOLOCK)"

    cursor.execute(f"""
        {cte_prefix}
        INSERT INTO NegativeList_New1 WITH (TABLOCK) (
            EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Nationality, Citizenship
        )
        SELECT 
            A.EntityGUID,
            CAST(SUBSTRING(A.EntityID, 1, 50) AS NVARCHAR(50)) as ReferenceID,
            CAST(SUBSTRING(A.EntityTypeDesc, 1, 50) AS NVARCHAR(50)) as EntityType,
            CAST(SUBSTRING(A.Gender, 1, 50) AS NVARCHAR(50)) as Gender,
            CAST(B.FirstName AS NVARCHAR(300)) as FirstName,
            CAST(B.LastName AS NVARCHAR(255)) as LastName,
            CAST(B.SecondName AS NVARCHAR(500)) as SecondName,
            CAST(A.Title AS NVARCHAR(255)) as Title,
            C.DOB, C.ALTDOB1, C.ALTDOB2, C.ALTDOB3,
            D.Address1 as AddressLine1, D.Address2 as AddressLine2, D.City, D.Country,
            CAST(NULL AS NVARCHAR(500)) as POB,
            'PEP' as WLType,
            CAST(G.OriginalSource AS NVARCHAR(MAX)) as OriginalSource,
            CAST(F.Remark AS NVARCHAR(MAX)) as Remark,
            CAST(NULL AS NVARCHAR(MAX)) as NationalIDInfo,
            CAST(NULL AS NVARCHAR(255)) as NationalIDNo,
            E.IdOtherInfo1, E.IdNo1, E.IdOtherInfo2, E.IdNo2, E.IdOtherInfo3, E.IdNo3, E.IdOtherInfo4, E.IdNo4, E.IdOtherInfo5, E.IdNo5,
            H.Nationality,
            CAST(I.CountryName AS NVARCHAR(100)) as Citizenship
        {from_clause}
        INNER JOIN #PEP_GUIDs PG ON A.EntityGUID = PG.EntityGUID
        LEFT JOIN EntityAlias_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        LEFT JOIN EntityDOB_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
        LEFT JOIN EntityAddress_New D WITH (NOLOCK) ON A.EntityGUID = D.EntityGUID
        LEFT JOIN EntityIdentification_New E WITH (NOLOCK) ON A.EntityGUID = E.EntityGUID
        LEFT JOIN EntityRemark_New F WITH (NOLOCK) ON A.EntityGUID = F.EntityGUID
        LEFT JOIN EntitySourceItem_New G WITH (NOLOCK) ON A.EntityGUID = G.EntityGUID
        LEFT JOIN #TempNationalities H ON A.EntityGUID = H.EntityGUID
        LEFT JOIN Entity_Citizenship_New I WITH (NOLOCK) ON A.EntityGUID = I.EntityGUID
    """)
    logging.info("[Step 1/3] PEP watchlist consolidation completed in %.2f seconds.", time.time() - step_start)

def get_target_version_id(cursor, mode: str) -> str:
    if mode == "first":
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'NegativeListVersionSeq' AND schema_id = SCHEMA_ID('dbo'))
                CREATE SEQUENCE dbo.NegativeListVersionSeq AS INT START WITH 1 INCREMENT BY 1;
            ELSE
                ALTER SEQUENCE dbo.NegativeListVersionSeq RESTART WITH 1;
        """)
        cursor.execute("SELECT NEXT VALUE FOR dbo.NegativeListVersionSeq")
        version_id = str(cursor.fetchone()[0])
        return version_id

    elif mode == "inc":
        cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList' AND schema_id = SCHEMA_ID('dbo')")
        if cursor.fetchone()[0] > 0:
            cursor.execute("""
                SELECT ISNULL(MAX(CAST(VersionID AS INT)), 0) + 1 
                FROM dbo.NegativeList WITH (NOLOCK) 
                WHERE ISNUMERIC(VersionID) = 1
            """)
            version_id = str(cursor.fetchone()[0])
        else:
            version_id = "1"
        return version_id

    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'NegativeListVersionSeq' AND schema_id = SCHEMA_ID('dbo'))
                CREATE SEQUENCE dbo.NegativeListVersionSeq AS INT START WITH 1 INCREMENT BY 1;
        """)
        cursor.execute("SELECT NEXT VALUE FOR dbo.NegativeListVersionSeq")
        version_id = str(cursor.fetchone()[0])
        return version_id

def ensure_indexes(cursor):
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList_New1' AND schema_id = SCHEMA_ID('dbo')")
    if cursor.fetchone()[0] == 0:
        return
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_EntityAlias_EntityGUID_Covering'
                       AND object_id = OBJECT_ID('EntityAlias'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_EntityAlias_EntityGUID_Covering
                ON EntityAlias(EntityGUID, AliasTypeDesc)
                INCLUDE (EntityAliasGUID, FirstName, MiddleName, LastName, Name);
        END
        """
    )

def prepare_page_compressed_heap(cursor):
    cursor.execute("DROP TABLE IF EXISTS dbo.NegativeList")
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
            WLType              NVARCHAR(250)  NULL,
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
            Basis               NVARCHAR(50)   NULL,
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
            LastUpdatedDate     DATETIME       NULL
        ) WITH (DATA_COMPRESSION = PAGE);
    """)

def set_recovery_model(config: dict, model: str):
    try:
        db = config["database"]
        trusted = "yes" if db["trusted_connection"] else "no"
        admin_conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=master;Trusted_Connection={trusted};"
        admin_conn = pyodbc.connect(admin_conn_str, autocommit=True)
        admin_conn.cursor().execute(f"ALTER DATABASE [{db['name']}] SET RECOVERY {model}")
        admin_conn.close()
    except Exception:
        pass

def bulk_insert_base(cursor, run_version_id):
    cursor.execute(
        """
        INSERT INTO dbo.NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Basis, EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID
        )
        SELECT
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Basis, EntityGUID, NULL, Nationality, Citizenship, POB, NULL, ?
        FROM dbo.NegativeList_New1 WITH (NOLOCK)
        """,
        (run_version_id,),
    )
    return cursor.rowcount

def bulk_insert_alias(cursor, run_version_id):
    cursor.execute(
        """
        INSERT INTO dbo.NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Basis, EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID
        )
        SELECT
            n.ReferenceID, n.EntityType, n.Gender,
            CASE WHEN a.FirstName IS NOT NULL AND a.FirstName <> '' THEN a.FirstName ELSE n.FirstName END,
            CASE WHEN a.LastName  IS NOT NULL AND a.LastName  <> '' THEN a.LastName  ELSE n.LastName  END,
            n.SecondName, n.Title,
            n.DOB, n.ALTDOB1, n.ALTDOB2, n.ALTDOB3, n.AddressLine1, n.AddressLine2, n.City, n.Country,
            n.WLType, n.OriginalSource, n.Remark, n.NationalIDInfo, n.NationalIDNo,
            n.IdOtherInfo1, n.IdNo1, n.IdOtherInfo2, n.IdNo2, n.IdOtherInfo3, n.IdNo3, n.IdOtherInfo4, n.IdNo4, n.IdOtherInfo5, n.IdNo5,
            n.Basis, n.EntityGUID, a.EntityAliasGUID, n.Nationality, n.Citizenship, n.POB, a.Name, ?
        FROM dbo.NegativeList_New1 n WITH (NOLOCK)
        INNER JOIN dbo.EntityAlias a WITH (NOLOCK)
            ON n.EntityGUID = a.EntityGUID
        WHERE a.AliasTypeDesc IN ('Also Known As', 'Formerly Known As', 'Maiden Name', 'Spelling Variation')
        """,
        (run_version_id,),
    )
    return cursor.rowcount

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
        SELECT * FROM dbo.NegativeList WITH (NOLOCK);
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
    logging.info("[Step 2/3] Synchronizing production table dbo.NegativeList...")
    ensure_indexes(cursor)

    run_version_id = get_target_version_id(cursor, mode)

    prepare_page_compressed_heap(cursor)
    set_recovery_model(config, 'SIMPLE')
    
    inserted_base = bulk_insert_base(cursor, run_version_id)
    inserted_alias = bulk_insert_alias(cursor, run_version_id)
    total_rows = inserted_base + inserted_alias
    
    logging.info("  Base Profiles: %s rows | Aliases: %s rows | VersionID: %s", f"{inserted_base:,}", f"{inserted_alias:,}", run_version_id)
    logging.info("[Step 2/3] Total Production Rows: %s rows populated.", f"{total_rows:,}")

    logging.info("[Step 3/3] Building post-load indexes and refreshing search views...")
    build_post_load_indexes(cursor)
    populate_master_and_filter(cursor)
    post_sync_cleanup(cursor, config)
    logging.info("[Step 3/3] Search views dbo.NegativeList_Master & dbo.NegativeListFilter active.")

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
        run_pep_consolidation(cursor, config)
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
