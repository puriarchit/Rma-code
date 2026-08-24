# -*- coding: utf-8 -*-
import sys
import json
import os
import pyodbc
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

def main():
    setup_logging()
    global_start = time.time()
    start_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Starting Module 4: Watchlist Consolidation [Started at %s] ===", start_time_str)

    config = load_config()
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"

    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()

    ROW_LIMIT = config.get("benchmark_row_limit", None)

    try:
        cursor.execute(f"ALTER DATABASE [{db['name']}] SET RECOVERY SIMPLE")
        cursor.execute(f"ALTER DATABASE [{db['name']}] MODIFY FILE (NAME = [{db['name']}], FILEGROWTH = 512MB)")
        cursor.execute(f"USE [{db['name']}]")
        
        obsolete_tables = [
            "AssociatedEntity", "ConsolidatedSanction", 
            "EntityAdverseMedia"
        ]
        for table in obsolete_tables:
            try:
                cursor.execute(f"TRUNCATE TABLE [{table}]")
            except Exception:
                pass
                
        cursor.execute("CHECKPOINT")
        logging.info("Staging table maintenance completed.")
    except Exception as ex:
        logging.warning("Maintenance note: %s", ex)

    logging.info("[1/4] Indexing staging tables...")
    index_start = time.time()

    index_queries = [
        ("IX_EntityDOB_New_EntityGUID", "EntityDOB_New", "EntityGUID"),
        ("IX_EntityAddress_New_EntityGUID", "EntityAddress_New", "EntityGUID"),
        ("IX_EntityIdentification_New_EntityGUID", "EntityIdentification_New", "EntityGUID"),
        ("IX_EntityIdentification_National_New_EntityGUID", "EntityIdentification_National_New", "EntityGUID"),
        ("IX_Entity_Citizenship_New_EntityGUID", "Entity_Citizenship_New", "EntityGUID"),
        ("IX_EntityRemark_New_EntityGUID", "EntityRemark_New", "EntityGUID"),
        ("IX_EntitySourceItem_New_EntityGUID", "EntitySourceItem_New", "EntityGUID")
    ]
    for idx_name, tbl_name, col_name in index_queries:
        try:
            cursor.execute(f"SELECT 1 FROM sys.indexes WHERE name = '{idx_name}'")
            if cursor.fetchone():
                continue
            cursor.execute(f"CREATE CLUSTERED INDEX [{idx_name}] ON [{tbl_name}]({col_name})")
        except Exception as ex:
            logging.warning("Index note on %s: %s", tbl_name, ex)

    logging.info("[1/4] Indexing completed in %.2f seconds.", time.time() - index_start)

    logging.info("[2/4] Setting up target table NegativeList_New1...")
    cursor.execute("IF OBJECT_ID('NegativeList_New1', 'U') IS NOT NULL DROP TABLE NegativeList_New1")
    cursor.execute("""
        CREATE TABLE [dbo].[NegativeList_New1](
            [ReferenceID] [nvarchar](50) NULL,
            [EntityType] [nvarchar](50) NULL,
            [Gender] [nvarchar](50) NULL,
            [FirstName] [nvarchar](300) NULL,
            [LastName] [nvarchar](255) NULL,
            [SecondName] [nvarchar](500) NULL,
            [Title] [nvarchar](500) NULL,
            [DOB] [nvarchar](92) NULL,
            [ALTDOB1] [datetime] NULL,
            [ALTDOB2] [datetime] NULL,
            [ALTDOB3] [datetime] NULL,
            [AddressLine1] [nvarchar](255) NULL,
            [AddressLine2] [nvarchar](255) NULL,
            [City] [nvarchar](50) NULL,
            [Country] [nvarchar](100) NULL,
            [WLType] [nvarchar](200) NULL,
            [OriginalSource] [nvarchar](4000) NULL,
            [Remark] [nvarchar](4000) NULL,
            [NationalIDInfo] [nvarchar](250) NULL,
            [NationalIDNo] [nvarchar](50) NULL,
            [IdOtherInfo1] [nvarchar](250) NULL,
            [IdNo1] [nvarchar](250) NULL,
            [IdOtherInfo2] [nvarchar](250) NULL,
            [IdNo2] [nvarchar](250) NULL,
            [IdOtherInfo3] [nvarchar](250) NULL,
            [IdNo3] [nvarchar](250) NULL,
            [IdOtherInfo4] [nvarchar](250) NULL,
            [IdNo4] [nvarchar](250) NULL,
            [IdOtherInfo5] [nvarchar](250) NULL,
            [IdNo5] [nvarchar](250) NULL,
            [EntityGUID] [nvarchar](50) NULL,
            [Nationality] [nvarchar](100) NULL,
            [Citizenship] [nvarchar](100) NULL,
            [POB] [nvarchar](50) NULL
        ) WITH (DATA_COMPRESSION = PAGE)
    """)

    try:
        cursor.execute("UPDATE STATISTICS Entity")
        cursor.execute("UPDATE STATISTICS EntityRemark_New")
        cursor.execute("UPDATE STATISTICS EntitySourceItem_New")
    except Exception as e:
        logging.warning("Statistics note: %s", e)

    logging.info("[2/4] Target table NegativeList_New1 setup completed.")

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

    # Database diagnostics to investigate remaining row count discrepancies
    try:
        cursor.execute("SELECT COUNT(DISTINCT EntityGUID) FROM #PEP_GUIDs")
        pep_guids_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM EntityCountryAssociation WHERE AssociationTypeDesc = 'PEP'")
        raw_pep_assoc_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM #TempNationalities")
        temp_nat_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT EntityGUID) FROM #TempNationalities")
        temp_nat_dist_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM EntityAddress_New")
        addr_new_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT EntityGUID) FROM EntityAddress_New")
        addr_new_dist_cnt = cursor.fetchone()[0]
        
        logging.info("=== DIAGNOSTICS ===")
        logging.info(f"Distinct PEP GUIDs in #PEP_GUIDs: {pep_guids_cnt}")
        logging.info(f"Raw 'PEP' rows in EntityCountryAssociation: {raw_pep_assoc_cnt}")
        logging.info(f"Total rows in #TempNationalities: {temp_nat_cnt}")
        logging.info(f"Distinct GUIDs in #TempNationalities: {temp_nat_dist_cnt}")
        logging.info(f"Total rows in EntityAddress_New: {addr_new_cnt}")
        logging.info(f"Distinct GUIDs in EntityAddress_New: {addr_new_dist_cnt}")
        logging.info("===================")
    except Exception as diag_ex:
        logging.warning("Failed to collect diagnostics: %s", diag_ex)

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

    # Load character translation map
    cursor.execute("SELECT Symbol, MapChar FROM dbo.WLCharMap")
    char_map = cursor.fetchall()
    
    def get_translate_sql(expr):
        sql = expr
        for sym, mc in char_map:
            sym_esc = sym.replace("'", "''")
            mc_esc = mc.replace("'", "''")
            sql = f"REPLACE({sql}, N'{sym_esc}', N'{mc_esc}')"
        return sql

    T_FirstName = get_translate_sql("ISNULL(A.FirstName,'') + ' ' + ISNULL(A.MiddleName,'')")
    T_LastName = get_translate_sql("ISNULL(A.LastName,'')")
    T_SecondName = get_translate_sql("ISNULL(A.Name,'')")

    FN_Expr = f"""CAST(SUBSTRING(
        CASE WHEN LEN(TRIM({T_FirstName})) < 1 AND LEN(TRIM({T_LastName})) > 0 
             THEN {T_LastName} 
             ELSE {T_FirstName} 
        END, 1, 4000) AS NVARCHAR(4000))"""

    LN_Expr = f"""CAST(SUBSTRING(
        CASE WHEN LEN(TRIM({T_FirstName})) < 1 AND LEN(TRIM({T_LastName})) > 0 
             THEN '' 
             ELSE {T_LastName} 
        END, 1, 250) AS NVARCHAR(250))"""

    SN_Expr = f"""CAST(SUBSTRING(
        REPLACE(REPLACE(REPLACE({T_SecondName}, '-', ' '), ',', ''), '''', ''), 1, 500) AS NVARCHAR(500))"""

    logging.info("[3/4] Executing watchlist consolidation into NegativeList_New1...")

    # Stage 1: Non-PEP Profiles
    logging.info("  [3/4] [Stage 1/2] Consolidating Non-PEP profiles...")
    stage1_start = time.time()
    cursor.execute(f"""
        {cte_prefix}
        INSERT INTO NegativeList_New1 WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, Nationality, Citizenship, POB
        )
        SELECT 
            CAST(SUBSTRING(A.EntityID, 1, 50) AS NVARCHAR(50)) as ReferenceID,
            CAST(SUBSTRING(A.EntityTypeDesc, 1, 50) AS NVARCHAR(50)) as EntityType,
            CAST(SUBSTRING(A.Gender, 1, 50) AS NVARCHAR(50)) as Gender,
            {FN_Expr} as FirstName,
            {LN_Expr} as LastName,
            {SN_Expr} as SecondName,
            CAST(SUBSTRING(A.Title, 1, 500) AS NVARCHAR(500)) as Title,
            B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3,
            C.AddressLine1, C.AddressLine2, C.City, C.Country,
            CAST(SUBSTRING(isnull(F.SourceName, G.SourceName), 1, 200) AS NVARCHAR(200)) as WLType,
            CAST(SUBSTRING(E.SourceURI, 1, 4000) AS NVARCHAR(4000)) as OriginalSource,
            D.Remark,
            H.IdentificationTypeDesc as NationalIDInfo,
            CAST(SUBSTRING(H.IdentificationNumber, 1, 50) AS NVARCHAR(50)) as NationalIDNo,
            I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
            A.EntityGUID,
            J.Nationality,
            K.Citizenship,
            C.POB
        {from_clause}
        LEFT JOIN #PEP_GUIDs p ON A.EntityGUID = p.EntityGUID
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
        WHERE (p.EntityGUID IS NULL AND isnull(F.SourceName, G.SourceName) IS NULL)
           OR isnull(F.SourceName, G.SourceName) IS NOT NULL
        OPTION (MERGE JOIN, RECOMPILE)
    """)
    # Stage 2: PEP Profiles
    logging.info("  [3/4] [Stage 2/2] Consolidating PEP profiles...")
    stage2_start = time.time()
    cursor.execute(f"""
        {cte_prefix}
        INSERT INTO NegativeList_New1 WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, Nationality, Citizenship, POB
        )
        SELECT 
            CAST(SUBSTRING(A.EntityID, 1, 50) AS NVARCHAR(50)) as ReferenceID,
            CAST(SUBSTRING(A.EntityTypeDesc, 1, 50) AS NVARCHAR(50)) as EntityType,
            CAST(SUBSTRING(A.Gender, 1, 50) AS NVARCHAR(50)) as Gender,
            {FN_Expr} as FirstName,
            {LN_Expr} as LastName,
            {SN_Expr} as SecondName,
            CAST(SUBSTRING(A.Title, 1, 500) AS NVARCHAR(500)) as Title,
            B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3,
            C.AddressLine1, C.AddressLine2, C.City, C.Country,
            'PEP' AS WLType,
            CAST(SUBSTRING(E.SourceURI, 1, 4000) AS NVARCHAR(4000)) as OriginalSource,
            D.Remark,
            H.IdentificationTypeDesc as NationalIDInfo,
            CAST(SUBSTRING(H.IdentificationNumber, 1, 50) AS NVARCHAR(50)) as NationalIDNo,
            I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
            A.EntityGUID,
            J.Nationality,
            K.Citizenship,
            C.POB
        {from_clause}
        INNER JOIN #PEP_GUIDs p ON A.EntityGUID = p.EntityGUID
        LEFT JOIN EntityDOB_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        LEFT JOIN EntityAddress_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
        LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON A.EntityGUID = D.EntityGUID
        LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON A.EntityGUID = E.EntityGUID
        --LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON A.EntityGUID = F.EntityGUID
        --LEFT JOIN EntitySanction G WITH (NOLOCK) ON A.EntityGUID = G.EntityGUID
        LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON A.EntityGUID = H.EntityGUID
        LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON A.EntityGUID = I.EntityGUID
        LEFT JOIN #TempNationalities J ON A.EntityGUID = J.EntityGUID
        LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON A.EntityGUID = K.EntityGUID
        OPTION (MERGE JOIN, RECOMPILE)
    """)
    logging.info("  [3/4] PEP profiles completed in %.2f seconds.", time.time() - stage2_start)

    cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
    cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")

    logging.info("[4/4] Cleaning up intermediate staging tables...")
    intermediate_tables = [
        "EntityAddress_New",
        "EntityDOB_New",
        "EntityIdentification_New",
        "EntityIdentification_National_New",
        "Entity_Citizenship_New",
        "EntityRemark_New",
        "EntitySourceItem_New"
    ]
    for tbl in intermediate_tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS dbo.[{tbl}]")
            logging.info("  Dropped intermediate table %s", tbl)
        except Exception as ex:
            logging.warning("  Could not drop %s: %s", tbl, ex)

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")
    logging.info("=== Module 4: Watchlist Consolidation completed successfully in %.2f minutes [Finished at %s] ===", elapsed_min, end_time_str)

if __name__ == "__main__":
    main()
