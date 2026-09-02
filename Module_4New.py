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

    logging.info("=========================================================")
    logging.info("   MODULE 4: WATCHLIST CONSOLIDATION                     ")
    logging.info("   Start Time: %s", start_time_str)
    logging.info("=========================================================")

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
        cursor.execute(f"USE [{db['name']}]")
        cursor.execute("CHECKPOINT")
    except Exception:
        pass

    logging.info("[Step 1/4] Creating staging indexes for fast consolidation...")
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
        except Exception:
            pass

    logging.info("[Step 1/4] Staging indexes verified in %.2f seconds.", time.time() - index_start)

    logging.info("[Step 2/4] Setting up calculation table dbo.NegativeList_New1...")
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

    logging.info("[Step 2/4] Calculation staging table schema ready.")

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
        entity_source = f"(SELECT TOP ({ROW_LIMIT}) * FROM Entity WITH (NOLOCK) ORDER BY EntityGUID)"
    else:
        entity_source = "Entity"

    logging.info("[Step 3/4] Consolidating Non-PEP watchlist profiles (Fix 1 & Fix 2 Applied)...")
    stage1_start = time.time()
    cursor.execute(f"""
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
            CAST(SUBSTRING(
                CASE 
                    WHEN NULLIF(LTRIM(RTRIM(A.FirstName)), '') IS NULL AND NULLIF(LTRIM(RTRIM(A.LastName)), '') IS NOT NULL 
                    THEN LTRIM(RTRIM(A.LastName))
                    ELSE LTRIM(RTRIM(ISNULL(A.FirstName, '') + ' ' + ISNULL(A.MiddleName, '')))
                END, 1, 4000) AS NVARCHAR(4000)) as FirstName,
            CAST(SUBSTRING(
                CASE 
                    WHEN NULLIF(LTRIM(RTRIM(A.FirstName)), '') IS NULL AND NULLIF(LTRIM(RTRIM(A.LastName)), '') IS NOT NULL 
                    THEN NULL
                    ELSE NULLIF(LTRIM(RTRIM(A.LastName)), '')
                END, 1, 250) AS NVARCHAR(250)) as LastName,
            CAST(SUBSTRING(REPLACE(ISNULL(A.Name, ''), ',', ''), 1, 500) AS NVARCHAR(500)) as SecondName,
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
        FROM {entity_source} A WITH (NOLOCK)
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
        OPTION (RECOMPILE)
    """)
    logging.info("[Step 3/4] Non-PEP profiles consolidated in %.2f seconds.", time.time() - stage1_start)

    logging.info("[Step 4/4] Consolidating Politically Exposed Persons (PEPs)...")
    stage2_start = time.time()
    cursor.execute(f"""
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
            CAST(SUBSTRING(
                CASE 
                    WHEN NULLIF(LTRIM(RTRIM(A.FirstName)), '') IS NULL AND NULLIF(LTRIM(RTRIM(A.LastName)), '') IS NOT NULL 
                    THEN LTRIM(RTRIM(A.LastName))
                    ELSE LTRIM(RTRIM(ISNULL(A.FirstName, '') + ' ' + ISNULL(A.MiddleName, '')))
                END, 1, 4000) AS NVARCHAR(4000)) as FirstName,
            CAST(SUBSTRING(
                CASE 
                    WHEN NULLIF(LTRIM(RTRIM(A.FirstName)), '') IS NULL AND NULLIF(LTRIM(RTRIM(A.LastName)), '') IS NOT NULL 
                    THEN NULL
                    ELSE NULLIF(LTRIM(RTRIM(A.LastName)), '')
                END, 1, 250) AS NVARCHAR(250)) as LastName,
            CAST(SUBSTRING(REPLACE(ISNULL(A.Name, ''), ',', ''), 1, 500) AS NVARCHAR(500)) as SecondName,
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
        FROM {entity_source} A WITH (NOLOCK)
        INNER JOIN #PEP_GUIDs p ON A.EntityGUID = p.EntityGUID
        LEFT JOIN EntityDOB_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        LEFT JOIN EntityAddress_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
        LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON A.EntityGUID = D.EntityGUID
        LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON A.EntityGUID = E.EntityGUID
        LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON A.EntityGUID = H.EntityGUID
        LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON A.EntityGUID = I.EntityGUID
        LEFT JOIN #TempNationalities J ON A.EntityGUID = J.EntityGUID
        LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON A.EntityGUID = K.EntityGUID
        OPTION (RECOMPILE)
    """)
    logging.info("[Step 4/4] PEP profiles consolidated in %.2f seconds.", time.time() - stage2_start)

    cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
    cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")

    cursor.execute("SELECT COUNT(*) FROM dbo.NegativeList_New1")
    total_base_rows = cursor.fetchone()[0]
    logging.info("[Step 4/4] Total Base Profiles in dbo.NegativeList_New1: %s rows.", f"{total_base_rows:,}")

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

    elapsed_min = (time.time() - global_start) / 60
    end_time_str = datetime.now().strftime("%H:%M:%S")

    logging.info("=========================================================")
    logging.info("   MODULE 4 COMPLETED SUCCESSFULLY                       ")
    logging.info("   End Time: %s | Duration: %.2f minutes", end_time_str, elapsed_min)
    logging.info("=========================================================")

if __name__ == "__main__":
    main()


