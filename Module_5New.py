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
    parser.add_argument("--action", default="all", choices=["all", "pep", "sync"],
                        help="Action to perform: 'pep' (Consolidate PEPs), 'sync' (Master Sync), or 'all'")
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

# =====================================================================
# ACTION 1: PEP WATCHLIST CONSOLIDATION (13 PACKAGES: 2_1 TO 4_4)
# =====================================================================
def run_pep(cursor, config):
    global_start = time.time()
    logging.info("=== [Module 5] Stage: PEP Watchlist Consolidation (NegativeList_2_1 to 4_4) ===")
    ROW_LIMIT = config.get("benchmark_row_limit", None)

    logging.info("Building temporary lookup tables...")
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

    logging.info("Temporary lookup tables created in %.2f seconds.", time.time() - step_start)

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

    logging.info("Consolidating PEP profiles...")
    stage2_start = time.time()
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
            CAST(SUBSTRING(ISNULL(A.FirstName,'') + ' ' + ISNULL(A.MiddleName,''), 1, 4000) AS NVARCHAR(4000)) as FirstName,
            CAST(SUBSTRING(A.LastName, 1, 250) AS NVARCHAR(250)) as LastName,
            CAST(SUBSTRING(A.Name, 1, 500) AS NVARCHAR(500)) as SecondName,
            CAST(SUBSTRING(A.Title, 1, 250) AS NVARCHAR(250)) as Title,
            B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3,
            C.AddressLine1, C.AddressLine2, C.City, C.Country, C.POB,
            'PEP' AS WLType,
            E.SourceURI as OriginalSource,
            D.Remark,
            H.IdentificationTypeDesc as NationalIDInfo,
            H.IdentificationNumber as NationalIDNo,
            I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
            J.Nationality,
            K.Citizenship
        {from_clause}
        INNER JOIN #PEP_GUIDs p ON A.EntityGUID = p.EntityGUID
        LEFT JOIN EntityDOB_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        LEFT JOIN EntityAddress_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
        LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON A.EntityGUID = D.EntityGUID
        LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON A.EntityGUID = E.EntityGUID
        LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON A.EntityGUID = F.EntityGUID
        LEFT JOIN EntitySanction G WITH (NOLOCK) ON A.EntityGUID = G.EntityGUID
        LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON A.EntityGUID = H.EntityGUID
        LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON A.EntityGUID = I.EntityGUID
        LEFT JOIN #TempNationalities J ON A.EntityGUID = J.EntityGUID
        LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON A.EntityGUID = K.EntityGUID
        OPTION (MERGE JOIN, RECOMPILE)
    """)
    logging.info("PEP profiles completed in %.2f seconds.", time.time() - stage2_start)

    cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
    cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")

    logging.info("Cleaning up intermediate staging tables...")
    intermediate_tables = [
        "EntityAddress_New", "EntityDOB_New", "EntityIdentification_New",
        "EntityIdentification_National_New", "Entity_Citizenship_New",
        "EntityRemark_New", "EntitySourceItem_New"
    ]
    for tbl in intermediate_tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS dbo.[{tbl}]")
        except Exception:
            pass

    logging.info("PEP Watchlist Consolidation completed successfully in %.2f minutes.", (time.time() - global_start) / 60)

# =====================================================================
# ACTION 2: DATABASE SYNC & VIEW CREATION (NEGATIVE LIST MASTER)
# =====================================================================
def pre_sync_cleanup(cursor):
    try:
        cursor.execute("DROP TABLE IF EXISTS dbo.[NegativeList_New1_Temp]")
    except Exception:
        pass

def ensure_sequence(cursor):
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'NegativeListVersionSeq' AND schema_id = SCHEMA_ID('dbo'))
        BEGIN
            CREATE SEQUENCE dbo.NegativeListVersionSeq AS INT START WITH 1 INCREMENT BY 1;
        END
        """
    )

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
            Basis, EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action, FileName, CreationDate
        )
        SELECT
            A.ReferenceID,
            CASE WHEN A.EntityType='Individual' THEN '3' WHEN A.EntityType='Country' THEN '1' WHEN A.EntityType='Organization' THEN '9' WHEN A.EntityType='Vessel' THEN '4' ELSE '6' END,
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
            A.EntityGUID, A.EntityGUID, NULL, A.Nationality, SUBSTRING(A.Citizenship, 1, 70), A.POB, NULL,
            ?, 'add', CONVERT(char(10), GETDATE(), 126), GETDATE()
        FROM dbo.NegativeList_New1 AS A WITH (NOLOCK);
        """,
        (run_version_id,)
    )
    return cursor.rowcount

def bulk_insert_alias(cursor, run_version_id):
    # Load character translation map
    cursor.execute("SELECT Symbol, MapChar FROM LexisNexis_Data.dbo.WLCharMap")
    char_map = cursor.fetchall()
    
    def get_translate_sql(expr):
        collate_clause = "COLLATE SQL_Latin1_General_CP1_CS_AS"
        sql = f"CAST({expr} AS NVARCHAR(MAX)) {collate_clause}"
        for sym, mc in char_map:
            sym_esc = sym.replace("'", "''")
            mc_esc = mc.replace("'", "''")
            sql = f"REPLACE({sql}, N'{sym_esc}' {collate_clause}, N'{mc_esc}' {collate_clause})"
        return sql

    def apply_formatting(expr):
        return f"REPLACE(REPLACE(REPLACE({expr}, '-', ' '), ',', ''), '''', '')"

    T_FirstName = get_translate_sql(apply_formatting("ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,'')"))
    T_LastName = get_translate_sql(apply_formatting("ISNULL(B.LastName,'')"))
    T_SecondName = get_translate_sql(apply_formatting("ISNULL(B.Name,'')"))

    FN_Expr = f"""CAST(SUBSTRING(
        CASE WHEN LEN(TRIM({T_FirstName})) < 1 AND LEN(TRIM({T_LastName})) > 0 
             THEN {T_LastName} 
             ELSE {T_FirstName} 
        END, 1, 300) AS NVARCHAR(300))"""

    LN_Expr = f"""CAST(SUBSTRING(
        CASE WHEN LEN(TRIM({T_FirstName})) < 1 AND LEN(TRIM({T_LastName})) > 0 
             THEN '' 
             ELSE {T_LastName} 
        END, 1, 255) AS NVARCHAR(255))"""

    SN_Expr = f"""CAST(SUBSTRING(
        REPLACE(REPLACE(REPLACE({T_SecondName}, '-', ' '), ',', ''), '''', ''), 1, 500) AS NVARCHAR(500))"""

    cursor.execute(
        f"""
        INSERT INTO dbo.NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Basis, EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action, FileName, CreationDate
        )
        SELECT
            A.ReferenceID,
            CASE WHEN A.EntityType='Individual'  THEN '3'
                 WHEN A.EntityType='Country'      THEN '1'
                 WHEN A.EntityType='Organization' THEN '9'
                 WHEN A.EntityType='Vessel'       THEN '4'
                 ELSE '6' END,
            SUBSTRING(A.Gender,1,7),
            {FN_Expr},
            {LN_Expr},
            {SN_Expr},
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
        FROM dbo.NegativeList_New1 AS A WITH (NOLOCK)
        INNER JOIN dbo.EntityAlias B WITH (NOLOCK)
            ON A.EntityGUID = B.EntityGUID
        WHERE B.AliasTypeDesc NOT IN (
              'Acronym','Call Sign','Chinese Commercial Code (CCC)',
              'Native Script For Alias','Native Script For Entity')
        ORDER BY A.ReferenceID, B.EntityAliasID;
        """,
        (run_version_id,)
    )
    inserted = cursor.rowcount
    if inserted < 0:
        cursor.execute("SELECT COUNT(*) FROM dbo.NegativeList WITH (NOLOCK) WHERE EntityAliasGUID IS NOT NULL")
        inserted = cursor.fetchone()[0]

    try:
        cursor.execute("CHECKPOINT;")
    except Exception:
        pass
    return inserted

def build_post_load_indexes(cursor):
    cursor.execute("SELECT COUNT(*) FROM sys.indexes WHERE name = 'PK_NegativeList' AND object_id = OBJECT_ID('dbo.NegativeList')")
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE dbo.NegativeList ADD CONSTRAINT PK_NegativeList PRIMARY KEY NONCLUSTERED (ID)")
    cursor.execute("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_EntityGUID' AND object_id = OBJECT_ID('dbo.NegativeList')) CREATE NONCLUSTERED INDEX IX_NegativeList_EntityGUID ON NegativeList(EntityGUID)")
    cursor.execute("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_EntityAliasGUID' AND object_id = OBJECT_ID('dbo.NegativeList')) CREATE NONCLUSTERED INDEX IX_NegativeList_EntityAliasGUID ON NegativeList(EntityAliasGUID)")

def populate_master_and_filter(cursor, inserted_total):
    cursor.execute("IF OBJECT_ID('dbo.NegativeList_Master', 'U') IS NOT NULL DROP TABLE dbo.NegativeList_Master;")
    cursor.execute("IF OBJECT_ID('dbo.NegativeList_Master', 'V') IS NOT NULL DROP VIEW dbo.NegativeList_Master;")
    cursor.execute("IF OBJECT_ID('dbo.NegativeListFilter', 'U') IS NOT NULL DROP TABLE dbo.NegativeListFilter;")
    cursor.execute("IF OBJECT_ID('dbo.NegativeListFilter', 'V') IS NOT NULL DROP VIEW dbo.NegativeListFilter;")

    cursor.execute(
        """
        CREATE VIEW dbo.NegativeList_Master AS
        SELECT
            A.ID,
            A.ReferenceID, A.WLType, A.FileName, A.VersionID,
            CASE WHEN ISNUMERIC(A.EntityType)=1 THEN CAST(A.EntityType AS NUMERIC(2,0))
                 WHEN A.EntityType='Individual' THEN 3
                 WHEN A.EntityType='Country' THEN 1
                 WHEN A.EntityType='Organization' THEN 9
                 WHEN A.EntityType='Vessel' THEN 4
                 ELSE 6 END AS EntityType,
            CAST(NULL AS NVARCHAR(50)) AS Source,
            A.OriginalSource, A.Action,
            CAST(SUBSTRING(A.Gender,1,7) AS NVARCHAR(7)) AS Gender,
            CAST(SUBSTRING(A.LastName,1,150) AS NVARCHAR(150)) AS LastName,
            A.FirstName,
            CAST(SUBSTRING(A.SecondName,1,300) AS NVARCHAR(300)) AS SecondName,
            A.POB, A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3,
            A.Nationality,
            CAST(SUBSTRING(A.Citizenship,1,70) AS NVARCHAR(70)) AS Citizenship,
            A.Alias,
            CAST(SUBSTRING(A.Title,1,255) AS NVARCHAR(255)) AS Title,
            CAST(SUBSTRING(A.AddressLine1,1,200) AS NVARCHAR(200)) AS AddressLine1,
            CAST(SUBSTRING(A.AddressLine2,1,200) AS NVARCHAR(200)) AS AddressLine2,
            A.City,
            A.IdNo1, A.IdOtherInfo1, A.IdNo2, A.IdOtherInfo2, A.IdNo3, A.IdOtherInfo3,
            A.IdNo4, A.IdOtherInfo4, A.IdNo5, A.IdOtherInfo5,
            A.NationalIDNo, A.NationalIDInfo,
            A.EntityGUID AS Basis, A.Remark AS Remarks, A.Country,
            A.CreationDate, A.LastUpdatedBy, A.LastUpdatedDate
        FROM dbo.NegativeList A WITH (NOLOCK);
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

    # NegativeList_History_Summary table logic (previously corresponding to NegativeList_4_6)
    # has been removed as per decommissioned package execution lists.

def post_sync_cleanup(cursor, config):
    try:
        cursor.execute("CHECKPOINT;")
        cursor.execute("DBCC SHRINKFILE (2, TRUNCATEONLY);")
    except Exception:
        pass
    set_recovery_model(config, "SIMPLE")

def check_existing_progress(cursor):
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList' AND schema_id = SCHEMA_ID('dbo')")
    if cursor.fetchone()[0] == 0:
        return False, 0
    cursor.execute("SELECT SUM(row_count) FROM sys.dm_db_partition_stats WHERE object_id = OBJECT_ID('dbo.NegativeList') AND index_id IN (0, 1)")
    row_count = cursor.fetchone()[0] or 0
    if row_count >= 3000000:
        return True, row_count
    return False, 0

def run_sync(cursor, config):
    global_start = time.time()
    logging.info("=== [Module 5] Stage: Database Sync (NegativeList_Master) ===")
    
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NegativeList_New1' AND schema_id = SCHEMA_ID('dbo')")
    if cursor.fetchone()[0] == 0:
        logging.info("Source table NegativeList_New1 does not exist. Nothing to sync. Skipping.")
        return
        
    pre_sync_cleanup(cursor)
    ensure_sequence(cursor)
    ensure_indexes(cursor)

    cursor.execute("SELECT NEXT VALUE FOR dbo.NegativeListVersionSeq")
    run_version_id = str(cursor.fetchone()[0])

    is_resumable, existing_rows = check_existing_progress(cursor)

    if not is_resumable:
        prepare_page_compressed_heap(cursor)
        set_recovery_model(config, 'SIMPLE')
        inserted_base = bulk_insert_base(cursor, run_version_id)
        inserted_alias = bulk_insert_alias(cursor, run_version_id)
        inserted_total = inserted_base + inserted_alias
    else:
        inserted_total = existing_rows
        set_recovery_model(config, 'SIMPLE')

    build_post_load_indexes(cursor)
    populate_master_and_filter(cursor, inserted_total)
    post_sync_cleanup(cursor, config)

    logging.info("Database Sync completed successfully in %.2f minutes.", (time.time() - global_start) / 60)

# =====================================================================
# MAIN ROUTINE
# =====================================================================
def main():
    args = parse_args()
    setup_logging(args.log_level)
    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 5: PEP Consolidation & Database Sync [Started at %s] ===", start_time_str)
    global_start = time.time()

    config = load_config(args.config)
    conn = get_connection(config)
    cursor = conn.cursor()

    try:
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")

        action = args.action
        logging.info("Executing Mode / Action: %s", action)

        if action == "pep":
            run_pep(cursor, config)
        elif action == "sync":
            run_sync(cursor, config)
        else: # "all"
            run_pep(cursor, config)
            run_sync(cursor, config)

        elapsed_min = (time.time() - global_start) / 60
        end_time_str = datetime.now().strftime("%H:%M:%S")
        logging.info("=== Module 5: PEP Consolidation & Database Sync completed in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)
    except Exception as e:
        logging.error("Execution failed: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()

