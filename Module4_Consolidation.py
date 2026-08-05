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
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("""
    SELECT A.EntityGUID, B.tCountry AS Nationality
    INTO #TempNationalities
    FROM EntityCountryAssociation A WITH (NOLOCK)
    INNER HASH JOIN Country B WITH (NOLOCK) ON A.ISOStandard = B.tISO
    WHERE A.AssociationTypeDesc = 'Nationality'
    OPTION (HASH JOIN)
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

print("assembling master profile details...")
start_time = time.time()
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
        B.DOB,
        B.ALTDOB1,
        B.ALTDOB2,
        B.ALTDOB3,
        C.AddressLine1,
        C.AddressLine2,
        C.City,
        C.Country,
        C.POB,
        CAST(SUBSTRING(isnull(F.SourceName, G.SourceName), 1, 50) AS NVARCHAR(50)) as WLType,
        E.SourceURI as OriginalSource,
        D.Remark,
        H.IdentificationTypeDesc as NationalIDInfo,
        H.IdentificationNumber as NationalIDNo,
        I.IdOtherInfo1,
        I.IdNo1,
        I.IdOtherInfo2,
        I.IdNo2,
        I.IdOtherInfo3,
        I.IdNo3,
        I.IdOtherInfo4,
        I.IdNo4,
        I.IdOtherInfo5,
        I.IdNo5,
        J.Nationality,
        K.Citizenship
    FROM Entity A WITH (NOLOCK)
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
    OPTION (HASH JOIN)
""")
conn.commit()
print(f"done assembling profiles, took {time.time() - start_time:.2f} seconds.")

print("splitting profiles into watchlist categories...")
start_time = time.time()

print("loading non-pep profiles...")
cursor.execute("""
    INSERT INTO NegativeList_New1 WITH (TABLOCK)
    SELECT n.* 
    FROM NegativeList_New n WITH (NOLOCK)
    LEFT JOIN #PEP_GUIDs p ON n.EntityGUID = p.EntityGUID
    WHERE n.WLType IS NULL AND p.EntityGUID IS NULL
    OPTION (HASH JOIN)
""")
conn.commit()

print("loading sanctions and enforcements...")
cursor.execute("""
    INSERT INTO NegativeList_New1 WITH (TABLOCK)
    SELECT * 
    FROM NegativeList_New WITH (NOLOCK)
    WHERE WLType IS NOT NULL
    OPTION (HASH JOIN)
""")
conn.commit()

print("loading pep profiles...")
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
    OPTION (HASH JOIN)
""")
conn.commit()

cursor.execute("DROP TABLE IF EXISTS NegativeList_New")
cursor.execute("DROP TABLE IF EXISTS #TempNationalities")
cursor.execute("DROP TABLE IF EXISTS #PEP_GUIDs")
conn.commit()

print(f"categorization done in {time.time() - start_time:.2f} seconds.")

cursor.close()
conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60
print(f"module 4 completed in {total_time:.2f} minutes.")

