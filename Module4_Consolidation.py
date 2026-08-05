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
    cursor.execute("CHECKPOINT")
    cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging_log, 10)")
    print("database optimized and log file shrunk.")
except Exception as e:
    print("db maintenance alert:", e)

print("starting module 4...")
global_start = time.time()

print("recreating staging tables...")
cursor.execute("IF OBJECT_ID('NegativeList_New', 'U') IS NOT NULL DROP TABLE NegativeList_New")
cursor.execute("""
    CREATE TABLE [dbo].[NegativeList_New](
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
    )
""")

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
    )
""")
conn.commit()

print("creating temporary lookup tables...")
step_start = time.time()
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("""
    SELECT A.EntityGUID, B.tCountry AS Nationality
    INTO #TempNationalities
    FROM EntityCountryAssociation A WITH (NOLOCK)
    INNER HASH JOIN Country B WITH (NOLOCK) ON A.ISOStandard = B.tISO
    WHERE A.AssociationTypeDesc = 'Nationality'
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 15)
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
print(f"lookup tables created, took {time.time() - step_start:.2f} seconds.")

print("assembling master profile details...")
master_total_time = 0.0

# Step 1: Join DOB + Address (Narrow intermediate)
print("step 1 processed (DOB & Address details joined)...")
t0 = time.time()
cursor.execute("DROP TABLE IF EXISTS #TempGroup1")
cursor.execute("""
    SELECT 
        A.EntityGUID,
        B.DOB, B.ALTDOB1, B.ALTDOB2, B.ALTDOB3,
        C.AddressLine1, C.AddressLine2, C.City, C.Country, C.POB
    INTO #TempGroup1
    FROM (SELECT EntityGUID FROM Entity WITH (NOLOCK)) A
    LEFT JOIN EntityDOB_New B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
    LEFT JOIN EntityAddress_New C WITH (NOLOCK) ON A.EntityGUID = C.EntityGUID
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 20)
""")
cursor.execute("CREATE CLUSTERED INDEX IX_TempGroup1_EntityGUID ON #TempGroup1(EntityGUID)")
cursor.execute("SELECT COUNT(*) FROM #TempGroup1")
g1_count = cursor.fetchone()[0]
dt = time.time() - t0
master_total_time += dt
print(f"step 1 completed ({g1_count} rows), took {dt:.2f} seconds.")

# Step 2: Join Remarks + Web Links (Narrow intermediate)
print("step 2 processed (Remarks & Web Links joined)...")
t0 = time.time()
cursor.execute("DROP TABLE IF EXISTS #TempGroup2")
cursor.execute("""
    SELECT 
        A.*,
        D.Remark,
        E.SourceURI as OriginalSource
    INTO #TempGroup2
    FROM #TempGroup1 A
    LEFT JOIN EntityRemark_New D WITH (NOLOCK) ON A.EntityGUID = D.EntityGUID
    LEFT JOIN EntitySourceItem_New E WITH (NOLOCK) ON A.EntityGUID = E.EntityGUID
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 20)
""")
cursor.execute("CREATE CLUSTERED INDEX IX_TempGroup2_EntityGUID ON #TempGroup2(EntityGUID)")
cursor.execute("DROP TABLE #TempGroup1")
cursor.execute("SELECT COUNT(*) FROM #TempGroup2")
g2_count = cursor.fetchone()[0]
dt = time.time() - t0
master_total_time += dt
print(f"step 2 completed ({g2_count} rows), took {dt:.2f} seconds.")

# Step 3: Join Enforcements + Sanctions + Citizenships (Narrow intermediate)
print("step 3 processed (Enforcements, Sanctions & Citizenships joined)...")
t0 = time.time()
cursor.execute("DROP TABLE IF EXISTS #TempGroup3")
cursor.execute("""
    SELECT 
        A.*,
        CAST(SUBSTRING(isnull(F.SourceName, G.SourceName), 1, 50) AS NVARCHAR(50)) as WLType,
        K.Citizenship
    INTO #TempGroup3
    FROM #TempGroup2 A
    LEFT JOIN EntityEnforcement F WITH (NOLOCK) ON A.EntityGUID = F.EntityGUID
    LEFT JOIN EntitySanction G WITH (NOLOCK) ON A.EntityGUID = G.EntityGUID
    LEFT JOIN Entity_Citizenship_New K WITH (NOLOCK) ON A.EntityGUID = K.EntityGUID
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 20)
""")
cursor.execute("CREATE CLUSTERED INDEX IX_TempGroup3_EntityGUID ON #TempGroup3(EntityGUID)")
cursor.execute("DROP TABLE #TempGroup2")
cursor.execute("SELECT COUNT(*) FROM #TempGroup3")
g3_count = cursor.fetchone()[0]
dt = time.time() - t0
master_total_time += dt
print(f"step 3 completed ({g3_count} rows), took {dt:.2f} seconds.")

# Step 4: Final insertion into NegativeList_New
print("step 4 processed (final master profile compilation and insert)...")
t0 = time.time()
cursor.execute("""
    INSERT INTO NegativeList_New WITH (TABLOCK) (
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
        T.DOB, T.ALTDOB1, T.ALTDOB2, T.ALTDOB3,
        T.AddressLine1, T.AddressLine2, T.City, T.Country, T.POB,
        T.WLType, T.OriginalSource, T.Remark,
        H.IdentificationTypeDesc as NationalIDInfo,
        H.IdentificationNumber as NationalIDNo,
        I.IdOtherInfo1, I.IdNo1, I.IdOtherInfo2, I.IdNo2, I.IdOtherInfo3, I.IdNo3, I.IdOtherInfo4, I.IdNo4, I.IdOtherInfo5, I.IdNo5,
        J.Nationality,
        T.Citizenship
    FROM #TempGroup3 T
    INNER JOIN Entity A WITH (NOLOCK) ON T.EntityGUID = A.EntityGUID
    LEFT JOIN EntityIdentification_National_New H WITH (NOLOCK) ON T.EntityGUID = H.EntityGUID
    LEFT JOIN EntityIdentification_New I WITH (NOLOCK) ON T.EntityGUID = I.EntityGUID
    LEFT JOIN #TempNationalities J ON T.EntityGUID = J.EntityGUID
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 20)
""")
conn.commit()
cursor.execute("DROP TABLE IF EXISTS #TempGroup3")
cursor.execute("SELECT COUNT(*) FROM NegativeList_New WITH (NOLOCK)")
rows_master = cursor.fetchone()[0]
dt = time.time() - t0
master_total_time += dt
print(f"master profiles consolidated ({rows_master} rows), took {dt:.2f} seconds.")

print("splitting profiles into watchlist categories...")
split_total_rows = 0
split_total_time = 0.0

# 1. Non-PEP Split
print("loading non-pep profiles...")
t0 = time.time()
cursor.execute("""
    INSERT INTO NegativeList_New1 WITH (TABLOCK)
    SELECT n.* 
    FROM NegativeList_New n WITH (NOLOCK)
    LEFT JOIN #PEP_GUIDs p ON n.EntityGUID = p.EntityGUID
    WHERE n.WLType IS NULL AND p.EntityGUID IS NULL
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 10)
""")
conn.commit()
rows_nonpep = cursor.rowcount
if rows_nonpep <= 0:
    cursor.execute("SELECT COUNT(*) FROM NegativeList_New1 WITH (NOLOCK) WHERE WLType IS NULL")
    rows_nonpep = cursor.fetchone()[0]
dt = time.time() - t0
split_total_rows += rows_nonpep
split_total_time += dt
print(f"non-pep watchlist split complete ({rows_nonpep} rows) in {dt:.2f} seconds.")

# 2. Sanctions/Enforcements Split
print("loading sanctions and enforcements...")
t0 = time.time()
cursor.execute("""
    INSERT INTO NegativeList_New1 WITH (TABLOCK)
    SELECT * 
    FROM NegativeList_New WITH (NOLOCK)
    WHERE WLType IS NOT NULL AND WLType <> 'PEP'
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 10)
""")
conn.commit()
rows_sanc = cursor.rowcount
if rows_sanc <= 0:
    cursor.execute("SELECT COUNT(*) FROM NegativeList_New1 WITH (NOLOCK) WHERE WLType IS NOT NULL AND WLType <> 'PEP'")
    rows_sanc = cursor.fetchone()[0]
dt = time.time() - t0
split_total_rows += rows_sanc
split_total_time += dt
print(f"sanctions split complete ({rows_sanc} rows) in {dt:.2f} seconds.")

# 3. PEP Split
print("loading pep profiles...")
t0 = time.time()
cursor.execute("""
    INSERT INTO NegativeList_New1 WITH (TABLOCK) (
        EntityGUID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
        DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, POB,
        WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
        IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
        Nationality, Citizenship
    )
    SELECT 
        n.EntityGUID, n.ReferenceID, n.EntityType, n.Gender, n.FirstName, n.LastName, n.SecondName, n.Title,
        n.DOB, n.ALTDOB1, n.ALTDOB2, n.ALTDOB3, n.AddressLine1, n.AddressLine2, n.City, n.Country, n.POB,
        'PEP' AS WLType, n.OriginalSource, n.Remark, n.NationalIDInfo, n.NationalIDNo,
        n.IdOtherInfo1, n.IdNo1, n.IdOtherInfo2, n.IdNo2, n.IdOtherInfo3, n.IdNo3, n.IdOtherInfo4, n.IdNo4, n.IdOtherInfo5, n.IdNo5,
        n.Nationality, n.Citizenship
    FROM NegativeList_New n WITH (NOLOCK)
    INNER JOIN #PEP_GUIDs p ON n.EntityGUID = p.EntityGUID
    OPTION (HASH JOIN, MIN_GRANT_PERCENT = 10)
""")
conn.commit()
rows_pep = cursor.rowcount
if rows_pep <= 0:
    cursor.execute("SELECT COUNT(*) FROM NegativeList_New1 WITH (NOLOCK) WHERE WLType = 'PEP'")
    rows_pep = cursor.fetchone()[0]
dt = time.time() - t0
split_total_rows += rows_pep
split_total_time += dt
print(f"pep watchlist split complete ({rows_pep} rows) in {dt:.2f} seconds.")

# Cleanup temporary tables
cursor.execute("DROP TABLE IF EXISTS NegativeList_New")
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
conn.commit()

print(f"watchlist splits categorized ({split_total_rows} rows), took {split_total_time:.2f} seconds.")

cursor.close()
conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60
print(f"module 4 completed in {total_time:.2f} minutes.")


