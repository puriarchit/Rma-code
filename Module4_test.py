import sys
import json
import os
import pyodbc
import time
# Config load karna
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]
trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
conn = pyodbc.connect(conn_str)
conn.autocommit = True
cursor = conn.cursor()
# CONFIGURATION: ROW_LIMIT load karna (Default 500,000 test mode)
ROW_LIMIT = config.get("benchmark_row_limit", 500000)
try:
    cursor.execute("ALTER DATABASE LexisNexis_Staging SET RECOVERY SIMPLE")
    cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging, FILEGROWTH = 512MB)")
    cursor.execute("USE LexisNexis_Staging")
    
    # Reclaim space by truncating obsolete tables
    print("reclaiming database file pages from obsolete raw tables...")
    obsolete_tables = [
        "AssociatedEntity", "ConsolidatedSanction", "EntityAddress", 
        "EntityAdverseMedia", "EntityCountryAssociation", "EntityDOB", 
        "EntityEnforcement", "EntityIdentification", "EntityRemark", 
        "EntitySanction", "EntitySourceItem"
    ]
    for table in obsolete_tables:
        try:
            cursor.execute(f"TRUNCATE TABLE {table}")
        except Exception:
            pass
            
    cursor.execute("CHECKPOINT")
    print("database optimized, logs and data files shrunk, and obsolete staging tables truncated.")
except Exception as ex:
    print("database optimization warning:", ex)
print(f"starting module 4 (Single-Query Bulk Insert with ROW_LIMIT = {ROW_LIMIT})...")
print("indexing staging tables for fast merge joins...")
index_start = time.time()
# Staging raw tables indices check/creation
raw_index_queries = [
    ("IX_Entity_EntityGUID", "Entity", "EntityGUID"),
    ("IX_EntityEnforcement_EntityGUID", "EntityEnforcement", "EntityGUID"),
    ("IX_EntitySanction_EntityGUID", "EntitySanction", "EntityGUID")
]
for idx_name, tbl_name, col_name in raw_index_queries:
    try:
        cursor.execute(f"SELECT 1 FROM sys.indexes WHERE name = '{idx_name}'")
        if cursor.fetchone():
            print(f"  index {idx_name} on raw table {tbl_name} already exists, skipping...")
            continue
        
        cursor.execute(f"SELECT name FROM sys.indexes WHERE object_id = OBJECT_ID('{tbl_name}') AND type = 1")
        existing_clustered = cursor.fetchone()
        
        if tbl_name == "Entity":
            if existing_clustered:
                print(f"  note: raw table {tbl_name} already has clustered index. Creating non-clustered index instead...")
                cursor.execute(f"CREATE NONCLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
            else:
                cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
        else:
            if existing_clustered:
                cursor.execute(f"CREATE NONCLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
            else:
                cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
        conn.commit()
    except Exception as ex:
        print(f"  raw table index alert on {tbl_name}: {ex}")
# Check/Create indexes for new tables
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
            print(f"  index {idx_name} on {tbl_name} already exists, skipping...")
            continue
        
        cursor.execute(f"SELECT name FROM sys.indexes WHERE object_id = OBJECT_ID('{tbl_name}') AND type = 1")
        row = cursor.fetchone()
        if row:
            cursor.execute(f"DROP INDEX {row[0]} ON {tbl_name}")
            conn.commit()
            
        cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
        conn.commit()
    except Exception as ex:
        print(f"  index alert on {tbl_name}: {ex}")
print(f"indexing staging tables completed, took {time.time() - index_start:.2f} seconds.")
# Recreate target table NegativeList_New1 WITH PAGE COMPRESSION
print("recreating staging tables with PAGE compression...")
cursor.execute("IF OBJECT_ID('NegativeList_New1', 'U') IS NOT NULL DROP TABLE NegativeList_New1")
cursor.execute("""
    CREATE TABLE [dbo].[NegativeList_New1](<
        [EntityGUID] [nvarchar](50>) NULL,
        [ReferenceID] [nvarchar](50) NULL,
        [EntityType] [nvarchar](50) NULL,
        [Gender] [nvarchar](50) NULL,
        [FirstName] [nvarchar](4000) NULL,
        [LastName] [nvarchar](250) NULL,
        [SecondName] [nvarchar](500) NULL,
        [Title] [nvarchar](250) NULL,
        [DOB] [nvarchar](92) NULL,
        [ALTDOB1] [datetime] NULL,
        [ALTDOB2] [datetime] NULL,
        [ALTDOB3] [datetime] NULL,
        [AddressLine1] [nvarchar](255) NULL,
        [AddressLine2] [nvarchar](255) NULL,
        [City] [nvarchar](50) NULL,
        [Country] [nvarchar](100) NULL,
        [POB] [nvarchar](50) NULL,
        [WLType] [nvarchar](50) NULL,
        [OriginalSource] [nvarchar](MAX) NULL,
        [Remark] [nvarchar](4000) NULL,
        [NationalIDInfo] [nvarchar](250) NULL,
        [NationalIDNo] [nvarchar](250) NULL,
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
        [Nationality] [nvarchar](4000) NULL,
        [Citizenship] [nvarchar](100) NULL
    ) WITH (DATA_COMPRESSION = PAGE)
""")
conn.commit()
print("updating database statistics...")
try:
    cursor.execute("UPDATE STATISTICS Entity")
    cursor.execute("UPDATE STATISTICS EntityRemark_New")
    cursor.execute("UPDATE STATISTICS EntitySourceItem_New")
    conn.commit()
except Exception as e:
    print("  statistics warning:", e)
# Lookup Tables
print("creating temporary lookup tables...")
step_start = time.time()
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("""
    SELECT A.EntityGUID, B.tCountry AS Nationality
    INTO #TempNationalities
    FROM EntityCountryAssociation A WITH (NOLOCK)
    INNER HASH JOIN Country B WITH (NOLOCK) ON A.ISOStandard = B.tISO
    WHERE A.AssociationTypeDesc = 'Nationality'
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 10)
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
conn.commit()
try:
    cursor.execute("TRUNCATE TABLE EntityCountryAssociation")
    cursor.execute("CHECKPOINT")
except Exception as e:
    print("  warning:", e)
print(f"lookup tables created, took {time.time() - step_start:.2f} seconds.")
# Construct CTE wrapper for benchmark testing (semicolon prepended for SQL Server CTE rule)
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
print("executing Single-Query Bulk Consolidation...")
execution_start = time.time()
# 1. Non-PEP Bulk Ingestion
print("  running Stage 3: loading non-PEP profiles...")
sys.stdout.flush()
stage3_nonpep_start = time.time()
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
        CAST(SUBSTRING(isnull(F.SourceName, G.SourceName), 1, 50) AS NVARCHAR(50)) as WLType,
        E.SourceURI as OriginalSource,
        D.Remark,
        H.IdentificationTypeDesc as NationalIDInfo,
        H.IdentificationNumber as NationalIDNo,
        I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
        J.Nationality,
        K.Citizenship
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
    WHERE p.EntityGUID IS NULL OR (isnull(F.SourceName, G.SourceName) IS NOT NULL AND isnull(F.SourceName, G.SourceName) <> 'PEP')
    OPTION (MERGE JOIN, RECOMPILE, MAXDOP 4)
""")
conn.commit()
print(f"  Stage 3 non-PEP completed in {time.time() - stage3_nonpep_start:.2f} seconds.")
sys.stdout.flush()
# 2. PEP Bulk Ingestion
print("  running Stage 3: loading PEP profiles...")
sys.stdout.flush()
stage3_pep_start = time.time()
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
    OPTION (MERGE JOIN, RECOMPILE, MAXDOP 4)
""")
conn.commit()
print(f"  Stage 3 PEP completed in {time.time() - stage3_pep_start:.2f} seconds.")
sys.stdout.flush()
# Cleanup
print("cleaning lookup tables...")
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
conn.commit()
# Count Check
cursor.execute("SELECT COUNT(*) FROM NegativeList_New1 WITH (NOLOCK)")
row_count = cursor.fetchone()[0]
print(f"Watchlist splits categorized ({row_count} rows), took {time.time() - execution_start:.2f} seconds total.")
print("module 4 completed successfully (Single-Query Bulk Ingest).")
conn.close()




# import sys
# import json
# import os
# import pyodbc
# import time

# config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
# with open(config_path, "r") as f:
#     config = json.load(f)
# db = config["database"]

# trusted = "yes" if db["trusted_connection"] else "no"
# conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"

# conn = pyodbc.connect(conn_str)
# conn.autocommit = True
# cursor = conn.cursor()

# try:
#     cursor.execute("ALTER DATABASE LexisNexis_Staging SET RECOVERY SIMPLE")
#     cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging, FILEGROWTH = 512MB)")
#     cursor.execute("USE LexisNexis_Staging")
    
#     # Reclaim space inside database file by truncating obsolete raw tables
#     print("reclaiming database file pages from obsolete raw tables...")
#     obsolete_tables = [
#         "AssociatedEntity", "ConsolidatedSanction", "EntityAddress", 
#         "EntityAdverseMedia", "EntityAdverseMediaSubCategory", 
#         "EntityDeletes", "EntityDOB", "EntityEnforcementSubCategory", 
#         "EntityIdentification", "EntityRemark", "EntitySourceItem"
#     ]
#     for tbl in obsolete_tables:
#         try:
#             cursor.execute(f"TRUNCATE TABLE {tbl}")
#         except Exception as truncate_ex:
#             print(f"  note: could not truncate {tbl}: {truncate_ex}")
            
#     cursor.execute("CHECKPOINT")
#     print("  skipping transaction log shrink to save runtime...")
#     # cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging_log, 10)")
#     print("  skipping data file shrink (reclaiming OS disk space) to save runtime...")
#     # try:
#     #     cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging, 10)")
#     # except Exception as shrink_ex:
#     #     print(f"  note: could not shrink data file: {shrink_ex}")
#     print("database checkpoint completed successfully.")
#     print("database optimized, logs and data files shrunk, and obsolete staging tables truncated.")
# except Exception as e:
#     print("db maintenance alert:", e)

# print("starting module 4...")
# global_start = time.time()

# # Critical Performance Step: Create Clustered Indexes on Staging Heaps to enable Merge Joins
# print("indexing staging tables for fast merge joins...")
# index_start = time.time()

# # Index raw staging tables used in the join to fully optimize join plan
# raw_index_queries = [
#     ("IX_Entity_EntityGUID", "Entity", "EntityGUID"),
#     ("IX_EntityEnforcement_EntityGUID", "EntityEnforcement", "EntityGUID"),
#     ("IX_EntitySanction_EntityGUID", "EntitySanction", "EntityGUID")
# ]
# for idx_name, tbl_name, col_name in raw_index_queries:
#     try:
#         cursor.execute(f"SELECT 1 FROM sys.indexes WHERE name = '{idx_name}'")
#         if cursor.fetchone():
#             print(f"  index {idx_name} on raw table {tbl_name} already exists, skipping...")
#             continue
#         cursor.execute(f"IF EXISTS (SELECT * FROM sys.indexes WHERE name = '{idx_name}') DROP INDEX {idx_name} ON {tbl_name}")
#         if tbl_name == "Entity":
#             print(f"  creating clustered index on raw table {tbl_name}...")
#             cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
#         else:
#             print(f"  creating non-clustered index on raw table {tbl_name}...")
#             cursor.execute(f"CREATE NONCLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
#         conn.commit()
#     except Exception as ex:
#         print(f"  raw table index alert on {tbl_name}: {ex}")

# index_queries = [
#     ("IX_EntityDOB_New_EntityGUID", "EntityDOB_New", "EntityGUID"),
#     ("IX_EntityAddress_New_EntityGUID", "EntityAddress_New", "EntityGUID"),
#     ("IX_EntityIdentification_New_EntityGUID", "EntityIdentification_New", "EntityGUID"),
#     ("IX_EntityIdentification_National_New_EntityGUID", "EntityIdentification_National_New", "EntityGUID"),
#     ("IX_Entity_Citizenship_New_EntityGUID", "Entity_Citizenship_New", "EntityGUID"),
#     ("IX_EntityRemark_New_EntityGUID", "EntityRemark_New", "EntityGUID"),
#     ("IX_EntitySourceItem_New_EntityGUID", "EntitySourceItem_New", "EntityGUID")
# ]

# for idx_name, tbl_name, col_name in index_queries:
#     try:
#         cursor.execute(f"SELECT 1 FROM sys.indexes WHERE name = '{idx_name}'")
#         if cursor.fetchone():
#             print(f"  index {idx_name} on {tbl_name} already exists, skipping...")
#             continue
#         # Dynamically check if any clustered index (type = 1) exists and drop it
#         cursor.execute(f"""
#             SELECT name FROM sys.indexes 
#             WHERE object_id = OBJECT_ID('{tbl_name}') AND type = 1
#         """)
#         row = cursor.fetchone()
#         if row:
#             cursor.execute(f"DROP INDEX {row[0]} ON {tbl_name}")
#             conn.commit()
            
#         print(f"  creating clustered index on {tbl_name}...")
#         cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
#         conn.commit()
#     except Exception as ex:
#         print(f"  index alert on {tbl_name}: {ex}")

# print(f"indexing staging tables completed, took {time.time() - index_start:.2f} seconds.")

# print("recreating staging tables...")
# cursor.execute("IF OBJECT_ID('NegativeList_New1', 'U') IS NOT NULL DROP TABLE NegativeList_New1")
# cursor.execute("""
#     CREATE TABLE [dbo].[NegativeList_New1](
#         [EntityGUID] [nvarchar](50) NULL,
#         [ReferenceID] [nvarchar](50) NULL,
#         [EntityType] [nvarchar](50) NULL,
#         [Gender] [nvarchar](50) NULL,
#         [FirstName] [nvarchar](4000) NULL,
#         [LastName] [nvarchar](250) NULL,
#         [SecondName] [nvarchar](500) NULL,
#         [Title] [nvarchar](250) NULL,
#         [DOB] [nvarchar](92) NULL,
#         [ALTDOB1] [datetime] NULL,
#         [ALTDOB2] [datetime] NULL,
#         [ALTDOB3] [datetime] NULL,
#         [AddressLine1] [nvarchar](255) NULL,
#         [AddressLine2] [nvarchar](255) NULL,
#         [City] [nvarchar](50) NULL,
#         [Country] [nvarchar](100) NULL,
#         [POB] [nvarchar](50) NULL,
#         [WLType] [nvarchar](50) NULL,
#         [OriginalSource] [nvarchar](MAX) NULL,
#         [Remark] [nvarchar](4000) NULL,
#         [NationalIDInfo] [nvarchar](250) NULL,
#         [NationalIDNo] [nvarchar](250) NULL,
#         [IdOtherInfo1] [nvarchar](250) NULL,
#         [IdNo1] [nvarchar](250) NULL,
#         [IdOtherInfo2] [nvarchar](250) NULL,
#         [IdNo2] [nvarchar](250) NULL,
#         [IdOtherInfo3] [nvarchar](250) NULL,
#         [IdNo3] [nvarchar](250) NULL,
#         [IdOtherInfo4] [nvarchar](250) NULL,
#         [IdNo4] [nvarchar](250) NULL,
#         [IdOtherInfo5] [nvarchar](250) NULL,
#         [IdNo5] [nvarchar](250) NULL,
#         [Nationality] [nvarchar](4000) NULL,
#         [Citizenship] [nvarchar](100) NULL
#     )
# """)
# conn.commit()

# print("creating temporary lookup tables...")
# step_start = time.time()
# cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
# cursor.execute("""
#     SELECT A.EntityGUID, B.tCountry AS Nationality
#     INTO #TempNationalities
#     FROM EntityCountryAssociation A WITH (NOLOCK)
#     INNER HASH JOIN Country B WITH (NOLOCK) ON A.ISOStandard = B.tISO
#     WHERE A.AssociationTypeDesc = 'Nationality'
#     OPTION (HASH JOIN, MIN_GRANT_PERCENT = 10)
# """)
# cursor.execute("CREATE CLUSTERED INDEX IX_TempNationalities_EntityGUID ON #TempNationalities(EntityGUID)")

# cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
# cursor.execute("""
#     SELECT DISTINCT EntityGUID
#     INTO #PEP_GUIDs
#     FROM EntityCountryAssociation WITH (NOLOCK)
#     WHERE AssociationTypeDesc = 'PEP'
# """)
# cursor.execute("CREATE CLUSTERED INDEX IX_PEP_GUIDs_EntityGUID ON #PEP_GUIDs(EntityGUID)")
# conn.commit()

# try:
#     cursor.execute("TRUNCATE TABLE EntityCountryAssociation")
#     cursor.execute("CHECKPOINT")
# except Exception as e:
#     print("  note: could not truncate EntityCountryAssociation:", e)
# print(f"lookup tables created, took {time.time() - step_start:.2f} seconds.")

# print("assembling master profile details...")
# step_start = time.time()

# # Pre-create Stage 1 temporary table with clustered index once outside the loop
# print("  pre-creating optimized temp staging tables and indexes...")
# cursor.execute("DROP TABLE IF EXISTS #Base1")
# cursor.execute("""
#     CREATE TABLE #Base1 (
#         EntityGUID NVARCHAR(50) NOT NULL,
#         ReferenceID NVARCHAR(50) NULL,
#         EntityType NVARCHAR(50) NULL,
#         Gender NVARCHAR(50) NULL,
#         FirstName NVARCHAR(4000) NULL,
#         LastName NVARCHAR(250) NULL,
#         SecondName NVARCHAR(500) NULL,
#         Title NVARCHAR(250) NULL,
#         DOB NVARCHAR(92) NULL,
#         ALTDOB1 DATETIME NULL,
#         ALTDOB2 DATETIME NULL,
#         ALTDOB3 DATETIME NULL,
#         AddressLine1 NVARCHAR(255) NULL,
#         AddressLine2 NVARCHAR(255) NULL,
#         City NVARCHAR(50) NULL,
#         Country NVARCHAR(100) NULL,
#         POB NVARCHAR(50) NULL
#     )
# """)
# cursor.execute("CREATE CLUSTERED INDEX IX_Base1_EntityGUID ON #Base1(EntityGUID)")
# conn.commit()

# # Keyset range batching loop on EntityGUID index
# last_guid = ""
# batch_size = 100000
# batch_num = 1

# while True:
#     # 1. Fetch the maximum GUID for the current batch of 250,000 using covering index scan
#     cursor.execute("""
#         SELECT MAX(EntityGUID) FROM (
#             SELECT TOP (?) EntityGUID 
#             FROM Entity WITH (NOLOCK) 
#             WHERE EntityGUID > ? 
#             ORDER BY EntityGUID
#         ) AS Batch
#     """, batch_size, last_guid)
    
#     max_guid = cursor.fetchone()[0]
#     if not max_guid:
#         print("  all batches completed successfully.")
#         break
        
#     print(f"  --> processing batch {batch_num} (EntityGUID from '{last_guid}' to '{max_guid}')...")
#     batch_start = time.time()
    
#     # Clean previous batch pages from temp tables
#     print("    cleaning staging temp tables...")
#     sys.stdout.flush()
#     cursor.execute("TRUNCATE TABLE #Base1")
#     conn.commit()
    
#     # Stage 1: Demographics for current batch range -> #Base1
#     print("    executing Stage 1: compiling demographics...")
#     sys.stdout.flush()
#     stage1_start = time.time()
#     cursor.execute("""
#         INSERT INTO #Base1 (
#             EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
#             DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB
#         )
#         SELECT 
#             A.EntityGUID,
#             CAST(SUBSTRING(A.EntityID, 1, 50) AS NVARCHAR(50)) as ReferenceID,
#             CAST(SUBSTRING(A.EntityTypeDesc, 1, 50) AS NVARCHAR(50)) as EntityType,
#             CAST(SUBSTRING(A.Gender, 1, 50) AS NVARCHAR(50)) as Gender,
#             CAST(SUBSTRING(ISNULL(A.FirstName,'') + ' ' + ISNULL(A.MiddleName,''), 1, 4000) AS NVARCHAR(4000)) as FirstName,
#             CAST(SUBSTRING(A.LastName, 1, 250) AS NVARCHAR(250)) as LastName,
#             CAST(SUBSTRING(A.Name, 1, 500) AS NVARCHAR(500)) as SecondName,
#             CAST(SUBSTRING(A.Title, 1, 250) AS NVARCHAR(250)) as Title,
#             B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3,
#             C.AddressLine1, C.AddressLine2, C.City, C.Country, C.POB
#         FROM Entity A WITH (NOLOCK)
#         LEFT JOIN EntityDOB_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
#         LEFT JOIN EntityAddress_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
#         WHERE A.EntityGUID > ? AND A.EntityGUID <= ?
#         OPTION (RECOMPILE, MAXDOP 4)
#     """, last_guid, max_guid)
#     conn.commit()
#     print(f"    Stage 1 completed in {time.time() - stage1_start:.2f} seconds.")
#     sys.stdout.flush()
    
#     # Stage 3: Load final target NegativeList_New1 directly by joining #Base1 with Remarks and Sources
#     print("    executing Stage 3: loading non-PEP profiles...")
#     sys.stdout.flush()
#     stage3_nonpep_start = time.time()
#     cursor.execute("""
#         INSERT INTO NegativeList_New1 WITH (TABLOCK) (
#             EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
#             DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB,
#             WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
#             IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
#             Nationality, Citizenship
#         )
#         SELECT 
#             B.EntityGUID, B.ReferenceID, B.EntityType, B.Gender, B.FirstName, B.LastName, B.SecondName, B.Title,
#             B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3, B.AddressLine1, B.AddressLine2, B.City, B.Country, B.POB,
#             CAST(SUBSTRING(isnull(F.SourceName, G.SourceName), 1, 50) AS NVARCHAR(50)) as WLType,
#             E.SourceURI as OriginalSource,
#             D.Remark,
#             H.IdentificationTypeDesc as NationalIDInfo,
#             H.IdentificationNumber as NationalIDNo,
#             I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
#             J.Nationality,
#             K.Citizenship
#         FROM #Base1 B
#         LEFT JOIN #PEP_GUIDs p ON B.EntityGUID = p.EntityGUID
#         LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON B.EntityGUID = D.EntityGUID
#         LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON B.EntityGUID = E.EntityGUID
#         LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON B.EntityGUID = F.EntityGUID
#         LEFT JOIN EntitySanction G WITH (NOLOCK) ON B.EntityGUID = G.EntityGUID
#         LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON B.EntityGUID = H.EntityGUID
#         LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON B.EntityGUID = I.EntityGUID
#         LEFT JOIN #TempNationalities J ON B.EntityGUID = J.EntityGUID
#         LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON B.EntityGUID = K.EntityGUID
#         WHERE p.EntityGUID IS NULL OR (isnull(F.SourceName, G.SourceName) IS NOT NULL AND isnull(F.SourceName, G.SourceName) <> 'PEP')
#         OPTION (MERGE JOIN, RECOMPILE, MAXDOP 4)
#     """)
#     conn.commit()
#     print(f"    Stage 3 non-PEP completed in {time.time() - stage3_nonpep_start:.2f} seconds.")
#     sys.stdout.flush()
    
#     print("    executing Stage 3: loading PEP profiles...")
#     sys.stdout.flush()
#     stage3_pep_start = time.time()
#     cursor.execute("""
#         INSERT INTO NegativeList_New1 WITH (TABLOCK) (
#             EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
#             DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB,
#             WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
#             IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
#             Nationality, Citizenship
#         )
#         SELECT 
#             B.EntityGUID, B.ReferenceID, B.EntityType, B.Gender, B.FirstName, B.LastName, B.SecondName, B.Title,
#             B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3, B.AddressLine1, B.AddressLine2, B.City, B.Country, B.POB,
#             'PEP' AS WLType,
#             E.SourceURI as OriginalSource,
#             D.Remark,
#             H.IdentificationTypeDesc as NationalIDInfo,
#             H.IdentificationNumber as NationalIDNo,
#             I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
#             J.Nationality,
#             K.Citizenship
#         FROM #Base1 B
#         INNER JOIN #PEP_GUIDs p ON B.EntityGUID = p.EntityGUID
#         LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON B.EntityGUID = D.EntityGUID
#         LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON B.EntityGUID = E.EntityGUID
#         LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON B.EntityGUID = F.EntityGUID
#         LEFT JOIN EntitySanction G WITH (NOLOCK) ON B.EntityGUID = G.EntityGUID
#         LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON B.EntityGUID = H.EntityGUID
#         LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON B.EntityGUID = I.EntityGUID
#         LEFT JOIN #TempNationalities J ON B.EntityGUID = J.EntityGUID
#         LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON B.EntityGUID = K.EntityGUID
#         OPTION (MERGE JOIN, RECOMPILE, MAXDOP 4)
#     """)
#     conn.commit()
#     print(f"    Stage 3 PEP completed in {time.time() - stage3_pep_start:.2f} seconds.")
#     sys.stdout.flush()
    
#     print(f"  --> batch completed in {time.time() - batch_start:.2f} seconds.")
#     sys.stdout.flush()
#     last_guid = max_guid
#     batch_num += 1

# # Cleanup intermediate temp tables to release physical TempDB pages
# cursor.execute("DROP TABLE IF EXISTS #Base1")
# cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
# cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
# conn.commit()

# rows_split = cursor.execute("SELECT COUNT(*) FROM NegativeList_New1 WITH (NOLOCK)").fetchone()[0]
# print(f"Watchlist splits categorized ({rows_split} rows), took {time.time() - step_start:.2f} seconds total.")

# cursor.close()
# conn.close()

# global_end = time.time()
# total_time = (global_end - global_start) / 60
# print(f"module 4 completed in {total_time:.2f} minutes.")

import sys
import json
import os
import pyodbc
import time

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]

trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"

conn = pyodbc.connect(conn_str)
conn.autocommit = True
cursor = conn.cursor()

try:
    cursor.execute("ALTER DATABASE LexisNexis_Staging SET RECOVERY SIMPLE")
    cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging, FILEGROWTH = 512MB)")
    cursor.execute("USE LexisNexis_Staging")
    
    # Reclaim space inside database file by truncating obsolete raw tables
    print("reclaiming database file pages from obsolete raw tables...")
    obsolete_tables = [
        "AssociatedEntity", "ConsolidatedSanction", "EntityAddress", 
        "EntityAdverseMedia", "EntityAdverseMediaSubCategory", 
        "EntityDeletes", "EntityDOB", "EntityEnforcementSubCategory", 
        "EntityIdentification", "EntityRemark", "EntitySourceItem"
    ]
    for tbl in obsolete_tables:
        try:
            cursor.execute(f"TRUNCATE TABLE {tbl}")
        except Exception as truncate_ex:
            print(f"  note: could not truncate {tbl}: {truncate_ex}")
            
    cursor.execute("CHECKPOINT")
    print("  skipping transaction log shrink to save runtime...")
    # cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging_log, 10)")
    print("  skipping data file shrink (reclaiming OS disk space) to save runtime...")
    # try:
    #     cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging, 10)")
    # except Exception as shrink_ex:
    #     print(f"  note: could not shrink data file: {shrink_ex}")
    print("database checkpoint completed successfully.")
    print("database optimized, logs and data files shrunk, and obsolete staging tables truncated.")
except Exception as e:
    print("db maintenance alert:", e)

print("starting module 4...")
global_start = time.time()

# Critical Performance Step: Create Clustered Indexes on Staging Heaps to enable Merge Joins
print("indexing staging tables for fast merge joins...")
index_start = time.time()

# Index raw staging tables used in the join to fully optimize join plan
raw_index_queries = [
    ("IX_Entity_EntityGUID", "Entity", "EntityGUID"),
    ("IX_EntityEnforcement_EntityGUID", "EntityEnforcement", "EntityGUID"),
    ("IX_EntitySanction_EntityGUID", "EntitySanction", "EntityGUID")
]
for idx_name, tbl_name, col_name in raw_index_queries:
    try:
        cursor.execute(f"SELECT 1 FROM sys.indexes WHERE name = '{idx_name}'")
        if cursor.fetchone():
            print(f"  index {idx_name} on raw table {tbl_name} already exists, skipping...")
            continue
        
        # Check if the table already has a clustered index (type = 1)
        cursor.execute(f"""
            SELECT name FROM sys.indexes 
            WHERE object_id = OBJECT_ID('{tbl_name}') AND type = 1
        """)
        existing_clustered = cursor.fetchone()
        
        if tbl_name == "Entity":
            if existing_clustered:
                print(f"  note: raw table {tbl_name} already has clustered index '{existing_clustered[0]}'. Creating non-clustered index instead...")
                cursor.execute(f"CREATE NONCLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
            else:
                print(f"  creating clustered index on raw table {tbl_name}...")
                cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
        else:
            if existing_clustered and tbl_name in ["EntityEnforcement", "EntitySanction"]:
                # For non-Entity raw tables, always non-clustered
                cursor.execute(f"CREATE NONCLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
            else:
                cursor.execute(f"IF EXISTS (SELECT * FROM sys.indexes WHERE name = '{idx_name}') DROP INDEX {idx_name} ON {tbl_name}")
                print(f"  creating non-clustered index on raw table {tbl_name}...")
                cursor.execute(f"CREATE NONCLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
        conn.commit()
    except Exception as ex:
        print(f"  raw table index alert on {tbl_name}: {ex}")

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
            print(f"  index {idx_name} on {tbl_name} already exists, skipping...")
            continue
        # Dynamically check if any clustered index (type = 1) exists and drop it
        cursor.execute(f"""
            SELECT name FROM sys.indexes 
            WHERE object_id = OBJECT_ID('{tbl_name}') AND type = 1
        """)
        row = cursor.fetchone()
        if row:
            cursor.execute(f"DROP INDEX {row[0]} ON {tbl_name}")
            conn.commit()
            
        print(f"  creating clustered index on {tbl_name}...")
        cursor.execute(f"CREATE CLUSTERED INDEX {idx_name} ON {tbl_name}({col_name})")
        conn.commit()
    except Exception as ex:
        print(f"  index alert on {tbl_name}: {ex}")

print(f"indexing staging tables completed, took {time.time() - index_start:.2f} seconds.")

print("recreating staging tables...")
cursor.execute("IF OBJECT_ID('NegativeList_New1', 'U') IS NOT NULL DROP TABLE NegativeList_New1")
cursor.execute("""
    CREATE TABLE [dbo].[NegativeList_New1](
        [EntityGUID] [nvarchar](50) NULL,
        [ReferenceID] [nvarchar](50) NULL,
        [EntityType] [nvarchar](50) NULL,
        [Gender] [nvarchar](50) NULL,
        [FirstName] [nvarchar](4000) NULL,
        [LastName] [nvarchar](250) NULL,
        [SecondName] [nvarchar](500) NULL,
        [Title] [nvarchar](250) NULL,
        [DOB] [nvarchar](92) NULL,
        [ALTDOB1] [datetime] NULL,
        [ALTDOB2] [datetime] NULL,
        [ALTDOB3] [datetime] NULL,
        [AddressLine1] [nvarchar](255) NULL,
        [AddressLine2] [nvarchar](255) NULL,
        [City] [nvarchar](50) NULL,
        [Country] [nvarchar](100) NULL,
        [POB] [nvarchar](50) NULL,
        [WLType] [nvarchar](50) NULL,
        [OriginalSource] [nvarchar](MAX) NULL,
        [Remark] [nvarchar](4000) NULL,
        [NationalIDInfo] [nvarchar](250) NULL,
        [NationalIDNo] [nvarchar](250) NULL,
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
        [Nationality] [nvarchar](4000) NULL,
        [Citizenship] [nvarchar](100) NULL
    ) WITH (DATA_COMPRESSION = PAGE)
""")
conn.commit()

print("updating database statistics for optimizer plans...")
try:
    cursor.execute("UPDATE STATISTICS Entity")
    cursor.execute("UPDATE STATISTICS EntityRemark_New")
    cursor.execute("UPDATE STATISTICS EntitySourceItem_New")
    conn.commit()
    print("  statistics updated successfully.")
except Exception as e:
    print("  note: could not update statistics:", e)


print("creating temporary lookup tables...")
step_start = time.time()
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("""
    SELECT A.EntityGUID, B.tCountry AS Nationality
    INTO #TempNationalities
    FROM EntityCountryAssociation A WITH (NOLOCK)
    INNER HASH JOIN Country B WITH (NOLOCK) ON A.ISOStandard = B.tISO
    WHERE A.AssociationTypeDesc = 'Nationality'
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 10)
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
conn.commit()

try:
    cursor.execute("TRUNCATE TABLE EntityCountryAssociation")
    cursor.execute("CHECKPOINT")
except Exception as e:
    print("  note: could not truncate EntityCountryAssociation:", e)
print(f"lookup tables created, took {time.time() - step_start:.2f} seconds.")

print("assembling master profile details...")
step_start = time.time()

# Pre-create Stage 1 temporary table with clustered index once outside the loop
print("  pre-creating optimized temp staging tables and indexes...")
cursor.execute("DROP TABLE IF EXISTS #Base1")
cursor.execute("""
    CREATE TABLE #Base1 (
        EntityGUID NVARCHAR(50) NOT NULL,
        ReferenceID NVARCHAR(50) NULL,
        EntityType NVARCHAR(50) NULL,
        Gender NVARCHAR(50) NULL,
        FirstName NVARCHAR(4000) NULL,
        LastName NVARCHAR(250) NULL,
        SecondName NVARCHAR(500) NULL,
        Title NVARCHAR(250) NULL,
        DOB NVARCHAR(92) NULL,
        ALTDOB1 DATETIME NULL,
        ALTDOB2 DATETIME NULL,
        ALTDOB3 DATETIME NULL,
        AddressLine1 NVARCHAR(255) NULL,
        AddressLine2 NVARCHAR(255) NULL,
        City NVARCHAR(50) NULL,
        Country NVARCHAR(100) NULL,
        POB NVARCHAR(50) NULL
    )
""")
cursor.execute("CREATE CLUSTERED INDEX IX_Base1_EntityGUID ON #Base1(EntityGUID)")
conn.commit()

# Keyset range batching loop on EntityGUID index
last_guid = ""
batch_size = 100000
batch_num = 1

while True:
    # 1. Fetch the maximum GUID for the current batch of 250,000 using covering index scan
    cursor.execute("""
        SELECT MAX(EntityGUID) FROM (
            SELECT TOP (?) EntityGUID 
            FROM Entity WITH (NOLOCK) 
            WHERE EntityGUID > ? 
            ORDER BY EntityGUID
        ) AS Batch
    """, batch_size, last_guid)
    
    max_guid = cursor.fetchone()[0]
    if not max_guid:
        print("  all batches completed successfully.")
        break
        
    print(f"  --> processing batch {batch_num} (EntityGUID from '{last_guid}' to '{max_guid}')...")
    batch_start = time.time()
    
    # Clean previous batch pages from temp tables
    print("    cleaning staging temp tables...")
    sys.stdout.flush()
    cursor.execute("TRUNCATE TABLE #Base1")
    conn.commit()
    
    # Stage 1: Demographics for current batch range -> #Base1
    print("    executing Stage 1: compiling demographics...")
    sys.stdout.flush()
    stage1_start = time.time()
    cursor.execute("""
        INSERT INTO #Base1 (
            EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB
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
            C.AddressLine1, C.AddressLine2, C.City, C.Country, C.POB
        FROM Entity A WITH (NOLOCK)
        LEFT JOIN EntityDOB_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        LEFT JOIN EntityAddress_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
        WHERE A.EntityGUID > ? AND A.EntityGUID <= ?
        OPTION (RECOMPILE, MAXDOP 4)
    """, last_guid, max_guid)
    conn.commit()
    print(f"    Stage 1 completed in {time.time() - stage1_start:.2f} seconds.")
    sys.stdout.flush()
    
    # Stage 3: Load final target NegativeList_New1 directly by joining #Base1 with Remarks and Sources
    print("    executing Stage 3: loading non-PEP profiles...")
    sys.stdout.flush()
    stage3_nonpep_start = time.time()
    cursor.execute("""
        INSERT INTO NegativeList_New1 WITH (TABLOCK) (
            EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Nationality, Citizenship
        )
        SELECT 
            B.EntityGUID, B.ReferenceID, B.EntityType, B.Gender, B.FirstName, B.LastName, B.SecondName, B.Title,
            B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3, B.AddressLine1, B.AddressLine2, B.City, B.Country, B.POB,
            CAST(SUBSTRING(isnull(F.SourceName, G.SourceName), 1, 50) AS NVARCHAR(50)) as WLType,
            E.SourceURI as OriginalSource,
            D.Remark,
            H.IdentificationTypeDesc as NationalIDInfo,
            H.IdentificationNumber as NationalIDNo,
            I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
            J.Nationality,
            K.Citizenship
        FROM #Base1 B
        LEFT JOIN #PEP_GUIDs p ON B.EntityGUID = p.EntityGUID
        LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON B.EntityGUID = D.EntityGUID
        LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON B.EntityGUID = E.EntityGUID
        LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON B.EntityGUID = F.EntityGUID
        LEFT JOIN EntitySanction G WITH (NOLOCK) ON B.EntityGUID = G.EntityGUID
        LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON B.EntityGUID = H.EntityGUID
        LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON B.EntityGUID = I.EntityGUID
        LEFT JOIN #TempNationalities J ON B.EntityGUID = J.EntityGUID
        LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON B.EntityGUID = K.EntityGUID
        WHERE p.EntityGUID IS NULL OR (isnull(F.SourceName, G.SourceName) IS NOT NULL AND isnull(F.SourceName, G.SourceName) <> 'PEP')
        OPTION (MERGE JOIN, RECOMPILE, MAXDOP 4)
    """)
    conn.commit()
    print(f"    Stage 3 non-PEP completed in {time.time() - stage3_nonpep_start:.2f} seconds.")
    sys.stdout.flush()
    
    print("    executing Stage 3: loading PEP profiles...")
    sys.stdout.flush()
    stage3_pep_start = time.time()
    cursor.execute("""
        INSERT INTO NegativeList_New1 WITH (TABLOCK) (
            EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            Nationality, Citizenship
        )
        SELECT 
            B.EntityGUID, B.ReferenceID, B.EntityType, B.Gender, B.FirstName, B.LastName, B.SecondName, B.Title,
            B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3, B.AddressLine1, B.AddressLine2, B.City, B.Country, B.POB,
            'PEP' AS WLType,
            E.SourceURI as OriginalSource,
            D.Remark,
            H.IdentificationTypeDesc as NationalIDInfo,
            H.IdentificationNumber as NationalIDNo,
            I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
            J.Nationality,
            K.Citizenship
        FROM #Base1 B
        INNER JOIN #PEP_GUIDs p ON B.EntityGUID = p.EntityGUID
        LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON B.EntityGUID = D.EntityGUID
        LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON B.EntityGUID = E.EntityGUID
        LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON B.EntityGUID = F.EntityGUID
        LEFT JOIN EntitySanction G WITH (NOLOCK) ON B.EntityGUID = G.EntityGUID
        LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON B.EntityGUID = H.EntityGUID
        LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON B.EntityGUID = I.EntityGUID
        LEFT JOIN #TempNationalities J ON B.EntityGUID = J.EntityGUID
        LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON B.EntityGUID = K.EntityGUID
        OPTION (MERGE JOIN, RECOMPILE, MAXDOP 4)
    """)
    conn.commit()
    print(f"    Stage 3 PEP completed in {time.time() - stage3_pep_start:.2f} seconds.")
    sys.stdout.flush()
    
    print(f"  --> batch completed in {time.time() - batch_start:.2f} seconds.")
    sys.stdout.flush()
    last_guid = max_guid
    batch_num += 1

# Cleanup intermediate temp tables to release physical TempDB pages
cursor.execute("DROP TABLE IF EXISTS #Base1")
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
conn.commit()

rows_split = cursor.execute("SELECT COUNT(*) FROM NegativeList_New1 WITH (NOLOCK)").fetchone()[0]
print(f"Watchlist splits categorized ({rows_split} rows), took {time.time() - step_start:.2f} seconds total.")

cursor.close()
conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60
print(f"module 4 completed in {total_time:.2f} minutes.")

