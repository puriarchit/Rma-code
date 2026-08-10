import json
import os
import pyodbc
import sys
import time

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)

db = config["database"]
trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"

conn = pyodbc.connect(conn_str)
conn.autocommit = False
cursor = conn.cursor()

try:
    cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON;")
    conn.commit()

    print("Starting Module 5 (V3.3 Direct Staging-less Sync)...")
    sys.stdout.flush()
    global_start = time.time()

    print("--- Phase A: Source Data Integrity Verification ---")
    sys.stdout.flush()
    phase_a_start = time.time()

    # Verify no duplicates in new base entities
    cursor.execute("""
        SELECT EntityGUID, COUNT(*) AS Cnt
        FROM NegativeList_New1 WITH (NOLOCK)
        GROUP BY EntityGUID
        HAVING COUNT(*) > 1
    """)
    dup_entities = cursor.fetchall()
    if dup_entities:
        print("ERROR: Source table NegativeList_New1 contains duplicate EntityGUIDs!")
        for d in dup_entities[:5]:
            print(f"Duplicate EntityGUID: {d[0]}, Count={d[1]}")
        raise Exception("Duplicate EntityGUIDs found in source data. Execution halted for data safety.")

    # Verify no duplicates in joined aliases
    cursor.execute("""
        SELECT A.EntityGUID, B.EntityAliasGUID, COUNT(*) AS Cnt
        FROM NegativeList_New1 A WITH (NOLOCK)
        INNER JOIN EntityAlias B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        WHERE B.AliasTypeDesc NOT IN ('Acronym','Call Sign','Chinese Commercial Code (CCC)','Native Script For Alias','Native Script For Entity')
        GROUP BY A.EntityGUID, B.EntityAliasGUID
        HAVING COUNT(*) > 1
    """)
    dup_aliases = cursor.fetchall()
    if dup_aliases:
        print("ERROR: Source joins produce duplicate business keys (EntityGUID, EntityAliasGUID)!")
        for d in dup_aliases[:5]:
            print(f"Duplicate Key: EntityGUID={d[0]}, EntityAliasGUID={d[1]}, Count={d[2]}")
        raise Exception("Duplicate (EntityGUID, EntityAliasGUID) combinations found in source join. Execution halted for data safety.")

    print(f"Phase A (Source Integrity Verification) completed in {time.time() - phase_a_start:.2f} seconds.")
    sys.stdout.flush()

    print("--- Phase B: Change Detection ---")
    sys.stdout.flush()
    phase_b_start = time.time()

    cursor.execute("""
        IF OBJECT_ID('NegativeList', 'U') IS NULL
        BEGIN
            CREATE TABLE [dbo].[NegativeList](
                [ID] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
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
                [OriginalSource] [nvarchar](MAX) NULL,
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
                [EntityAliasGUID] [nvarchar](50) NULL,
                [Nationality] [nvarchar](100) NULL,
                [Citizenship] [nvarchar](100) NULL,
                [POB] [nvarchar](50) NULL,
                [Alias] [nvarchar](300) NULL,
                [VersionID] [nvarchar](15) NULL,
                [Action] [nchar](3) NULL,
                [FileName] [nvarchar](100) NULL,
                [LastUpdatedBy] [int] NULL,
                [LastUpdatedDate] [datetime] NULL,
                [CreationDate] [datetime] DEFAULT GETDATE()
            )
            CREATE NONCLUSTERED INDEX IX_NegativeList_EntityGUID ON NegativeList(EntityGUID)
            CREATE NONCLUSTERED INDEX IX_NegativeList_EntityAliasGUID ON NegativeList(EntityAliasGUID)
            CREATE NONCLUSTERED INDEX IX_NegativeList_Alias ON NegativeList(Alias)
        END
    """)

    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_SyncKey' AND object_id = OBJECT_ID('NegativeList'))
        BEGIN
            CREATE NONCLUSTERED INDEX IX_NegativeList_SyncKey ON NegativeList (EntityGUID, EntityAliasGUID)
        END
    """)

    cursor.execute("""
        IF OBJECT_ID('NegativeList_History', 'U') IS NULL
        BEGIN
            CREATE TABLE NegativeList_History (
                ID INT NULL, ReferenceID NVARCHAR(100) NULL, WLType NVARCHAR(255) NULL, FileName NVARCHAR(100) NULL,
                VersionID NVARCHAR(15) NULL, EntityType NUMERIC(2,0) NULL, Source NVARCHAR(255) NULL, OriginalSource NVARCHAR(MAX) NULL,
                Action NCHAR(3) NULL, Gender NVARCHAR(7) NULL, Deceased NCHAR(3) NULL, LastName NVARCHAR(150) NULL,
                FirstName NVARCHAR(300) NULL, SecondName NVARCHAR(300) NULL, ThirdName NVARCHAR(150) NULL, FourthName NVARCHAR(150) NULL,
                POB NVARCHAR(255) NULL, ALTPOB NVARCHAR(50) NULL, DOB NVARCHAR(255) NULL, ALTDOB1 DATETIME NULL,
                ALTDOB2 DATETIME NULL, ALTDOB3 DATETIME NULL, Nationality NVARCHAR(255) NULL, Citizenship NVARCHAR(70) NULL,
                Alias4 NVARCHAR(255) NULL, Alias3 NVARCHAR(255) NULL, Alias2 NVARCHAR(255) NULL, Alias1 NVARCHAR(255) NULL,
                Alias NVARCHAR(300) NULL, AliasType NVARCHAR(25) NULL, Title NVARCHAR(255) NULL, Designation NVARCHAR(500) NULL,
                AddressLine1 NVARCHAR(200) NULL, AddressLine2 NVARCHAR(200) NULL, City NVARCHAR(255) NULL, IdNo1 NVARCHAR(255) NULL,
                IdOtherInfo1 NVARCHAR(255) NULL, IdNo2 NVARCHAR(255) NULL, IdOtherInfo2 NVARCHAR(255) NULL, IdNo3 NVARCHAR(255) NULL,
                IdOtherInfo3 NVARCHAR(255) NULL, IdNo4 NVARCHAR(255) NULL, IdOtherInfo4 NVARCHAR(255) NULL, IdNo5 NVARCHAR(255) NULL,
                IdOtherInfo5 NVARCHAR(255) NULL, NationalIDNo NVARCHAR(50) NULL, NationalIDInfo NVARCHAR(255) NULL,
                Program NVARCHAR(150) NULL, OtherInfo TEXT NULL, Sdf NVARCHAR(255) NULL, SdfName NVARCHAR(255) NULL,
                Basis NVARCHAR(50) NULL, Remarks TEXT NULL, Status TINYINT NULL, Country NVARCHAR(255) NULL, SystemSource NCHAR(1) NULL,
                CreatedBy INT NULL, ApprovedBy INT NULL, CreationDate DATETIME NULL, ApprovalDate DATETIME NULL,
                LastUpdatedBy INT NULL, LastUpdatedDate DATETIME NULL, LastApprovedBy INT NULL, LastApprovalDate DATETIME NULL
            )
        END
    """)

    cursor.execute("""
        IF OBJECT_ID('NegativeList_Master', 'U') IS NULL
        BEGIN
            CREATE TABLE NegativeList_Master (
                ID INT NULL, ReferenceID NVARCHAR(100) NULL, WLType NVARCHAR(255) NULL, FileName NVARCHAR(100) NULL,
                VersionID NVARCHAR(15) NULL, EntityType NUMERIC(2,0) NULL, Source NVARCHAR(255) NULL, OriginalSource NVARCHAR(MAX) NULL,
                Action NCHAR(3) NULL, Gender NVARCHAR(7) NULL, Deceased NCHAR(3) NULL, LastName NVARCHAR(150) NULL,
                FirstName NVARCHAR(300) NULL, SecondName NVARCHAR(300) NULL, ThirdName NVARCHAR(150) NULL, FourthName NVARCHAR(150) NULL,
                POB NVARCHAR(255) NULL, ALTPOB NVARCHAR(50) NULL, DOB NVARCHAR(255) NULL, ALTDOB1 DATETIME NULL,
                ALTDOB2 DATETIME NULL, ALTDOB3 DATETIME NULL, Nationality NVARCHAR(255) NULL, Citizenship NVARCHAR(70) NULL,
                Alias4 NVARCHAR(255) NULL, Alias3 NVARCHAR(255) NULL, Alias2 NVARCHAR(255) NULL, Alias1 NVARCHAR(255) NULL,
                Alias NVARCHAR(300) NULL, AliasType NVARCHAR(25) NULL, Title NVARCHAR(255) NULL, Designation NVARCHAR(500) NULL,
                AddressLine1 NVARCHAR(200) NULL, AddressLine2 NVARCHAR(200) NULL, City NVARCHAR(255) NULL, IdNo1 NVARCHAR(255) NULL,
                IdOtherInfo1 NVARCHAR(255) NULL, IdNo2 NVARCHAR(255) NULL, IdOtherInfo2 NVARCHAR(255) NULL, IdNo3 NVARCHAR(255) NULL,
                IdOtherInfo3 NVARCHAR(255) NULL, IdNo4 NVARCHAR(255) NULL, IdOtherInfo4 NVARCHAR(255) NULL, IdNo5 NVARCHAR(255) NULL,
                IdOtherInfo5 NVARCHAR(255) NULL, NationalIDNo NVARCHAR(50) NULL, NationalIDInfo NVARCHAR(255) NULL,
                Program NVARCHAR(150) NULL, OtherInfo TEXT NULL, Sdf NVARCHAR(255) NULL, SdfName NVARCHAR(255) NULL,
                Basis NVARCHAR(50) NULL, Remarks TEXT NULL, Status TINYINT NULL, Country NVARCHAR(255) NULL, SystemSource NCHAR(1) NULL,
                CreatedBy INT NULL, ApprovedBy INT NULL, CreationDate DATETIME NULL, ApprovalDate DATETIME NULL,
                LastUpdatedBy INT NULL, LastUpdatedDate DATETIME NULL, LastApprovedBy INT NULL, LastApprovalDate DATETIME NULL
            )
        END
    """)

    cursor.execute("DROP TABLE IF EXISTS #ChangeSet")
    cursor.execute("""
        CREATE TABLE #ChangeSet (
            ID INT NOT NULL PRIMARY KEY,
            ChangeType CHAR(3) NOT NULL
        )
    """)

    # Non-alias change detection directly matching against source table
    cursor.execute("""
        INSERT INTO #ChangeSet (ID, ChangeType)
        SELECT N.ID, 'chg'
        FROM NegativeList N
        INNER JOIN NegativeList_New1 NT ON N.EntityGUID = NT.EntityGUID 
        WHERE N.EntityAliasGUID IS NULL
          AND (
            (ISNULL(N.ReferenceID, '') <> ISNULL(NT.ReferenceID, '')) OR
            (ISNULL(N.EntityType, 0) <> CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END) OR
            (ISNULL(N.Gender, '') <> CAST(SUBSTRING(ISNULL(NT.Gender, ''), 1, 7) AS NVARCHAR(7))) OR
            (ISNULL(N.FirstName, '') <> ISNULL(NT.FirstName, '')) OR
            (ISNULL(N.LastName, '') <> CAST(SUBSTRING(ISNULL(NT.LastName, ''), 1, 150) AS NVARCHAR(150))) OR
            (ISNULL(N.SecondName, '') <> CAST(SUBSTRING(ISNULL(NT.SecondName, ''), 1, 300) AS NVARCHAR(300))) OR
            (ISNULL(N.Title, '') <> CAST(SUBSTRING(ISNULL(NT.Title, ''), 1, 255) AS NVARCHAR(255))) OR
            (ISNULL(N.DOB, '') <> ISNULL(NT.DOB, '')) OR
            (ISNULL(N.ALTDOB1, '1900-01-01') <> ISNULL(NT.ALTDOB1, '1900-01-01')) OR
            (ISNULL(N.ALTDOB2, '1900-01-01') <> ISNULL(NT.ALTDOB2, '1900-01-01')) OR
            (ISNULL(N.ALTDOB3, '1900-01-01') <> ISNULL(NT.ALTDOB3, '1900-01-01')) OR
            (ISNULL(N.AddressLine1, '') <> CAST(SUBSTRING(ISNULL(NT.AddressLine1, ''), 1, 200) AS NVARCHAR(200))) OR
            (ISNULL(N.AddressLine2, '') <> CAST(SUBSTRING(ISNULL(NT.AddressLine2, ''), 1, 200) AS NVARCHAR(200))) OR
            (ISNULL(N.City, '') <> ISNULL(NT.City, '')) OR
            (ISNULL(N.Country, '') <> ISNULL(NT.Country, '')) OR
            (ISNULL(N.WLType, '') <> ISNULL(NT.WLType, '')) OR
            (ISNULL(N.OriginalSource, '') <> ISNULL(NT.OriginalSource, '')) OR
            (ISNULL(N.Remark, '') <> ISNULL(NT.Remark, '')) OR
            (ISNULL(N.NationalIDInfo, '') <> ISNULL(NT.NationalIDInfo, '')) OR
            (ISNULL(N.NationalIDNo, '') <> ISNULL(NT.NationalIDNo, '')) OR
            (ISNULL(N.IdOtherInfo1, '') <> ISNULL(NT.IdOtherInfo1, '')) OR
            (ISNULL(N.IdNo1, '') <> ISNULL(NT.IdNo1, '')) OR
            (ISNULL(N.IdOtherInfo2, '') <> ISNULL(NT.IdOtherInfo2, '')) OR
            (ISNULL(N.IdNo2, '') <> ISNULL(NT.IdNo2, '')) OR
            (ISNULL(N.IdOtherInfo3, '') <> ISNULL(NT.IdOtherInfo3, '')) OR
            (ISNULL(N.IdNo3, '') <> ISNULL(NT.IdNo3, '')) OR
            (ISNULL(N.IdOtherInfo4, '') <> ISNULL(NT.IdOtherInfo4, '')) OR
            (ISNULL(N.IdNo4, '') <> ISNULL(NT.IdNo4, '')) OR
            (ISNULL(N.IdOtherInfo5, '') <> ISNULL(NT.IdOtherInfo5, '')) OR
            (ISNULL(N.IdNo5, '') <> ISNULL(NT.IdNo5, '')) OR
            (ISNULL(N.Nationality, '') <> ISNULL(NT.Nationality, '')) OR
            (ISNULL(N.Citizenship, '') <> CAST(SUBSTRING(ISNULL(NT.Citizenship, ''), 1, 70) AS NVARCHAR(70))) OR
            (ISNULL(N.POB, '') <> ISNULL(NT.POB, '')) OR
            N.Alias IS NOT NULL
          )
    """)

    # Alias change detection matching against source table joined with EntityAlias
    cursor.execute("""
        INSERT INTO #ChangeSet (ID, ChangeType)
        SELECT N.ID, 'chg'
        FROM NegativeList N
        INNER JOIN NegativeList_New1 NT ON N.EntityGUID = NT.EntityGUID 
        INNER JOIN EntityAlias B ON NT.EntityGUID = B.EntityGUID AND N.EntityAliasGUID = B.EntityAliasGUID
        WHERE N.EntityAliasGUID IS NOT NULL
          AND B.AliasTypeDesc NOT IN ('Acronym','Call Sign','Chinese Commercial Code (CCC)','Native Script For Alias','Native Script For Entity')
          AND NOT EXISTS (SELECT 1 FROM #ChangeSet C WHERE C.ID = N.ID)
          AND (
            (ISNULL(N.ReferenceID, '') <> ISNULL(NT.ReferenceID, '')) OR
            (ISNULL(N.EntityType, 0) <> CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END) OR
            (ISNULL(N.Gender, '') <> CAST(SUBSTRING(ISNULL(NT.Gender, ''), 1, 7) AS NVARCHAR(7))) OR
            (ISNULL(N.FirstName, '') <> CAST(SUBSTRING(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,''), 1, 300) AS NVARCHAR(300))) OR
            (ISNULL(N.LastName, '') <> CAST(SUBSTRING(B.LastName, 1, 255) AS NVARCHAR(255))) OR
            (ISNULL(N.SecondName, '') <> CAST(SUBSTRING(B.Name, 1, 500) AS NVARCHAR(500))) OR
            (ISNULL(N.Title, '') <> CAST(SUBSTRING(ISNULL(NT.Title, ''), 1, 255) AS NVARCHAR(255))) OR
            (ISNULL(N.DOB, '') <> ISNULL(NT.DOB, '')) OR
            (ISNULL(N.ALTDOB1, '1900-01-01') <> ISNULL(NT.ALTDOB1, '1900-01-01')) OR
            (ISNULL(N.ALTDOB2, '1900-01-01') <> ISNULL(NT.ALTDOB2, '1900-01-01')) OR
            (ISNULL(N.ALTDOB3, '1900-01-01') <> ISNULL(NT.ALTDOB3, '1900-01-01')) OR
            (ISNULL(N.AddressLine1, '') <> CAST(SUBSTRING(ISNULL(NT.AddressLine1, ''), 1, 200) AS NVARCHAR(200))) OR
            (ISNULL(N.AddressLine2, '') <> CAST(SUBSTRING(ISNULL(NT.AddressLine2, ''), 1, 200) AS NVARCHAR(200))) OR
            (ISNULL(N.City, '') <> ISNULL(NT.City, '')) OR
            (ISNULL(N.Country, '') <> ISNULL(NT.Country, '')) OR
            (ISNULL(N.WLType, '') <> ISNULL(NT.WLType, '')) OR
            (ISNULL(N.OriginalSource, '') <> ISNULL(NT.OriginalSource, '')) OR
            (ISNULL(N.Remark, '') <> ISNULL(NT.Remark, '')) OR
            (ISNULL(N.NationalIDInfo, '') <> ISNULL(NT.NationalIDInfo, '')) OR
            (ISNULL(N.NationalIDNo, '') <> ISNULL(NT.NationalIDNo, '')) OR
            (ISNULL(N.IdOtherInfo1, '') <> ISNULL(NT.IdOtherInfo1, '')) OR
            (ISNULL(N.IdNo1, '') <> ISNULL(NT.IdNo1, '')) OR
            (ISNULL(N.IdOtherInfo2, '') <> ISNULL(NT.IdOtherInfo2, '')) OR
            (ISNULL(N.IdNo2, '') <> ISNULL(NT.IdNo2, '')) OR
            (ISNULL(N.IdOtherInfo3, '') <> ISNULL(NT.IdOtherInfo3, '')) OR
            (ISNULL(N.IdNo3, '') <> ISNULL(NT.IdNo3, '')) OR
            (ISNULL(N.IdOtherInfo4, '') <> ISNULL(NT.IdOtherInfo4, '')) OR
            (ISNULL(N.IdNo4, '') <> ISNULL(NT.IdNo4, '')) OR
            (ISNULL(N.IdOtherInfo5, '') <> ISNULL(NT.IdOtherInfo5, '')) OR
            (ISNULL(N.IdNo5, '') <> ISNULL(NT.IdNo5, '')) OR
            (ISNULL(N.Nationality, '') <> ISNULL(NT.Nationality, '')) OR
            (ISNULL(N.Citizenship, '') <> CAST(SUBSTRING(ISNULL(NT.Citizenship, ''), 1, 70) AS NVARCHAR(70))) OR
            (ISNULL(N.POB, '') <> ISNULL(NT.POB, '')) OR
            (ISNULL(N.Alias, '') <> ISNULL(B.Name, ''))
          )
    """)

    conn.commit()
    print(f"Phase B completed in {time.time() - phase_b_start:.2f} seconds.")
    sys.stdout.flush()

    print("--- Phase C: Atomic Data Sync & History Backup ---")
    sys.stdout.flush()
    phase_c_start = time.time()

    cursor.execute("IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'NegativeListVersionSeq') SELECT 1 ELSE SELECT 0")
    seq_exists = cursor.fetchone()[0] == 0
    if not seq_exists:
        try:
            cursor.execute("SELECT COALESCE(MAX(TRY_CAST(VersionID AS INT)), 0) FROM NegativeList")
            max_val = cursor.fetchone()[0]
        except Exception:
            max_val = 0
        start_val = max_val + 1
        cursor.execute(f"CREATE SEQUENCE dbo.NegativeListVersionSeq AS INT START WITH {start_val} INCREMENT BY 1")
        conn.commit()

    cursor.execute("SELECT NEXT VALUE FOR dbo.NegativeListVersionSeq")
    run_version_id = str(cursor.fetchone()[0])

    cursor.execute("DROP TABLE IF EXISTS #NewIDs")
    cursor.execute("CREATE TABLE #NewIDs (ID INT NOT NULL PRIMARY KEY)")

    cursor.execute("""
        INSERT INTO NegativeList_History (
            ID, ReferenceID, WLType, FileName, VersionID, EntityType, Source, OriginalSource, Action, Gender, 
            LastName, FirstName, SecondName, POB, DOB, ALTDOB1, ALTDOB2, ALTDOB3, Nationality, Citizenship, 
            Alias, Title, AddressLine1, AddressLine2, City, IdNo1, IdOtherInfo1, IdNo2, IdOtherInfo2, IdNo3, 
            IdOtherInfo3, IdNo4, IdOtherInfo4, IdNo5, IdOtherInfo5, NationalIDNo, NationalIDInfo, Basis, Remarks, 
            Country, CreationDate, LastUpdatedBy, LastUpdatedDate
        )
        SELECT 
            A.ID, A.ReferenceID, A.WLType, A.FileName, A.VersionID, 
            CASE 
                WHEN ISNUMERIC(A.EntityType) = 1 THEN CAST(A.EntityType AS NUMERIC(2,0))
                WHEN A.EntityType = 'Individual' THEN 3
                WHEN A.EntityType = 'Country' THEN 1
                WHEN A.EntityType = 'Organization' THEN 9
                WHEN A.EntityType = 'Vessel' THEN 4
                ELSE 6 
            END, 
            A.SystemSource, A.OriginalSource, A.Action, CAST(SUBSTRING(A.Gender, 1, 7) AS NVARCHAR(7)), CAST(SUBSTRING(A.LastName, 1, 150) AS NVARCHAR(150)), 
            A.FirstName, CAST(SUBSTRING(A.SecondName, 1, 300) AS NVARCHAR(300)), A.POB, A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, 
            A.Nationality, CAST(SUBSTRING(A.Citizenship, 1, 70) AS NVARCHAR(70)), A.Alias, CAST(SUBSTRING(A.Title, 1, 255) AS NVARCHAR(255)), 
            CAST(SUBSTRING(A.AddressLine1, 1, 200) AS NVARCHAR(200)), CAST(SUBSTRING(A.AddressLine2, 1, 200) AS NVARCHAR(200)), 
            A.City, A.IdNo1, A.IdOtherInfo1, A.IdNo2, A.IdOtherInfo2, A.IdNo3, A.IdOtherInfo3, A.IdNo4, A.IdOtherInfo4, A.IdNo5, A.IdOtherInfo5, 
            A.NationalIDNo, A.NationalIDInfo, A.EntityGUID, A.Remark, A.Country, A.CreationDate, A.LastUpdatedBy, A.LastUpdatedDate
        FROM NegativeList A
        INNER JOIN #ChangeSet C ON A.ID = C.ID
    """)

    # Update base entities
    cursor.execute("""
        UPDATE N 
        SET N.ReferenceID = NT.ReferenceID, 
            N.EntityType = CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END,
            N.Gender = SUBSTRING(NT.Gender,1,7),
            N.FirstName = NT.FirstName,
            N.LastName = SUBSTRING(NT.LastName,1,150),
            N.SecondName = SUBSTRING(NT.SecondName,1,300),
            N.Title = SUBSTRING(NT.Title,1,255),
            N.DOB = NT.DOB,
            N.ALTDOB1 = NT.ALTDOB1,
            N.ALTDOB2 = NT.ALTDOB2,
            N.ALTDOB3 = NT.ALTDOB3, 
            N.AddressLine1 = SUBSTRING(NT.AddressLine1,1,200),
            N.AddressLine2 = SUBSTRING(NT.AddressLine2,1,200),
            N.City = NT.City,
            N.Country = NT.Country,
            N.WLType = NT.WLType,
            N.OriginalSource = NT.OriginalSource,
            N.Remark = NT.Remark,
            N.NationalIDInfo = NT.NationalIDInfo,
            N.NationalIDNo = NT.NationalIDNo,
            N.IdOtherInfo1 = NT.IdOtherInfo1,
            N.IdNo1 = NT.IdNo1,
            N.IdOtherInfo2 = NT.IdOtherInfo2,
            N.IdNo2 = NT.IdNo2,
            N.IdOtherInfo3 = NT.IdOtherInfo3,
            N.IdNo3 = NT.IdNo3,
            N.IdOtherInfo4 = NT.IdOtherInfo4,
            N.IdNo4 = NT.IdNo4,
            N.IdOtherInfo5 = NT.IdOtherInfo5,
            N.IdNo5 = NT.IdNo5,
            N.Nationality = NT.Nationality,
            N.Citizenship = SUBSTRING(NT.Citizenship,1,70),
            N.POB = NT.POB,
            N.Alias = NULL,
            N.FileName = CONVERT(char(10), GETDATE(), 126),
            N.LastUpdatedBy = 3,
            N.LastUpdatedDate = GETDATE(),
            N.Action = 'chg',
            N.VersionID = ?
        FROM NegativeList N
        INNER JOIN #ChangeSet C ON N.ID = C.ID
        INNER JOIN NegativeList_New1 NT ON N.EntityGUID = NT.EntityGUID 
        WHERE N.EntityAliasGUID IS NULL;
        
        SELECT @@ROWCOUNT;
    """, (run_version_id,))
    total_updated = cursor.fetchone()[0]

    # Update alias records
    cursor.execute("""
        UPDATE N 
        SET N.ReferenceID = NT.ReferenceID, 
            N.EntityType = CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END,
            N.Gender = SUBSTRING(NT.Gender,1,7),
            N.FirstName = CAST(SUBSTRING(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,''), 1, 300) AS NVARCHAR(300)),
            N.LastName = CAST(SUBSTRING(B.LastName, 1, 255) AS NVARCHAR(255)),
            N.SecondName = CAST(SUBSTRING(B.Name, 1, 500) AS NVARCHAR(500)),
            N.Title = SUBSTRING(NT.Title,1,255),
            N.DOB = NT.DOB,
            N.ALTDOB1 = NT.ALTDOB1,
            N.ALTDOB2 = NT.ALTDOB2,
            N.ALTDOB3 = NT.ALTDOB3, 
            N.AddressLine1 = SUBSTRING(NT.AddressLine1,1,200),
            N.AddressLine2 = SUBSTRING(NT.AddressLine2,1,200),
            N.City = NT.City,
            N.Country = NT.Country,
            N.WLType = NT.WLType,
            N.OriginalSource = NT.OriginalSource,
            N.Remark = NT.Remark,
            N.NationalIDInfo = NT.NationalIDInfo,
            N.NationalIDNo = NT.NationalIDNo,
            N.IdOtherInfo1 = NT.IdOtherInfo1,
            N.IdNo1 = NT.IdNo1,
            N.IdOtherInfo2 = NT.IdOtherInfo2,
            N.IdNo2 = NT.IdNo2,
            N.IdOtherInfo3 = NT.IdOtherInfo3,
            N.IdNo3 = NT.IdNo3,
            N.IdOtherInfo4 = NT.IdOtherInfo4,
            N.IdNo4 = NT.IdNo4,
            N.IdOtherInfo5 = NT.IdOtherInfo5,
            N.IdNo5 = NT.IdNo5,
            N.Nationality = NT.Nationality,
            N.Citizenship = SUBSTRING(NT.Citizenship,1,70),
            N.POB = NT.POB,
            N.Alias = B.Name,
            N.FileName = CONVERT(char(10), GETDATE(), 126),
            N.LastUpdatedBy = 3,
            N.LastUpdatedDate = GETDATE(),
            N.Action = 'chg',
            N.VersionID = ?
        FROM NegativeList N
        INNER JOIN #ChangeSet C ON N.ID = C.ID
        INNER JOIN NegativeList_New1 NT ON N.EntityGUID = NT.EntityGUID
        INNER JOIN EntityAlias B ON NT.EntityGUID = B.EntityGUID AND N.EntityAliasGUID = B.EntityAliasGUID
        WHERE N.EntityAliasGUID IS NOT NULL;

        SELECT @@ROWCOUNT;
    """, (run_version_id,))
    total_updated += cursor.fetchone()[0]

    # Insert new base entities
    cursor.execute("""
        INSERT INTO NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action, FileName, CreationDate
        )
        OUTPUT INSERTED.ID INTO #NewIDs(ID)
        SELECT 
            ReferenceID, 
            CASE WHEN EntityType='Individual' THEN 3 WHEN EntityType='Country' THEN 1 WHEN EntityType='Organization' THEN 9 WHEN EntityType='Vessel' THEN 4 ELSE 6 END,
            SUBSTRING(Gender, 1, 7), FirstName, SUBSTRING(LastName, 1, 150), SUBSTRING(SecondName, 1, 300), SUBSTRING(Title, 1, 255),
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, SUBSTRING(AddressLine1, 1, 200), SUBSTRING(AddressLine2, 1, 200), City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, NULL, Nationality, SUBSTRING(Citizenship, 1, 70), POB, NULL, ?, 'add', CONVERT(char(10), GETDATE(), 126), GETDATE()
        FROM NegativeList_New1 A
        WHERE NOT EXISTS (
              SELECT 1 FROM NegativeList N
              WHERE N.EntityGUID = A.EntityGUID 
                AND N.EntityAliasGUID IS NULL
          );

        SELECT @@ROWCOUNT;
    """, (run_version_id,))
    total_inserted = cursor.fetchone()[0]

    # Insert new alias records
    cursor.execute("""
        INSERT INTO NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action, FileName, CreationDate
        )
        OUTPUT INSERTED.ID INTO #NewIDs(ID)
        SELECT 
            A.ReferenceID, 
            CASE WHEN A.EntityType='Individual' THEN 3 WHEN A.EntityType='Country' THEN 1 WHEN A.EntityType='Organization' THEN 9 WHEN A.EntityType='Vessel' THEN 4 ELSE 6 END,
            SUBSTRING(A.Gender, 1, 7), 
            CAST(SUBSTRING(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,''), 1, 300) AS NVARCHAR(300)),
            CAST(SUBSTRING(B.LastName, 1, 255) AS NVARCHAR(255)),
            CAST(SUBSTRING(B.Name, 1, 500) AS NVARCHAR(500)),
            SUBSTRING(A.Title, 1, 255),
            A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, SUBSTRING(A.AddressLine1, 1, 200), SUBSTRING(A.AddressLine2, 1, 200), A.City, A.Country,
            A.WLType, A.OriginalSource, A.Remark, A.NationalIDInfo, A.NationalIDNo,
            A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3, A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5,
            A.EntityGUID, B.EntityAliasGUID, A.Nationality, SUBSTRING(A.Citizenship, 1, 70), A.POB, B.Name, ?, 'add', CONVERT(char(10), GETDATE(), 126), GETDATE()
        FROM NegativeList_New1 A
        INNER JOIN EntityAlias B ON A.EntityGUID = B.EntityGUID
        WHERE B.AliasTypeDesc NOT IN ('Acronym','Call Sign','Chinese Commercial Code (CCC)','Native Script For Alias','Native Script For Entity')
          AND NOT EXISTS (
              SELECT 1 FROM NegativeList N
              WHERE N.EntityGUID = A.EntityGUID 
                AND N.EntityAliasGUID = B.EntityAliasGUID
          );

        SELECT @@ROWCOUNT;
    """, (run_version_id,))
    total_inserted += cursor.fetchone()[0]

    cursor.execute("DROP TABLE IF EXISTS #AffectedIDs")
    cursor.execute("CREATE TABLE #AffectedIDs (ID INT NOT NULL PRIMARY KEY)")
    cursor.execute("INSERT INTO #AffectedIDs (ID) SELECT ID FROM #ChangeSet UNION SELECT ID FROM #NewIDs")

    conn.commit()
    print(f"Phase C completed in {time.time() - phase_c_start:.2f} seconds.")
    sys.stdout.flush()

    print("--- Phase D: Master Sync & Filter Sync ---")
    sys.stdout.flush()
    phase_d_start = time.time()

    cursor.execute("""
        DELETE M
        FROM NegativeList_Master M
        INNER JOIN #AffectedIDs Aff ON M.ID = Aff.ID
    """)

    cursor.execute("""
        INSERT INTO NegativeList_Master (
            ID, ReferenceID, WLType, FileName, VersionID, EntityType, OriginalSource, Action, Gender, 
            LastName, FirstName, SecondName, POB, DOB, ALTDOB1, ALTDOB2, ALTDOB3, Nationality, Citizenship, 
            Alias, Title, AddressLine1, AddressLine2, City, IdNo1, IdOtherInfo1, IdNo2, IdOtherInfo2, IdNo3, 
            IdOtherInfo3, IdNo4, IdOtherInfo4, IdNo5, IdOtherInfo5, NationalIDNo, NationalIDInfo, Basis, Remarks, 
            Country, CreationDate, LastUpdatedBy, LastUpdatedDate
        )
        SELECT 
            A.ID, A.ReferenceID, A.WLType, A.FileName, A.VersionID, 
            CASE 
                WHEN ISNUMERIC(A.EntityType) = 1 THEN CAST(A.EntityType AS NUMERIC(2,0))
                WHEN A.EntityType = 'Individual' THEN 3
                WHEN A.EntityType = 'Country' THEN 1
                WHEN A.EntityType = 'Organization' THEN 9
                WHEN A.EntityType = 'Vessel' THEN 4
                ELSE 6 
            END, 
            A.OriginalSource, A.Action, CAST(SUBSTRING(A.Gender, 1, 7) AS NVARCHAR(7)), CAST(SUBSTRING(A.LastName, 1, 150) AS NVARCHAR(150)), 
            A.FirstName, CAST(SUBSTRING(A.SecondName, 1, 300) AS NVARCHAR(300)), A.POB, A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, 
            A.Nationality, CAST(SUBSTRING(A.Citizenship, 1, 70) AS NVARCHAR(70)), A.Alias, CAST(SUBSTRING(A.Title, 1, 255) AS NVARCHAR(255)), 
            CAST(SUBSTRING(A.AddressLine1, 1, 200) AS NVARCHAR(200)), CAST(SUBSTRING(A.AddressLine2, 1, 200) AS NVARCHAR(200)), 
            A.City, A.IdNo1, A.IdOtherInfo1, A.IdNo2, A.IdOtherInfo2, A.IdNo3, A.IdOtherInfo3, A.IdNo4, A.IdOtherInfo4, A.IdNo5, A.IdOtherInfo5, 
            A.NationalIDNo, A.NationalIDInfo, A.EntityGUID, A.Remark, A.Country, A.CreationDate, A.LastUpdatedBy, A.LastUpdatedDate
        FROM NegativeList A
        INNER JOIN #AffectedIDs Aff ON A.ID = Aff.ID
    """)

    cursor.execute("IF OBJECT_ID('NegativeListFilter', 'U') IS NULL BEGIN CREATE TABLE NegativeListFilter (ID INT PRIMARY KEY, FirstName NVARCHAR(1000) NULL, LastName NVARCHAR(1000) NULL, Nationality NVARCHAR(255) NULL) END")
    
    cursor.execute("""
        INSERT INTO NegativeListFilter WITH (TABLOCK) (ID, FirstName, LastName, Nationality)
        SELECT i.ID, 
               UPPER(RTRIM(LTRIM(ISNULL(i.FirstName, '')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(i.LastName, '')))), 
               UPPER(RTRIM(LTRIM(ISNULL(i.LastName, '')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(i.FirstName, '')))), 
               i.Nationality
        FROM NegativeList i
        INNER JOIN #NewIDs n ON i.ID = n.ID
        WHERE NOT EXISTS (
            SELECT 1 FROM NegativeListFilter nf WHERE nf.ID = i.ID
        );
    """)

    cursor.execute("""
        UPDATE N 
        SET FirstName = UPPER(RTRIM(LTRIM(ISNULL(NT.FirstName, '')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(NT.LastName, '')))), 
            LastName = UPPER(RTRIM(LTRIM(ISNULL(NT.LastName, '')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(NT.FirstName, '')))), 
            Nationality = NT.Nationality
        FROM NegativeListFilter N
        INNER JOIN NegativeList NT ON N.ID = NT.ID
        INNER JOIN #ChangeSet C ON NT.ID = C.ID
    """)

    cursor.execute("IF OBJECT_ID('NegativeList_History_Summary', 'U') IS NULL BEGIN CREATE TABLE [NegativeList_History_Summary] ([Type] varchar(29), [Count] int, [RunDate] datetime) END")
    
    cursor.execute("""
        INSERT INTO NegativeList_History_Summary WITH (TABLOCK) (Type, Count, RunDate)
        VALUES 
            ('New Negative List Records', ?, GETDATE()),
            ('Updated Negative List Records', ?, GETDATE()),
            ('Total Negative List Records', ?, GETDATE())
    """, (total_inserted, total_updated, total_inserted + total_updated))

    conn.commit()
    print(f"Phase D completed in {time.time() - phase_d_start:.2f} seconds.")
    sys.stdout.flush()

    print("--- Phase E: Cleanup Operations ---")
    sys.stdout.flush()
    phase_e_start = time.time()

    cursor.execute("DROP TABLE IF EXISTS #ChangeSet")
    cursor.execute("DROP TABLE IF EXISTS #NewIDs")
    cursor.execute("DROP TABLE IF EXISTS #AffectedIDs")
    
    conn.commit()
    print(f"Phase E completed in {time.time() - phase_e_start:.2f} seconds.")
    print(f"Module 5 V3.3 Direct Sync completed successfully! Total Time: {time.time() - global_start:.2f} seconds.")
    sys.stdout.flush()

except KeyboardInterrupt:
    print("\nCancellation requested by user. Rolling back active transaction...")
    sys.stdout.flush()
    try:
        conn.rollback()
    except Exception:
        pass
    raise

except Exception as ex:
    print(f"\nModule 5 execution failed! Rolling back active transaction. Error: {ex}")
    sys.stdout.flush()
    try:
        conn.rollback()
    except Exception:
        pass
    raise ex
    
finally:
    cursor.close()
    conn.close()
