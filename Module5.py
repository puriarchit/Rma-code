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
    print("Starting Module 5 (Production Sync & Merge)...")
    sys.stdout.flush()
    global_start = time.time()
    
    print("Recreating staging NegativeList table...")
    sys.stdout.flush()
    cursor.execute("IF OBJECT_ID('NegativeList', 'U') IS NOT NULL DROP TABLE NegativeList")
    cursor.execute("""
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
    """)
    
    print("Loading non-alias records from NegativeList_New1...")
    sys.stdout.flush()
    cursor.execute("""
        INSERT INTO NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action
        )
        SELECT 
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, NULL, Nationality, Citizenship, POB, NULL, NULL, 'add'
        FROM NegativeList_New1 WITH (NOLOCK)
    """)
    
    print("Loading alias profiles using EntityAlias...")
    sys.stdout.flush()
    cursor.execute("""
        INSERT INTO NegativeList WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title,
            DOB, ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country,
            WLType, OriginalSource, Remark, NationalIDInfo, NationalIDNo,
            IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5,
            EntityGUID, EntityAliasGUID, Nationality, Citizenship, POB, Alias, VersionID, Action
        )
        SELECT 
            A.ReferenceID, A.EntityType, A.Gender, 
            CAST(SUBSTRING(ISNULL(B.FirstName,'') + ' ' + ISNULL(B.MiddleName,''), 1, 300) AS NVARCHAR(300)),
            CAST(SUBSTRING(B.LastName, 1, 255) AS NVARCHAR(255)),
            CAST(SUBSTRING(B.Name, 1, 500) AS NVARCHAR(500)),
            A.Title, A.DOB, A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, A.AddressLine1, A.AddressLine2, A.City, A.Country,
            A.WLType, A.OriginalSource, A.Remark, A.NationalIDInfo, A.NationalIDNo,
            A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3, A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5,
            A.EntityGUID, B.EntityAliasGUID, A.Nationality, A.Citizenship, A.POB, B.Name, NULL, 'add'
        FROM NegativeList_New1 A WITH (NOLOCK)
        INNER JOIN EntityAlias B WITH (NOLOCK) ON A.EntityGUID = B.EntityGUID
        WHERE B.AliasTypeDesc NOT IN ('Acronym','Call Sign','Chinese Commercial Code (CCC)','Native Script For Alias','Native Script For Entity')
    """)
    
    print("Creating indexes on NegativeList staging table...")
    sys.stdout.flush()
    cursor.execute("CREATE CLUSTERED INDEX IX_NegativeList_EntityGUID ON NegativeList(EntityGUID)")
    cursor.execute("CREATE NONCLUSTERED INDEX IX_NegativeList_Alias ON NegativeList(Alias)")
    
    print("Extracting unique EntityGUID mapping table...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS EntityGUID")
    cursor.execute("""
        CREATE TABLE EntityGUID (
            EntityGUID NVARCHAR(50) NULL,
            EntityAliasGUID NVARCHAR(50) NULL,
            WLType NVARCHAR(200) NULL,
            Nationality NVARCHAR(100) NULL,
            WLType1 NVARCHAR(255) NULL,
            Nationality1 NVARCHAR(255) NULL
        )
    """)
    cursor.execute("""
        INSERT INTO EntityGUID WITH (TABLOCK) (EntityGUID, EntityAliasGUID, Nationality, WLType, Nationality1, WLType1)
        SELECT DISTINCT EntityGUID, EntityAliasGUID, Nationality, WLType, ISNULL(Nationality,'ABC'), ISNULL(WLType,'XYZ')
        FROM NegativeList
    """)
    cursor.execute("CREATE CLUSTERED INDEX IX_EntityGUID_Join ON EntityGUID(EntityGUID, EntityAliasGUID, Nationality1, WLType1)")
    
    print("Populating NegativeList_NotNull table...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS NegativeList_NotNull")
    cursor.execute("""
        CREATE TABLE NegativeList_NotNull (
            ID INT NOT NULL,
            Basis NVARCHAR(50) NULL,
            Alias NVARCHAR(300) NULL,
            WLType1 NVARCHAR(255) NULL,
            Nationality1 NVARCHAR(255) NULL
        )
    """)
    cursor.execute("""
        INSERT INTO NegativeList_NotNull WITH (TABLOCK) (ID, Basis, Alias, WLType1, Nationality1)
        SELECT ID, EntityGUID, Alias, ISNULL(WLType,'XYZ'), ISNULL(Nationality,'ABC')
        FROM NegativeList
    """)
    cursor.execute("CREATE CLUSTERED INDEX IX_NegativeListNotNull_Join ON NegativeList_NotNull(Basis, Alias, Nationality1, WLType1)")

    print("Recreating updated backup temporary tables...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS EntityGUID_Updated")
    cursor.execute("""
        CREATE TABLE EntityGUID_Updated (
            EntityGUID NVARCHAR(50) NULL,
            EntityAliasGUID NVARCHAR(50) NULL,
            WLType NVARCHAR(200) NULL,
            Nationality NVARCHAR(100) NULL,
            WLType1 NVARCHAR(255) NULL,
            Nationality1 NVARCHAR(255) NULL
        )
    """)
    
    cursor.execute("DROP TABLE IF EXISTS NegativeList_History")
    cursor.execute("""
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
    """)
    
    print("Backing up non-alias updated profiles to NegativeList_History...")
    sys.stdout.flush()
    cursor.execute("""
        INSERT INTO EntityGUID_Updated WITH (TABLOCK) (Nationality1, WLType1, EntityGUID, EntityAliasGUID, Nationality, WLType)
        SELECT DISTINCT B.Nationality1, B.WLType1, C.EntityGUID, C.EntityAliasGUID, C.Nationality, C.WLType
        FROM NegativeList A
        INNER JOIN NegativeList_NotNull B ON A.ID = B.ID
        INNER JOIN EntityGUID C ON C.EntityGUID = B.Basis AND C.Nationality1 = B.Nationality1 AND C.WLType1 = B.WLType1
        WHERE A.Alias IS NULL AND B.Alias IS NULL AND C.EntityAliasGUID IS NULL
    """)
    
    print("Backing up alias updated profiles to NegativeList_History...")
    sys.stdout.flush()
    cursor.execute("""
        INSERT INTO EntityGUID_Updated WITH (TABLOCK) (Nationality1, WLType1, EntityGUID, EntityAliasGUID, Nationality, WLType)
        SELECT DISTINCT B.Nationality1, B.WLType1, C.EntityGUID, C.EntityAliasGUID, C.Nationality, C.WLType
        FROM NegativeList A
        INNER JOIN NegativeList_NotNull B ON A.ID = B.ID
        INNER JOIN EntityGUID C ON C.EntityGUID = B.Basis AND C.EntityAliasGUID = B.Alias AND C.Nationality1 = B.Nationality1 AND C.WLType1 = B.WLType1
        WHERE A.Alias IS NOT NULL AND B.Alias IS NOT NULL AND C.EntityAliasGUID IS NOT NULL
    """)
    
    print("Filtering update candidates into NegativeList_Temp...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS NegativeList_Temp")
    cursor.execute("""
        CREATE TABLE NegativeList_Temp(
            ReferenceID [nvarchar](50) NULL, EntityType [nvarchar](50) NULL, Gender [nvarchar](50) NULL,
            FirstName [nvarchar](300) NULL, LastName [nvarchar](255) NULL, SecondName [nvarchar](500) NULL,
            Title [nvarchar](500) NULL, DOB [nvarchar](92) NULL, ALTDOB1 [datetime] NULL, ALTDOB2 [datetime] NULL,
            ALTDOB3 [datetime] NULL, AddressLine1 [nvarchar](255) NULL, AddressLine2 [nvarchar](255) NULL,
            City [nvarchar](50) NULL, Country [nvarchar](100) NULL, WLType [nvarchar](200) NULL,
            OriginalSource [nvarchar](MAX) NULL, Remark [nvarchar](4000) NULL, NationalIDInfo [nvarchar](250) NULL,
            NationalIDNo [nvarchar](50) NULL, IdOtherInfo1 [nvarchar](250) NULL, IdNo1 [nvarchar](250) NULL,
            IdOtherInfo2 [nvarchar](250) NULL, IdNo2 [nvarchar](250) NULL, IdOtherInfo3 [nvarchar](250) NULL,
            IdNo3 [nvarchar](250) NULL, IdOtherInfo4 [nvarchar](250) NULL, IdNo4 [nvarchar](250) NULL,
            IdOtherInfo5 [nvarchar](250) NULL, IdNo5 [nvarchar](250) NULL, EntityGUID [nvarchar](50) NULL,
            Nationality [nvarchar](100) NULL, Citizenship [nvarchar](100) NULL, POB [nvarchar](50) NULL,
            EntityAliasGUID [nvarchar](50) NULL, WLType1 [nvarchar](255) NULL, Nationality1 [nvarchar](255) NULL
        )
    """)
    
    cursor.execute("""
        INSERT INTO NegativeList_Temp WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title, DOB,
            ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, WLType, OriginalSource,
            Remark, NationalIDInfo, NationalIDNo, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
            IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID, Nationality, Citizenship, POB, EntityAliasGUID, WLType1, Nationality1
        )
        SELECT A.ReferenceID, A.EntityType, A.Gender, A.FirstName, A.LastName, A.SecondName, A.Title, A.DOB,
               A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, A.AddressLine1, A.AddressLine2, A.City, A.Country, A.WLType, A.OriginalSource,
               A.Remark, A.NationalIDInfo, A.NationalIDNo, A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3,
               A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5, A.EntityGUID, A.Nationality, A.Citizenship, A.POB, A.EntityAliasGUID, B.WLType1, B.Nationality1
        FROM NegativeList A
        INNER JOIN (
            SELECT DISTINCT EntityGUID, WLType1, Nationality1 
            FROM EntityGUID_Updated 
            WHERE EntityAliasGUID IS NULL
        ) B ON A.EntityGUID = B.EntityGUID AND ISNULL(A.WLType,'XYZ') = B.WLType1 AND ISNULL(A.Nationality,'ABC') = B.Nationality1
        WHERE A.EntityAliasGUID IS NULL
    """)
    
    cursor.execute("""
        INSERT INTO NegativeList_Temp WITH (TABLOCK) (
            ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title, DOB,
            ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, WLType, OriginalSource,
            Remark, NationalIDInfo, NationalIDNo, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
            IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID, Nationality, Citizenship, POB, EntityAliasGUID, WLType1, Nationality1
        )
        SELECT A.ReferenceID, A.EntityType, A.Gender, A.FirstName, A.LastName, A.SecondName, A.Title, A.DOB,
               A.ALTDOB1, A.ALTDOB2, A.ALTDOB3, A.AddressLine1, A.AddressLine2, A.City, A.Country, A.WLType, A.OriginalSource,
               A.Remark, A.NationalIDInfo, A.NationalIDNo, A.IdOtherInfo1, A.IdNo1, A.IdOtherInfo2, A.IdNo2, A.IdOtherInfo3, A.IdNo3,
               A.IdOtherInfo4, A.IdNo4, A.IdOtherInfo5, A.IdNo5, A.EntityGUID, A.Nationality, A.Citizenship, A.POB, A.EntityAliasGUID, B.WLType1, B.Nationality1
        FROM NegativeList A
        INNER JOIN (
            SELECT DISTINCT EntityGUID, EntityAliasGUID, WLType1, Nationality1 
            FROM EntityGUID_Updated 
            WHERE EntityAliasGUID IS NOT NULL
        ) B ON A.EntityGUID = B.EntityGUID AND A.EntityAliasGUID = B.EntityAliasGUID AND ISNULL(A.WLType,'XYZ') = B.WLType1 AND ISNULL(A.Nationality,'ABC') = B.Nationality1
        WHERE A.EntityAliasGUID IS NOT NULL
    """)
    
    print("Compiling incremental records to NegativeList_Update_INC...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS NegativeList_Update_INC")
    cursor.execute("""
        CREATE TABLE [NegativeList_Update_INC] (
            [ID] int, [ReferenceID] nvarchar(50), [EntityType] nvarchar(50), [Gender] nvarchar(50), 
            [FirstName] nvarchar(300), [LastName] nvarchar(255), [SecondName] nvarchar(500), [Title] nvarchar(500), 
            [DOB] nvarchar(92), [ALTDOB1] datetime, [ALTDOB2] datetime, [ALTDOB3] datetime, 
            [AddressLine1] nvarchar(255), [AddressLine2] nvarchar(255), [City] nvarchar(50), [Country] nvarchar(100), 
            [WLType] nvarchar(200), [OriginalSource] nvarchar(MAX), [Remark] nvarchar(4000), [NationalIDInfo] nvarchar(250), 
            [NationalIDNo] nvarchar(50), [IdOtherInfo1] nvarchar(250), [IdNo1] nvarchar(250), [IdOtherInfo2] nvarchar(250), 
            [IdNo2] nvarchar(250), [IdOtherInfo3] nvarchar(250), [IdNo3] nvarchar(250), [IdOtherInfo4] nvarchar(250), 
            [IdNo4] nvarchar(250), [IdOtherInfo5] nvarchar(250), [IdNo5] nvarchar(250), [EntityGUID] nvarchar(50), 
            [Nationality] nvarchar(100), [Citizenship] nvarchar(100), [POB] nvarchar(50), [EntityAliasGUID] nvarchar(50), 
            [WLType1] nvarchar(255), [Nationality1] nvarchar(255), 
            [EntityType_fm] int, [Gender_fm] nvarchar(7), [LastName_fm] nvarchar(150), [SecondName_fm] nvarchar(300), 
            [Title_fm] nvarchar(255), [AddressLine1_fm] nvarchar(200), [AddressLine2_fm] nvarchar(200), 
            [Citizenship_fm] nvarchar(70), [LastUpdatedDate] datetime, [Action] nvarchar(3), [LastUpdatedBy] int
        )
    """)
    
    cursor.execute("""
        INSERT INTO NegativeList_Update_INC WITH (TABLOCK) (
            ID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title, DOB,
            ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, WLType, OriginalSource,
            Remark, NationalIDInfo, NationalIDNo, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
            IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID, Nationality, Citizenship, POB, EntityAliasGUID, WLType1, Nationality1,
            EntityType_fm, Gender_fm, LastName_fm, SecondName_fm, Title_fm, AddressLine1_fm, AddressLine2_fm, Citizenship_fm,
            LastUpdatedDate, Action, LastUpdatedBy
        )
        SELECT N.ID, NT.ReferenceID, NT.EntityType, NT.Gender, NT.FirstName, NT.LastName, NT.SecondName, NT.Title, NT.DOB,
               NT.ALTDOB1, NT.ALTDOB2, NT.ALTDOB3, NT.AddressLine1, NT.AddressLine2, NT.City, NT.Country, NT.WLType, NT.OriginalSource,
               NT.Remark, NT.NationalIDInfo, NT.NationalIDNo, NT.IdOtherInfo1, NT.IdNo1, NT.IdOtherInfo2, NT.IdNo2, NT.IdOtherInfo3, NT.IdNo3,
               NT.IdOtherInfo4, NT.IdNo4, NT.IdOtherInfo5, NT.IdNo5, NT.EntityGUID, NT.Nationality, NT.Citizenship, NT.POB, NT.EntityAliasGUID, NT.WLType1, NT.Nationality1,
               CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END,
               SUBSTRING(NT.Gender, 1, 7), SUBSTRING(NT.LastName, 1, 150), SUBSTRING(NT.SecondName, 1, 300),
               SUBSTRING(NT.Title, 1, 255), SUBSTRING(NT.AddressLine1, 1, 200), SUBSTRING(NT.AddressLine2, 1, 200),
               SUBSTRING(NT.Citizenship, 1, 70), GETDATE(), 'chg', 3
        FROM NegativeList_Temp NT
        INNER JOIN NegativeList_NotNull A ON A.Basis = NT.EntityGUID AND A.Nationality1 = NT.Nationality1 AND A.WLType1 = NT.WLType1
        INNER JOIN NegativeList N ON A.ID = N.ID
        WHERE NT.EntityAliasGUID IS NULL AND A.Alias IS NULL AND N.Alias IS NULL
    """)
    
    cursor.execute("""
        INSERT INTO NegativeList_Update_INC WITH (TABLOCK) (
            ID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title, DOB,
            ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, WLType, OriginalSource,
            Remark, NationalIDInfo, NationalIDNo, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
            IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID, Nationality, Citizenship, POB, EntityAliasGUID, WLType1, Nationality1,
            EntityType_fm, Gender_fm, LastName_fm, SecondName_fm, Title_fm, AddressLine1_fm, AddressLine2_fm, Citizenship_fm,
            LastUpdatedDate, Action, LastUpdatedBy
        )
        SELECT N.ID, NT.ReferenceID, NT.EntityType, NT.Gender, NT.FirstName, NT.LastName, NT.SecondName, NT.Title, NT.DOB,
               NT.ALTDOB1, NT.ALTDOB2, NT.ALTDOB3, NT.AddressLine1, NT.AddressLine2, NT.City, NT.Country, NT.WLType, NT.OriginalSource,
               NT.Remark, NT.NationalIDInfo, NT.NationalIDNo, NT.IdOtherInfo1, NT.IdNo1, NT.IdOtherInfo2, NT.IdNo2, NT.IdOtherInfo3, NT.IdNo3,
               NT.IdOtherInfo4, NT.IdNo4, NT.IdOtherInfo5, NT.IdNo5, NT.EntityGUID, NT.Nationality, NT.Citizenship, NT.POB, NT.EntityAliasGUID, NT.WLType1, NT.Nationality1,
               CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END,
               SUBSTRING(NT.Gender, 1, 7), SUBSTRING(NT.LastName, 1, 150), SUBSTRING(NT.SecondName, 1, 300),
               SUBSTRING(NT.Title, 1, 255), SUBSTRING(NT.AddressLine1, 1, 200), SUBSTRING(NT.AddressLine2, 1, 200),
               SUBSTRING(NT.Citizenship, 1, 70), GETDATE(), 'chg', 3
        FROM NegativeList_Temp NT
        INNER JOIN NegativeList_NotNull A ON A.Basis = NT.EntityGUID AND A.Alias = NT.EntityAliasGUID AND A.Nationality1 = NT.Nationality1 AND A.WLType1 = NT.WLType1
        INNER JOIN NegativeList N ON A.ID = N.ID
        WHERE NT.EntityAliasGUID IS NOT NULL AND A.Alias IS NOT NULL AND N.Alias IS NOT NULL
    """)
    
    print("Filtering duplicate updates (Latest row per ID)...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS NegativeList_Update_INC1")
    cursor.execute("""
        CREATE TABLE [NegativeList_Update_INC1] (
            [ID] int PRIMARY KEY, [ReferenceID] nvarchar(50), [EntityType] nvarchar(50), [Gender] nvarchar(50), 
            [FirstName] nvarchar(300), [LastName] nvarchar(255), [SecondName] nvarchar(500), [Title] nvarchar(500), 
            [DOB] nvarchar(92), [ALTDOB1] datetime, [ALTDOB2] datetime, [ALTDOB3] datetime, 
            [AddressLine1] nvarchar(255), [AddressLine2] nvarchar(255), [City] nvarchar(50), [Country] nvarchar(100), 
            [WLType] nvarchar(200), [OriginalSource] nvarchar(MAX), [Remark] nvarchar(4000), [NationalIDInfo] nvarchar(250), 
            [NationalIDNo] nvarchar(50), [IdOtherInfo1] nvarchar(250), [IdNo1] nvarchar(250), [IdOtherInfo2] nvarchar(250), 
            [IdNo2] nvarchar(250), [IdOtherInfo3] nvarchar(250), [IdNo3] nvarchar(250), [IdOtherInfo4] nvarchar(250), 
            [IdNo4] nvarchar(250), [IdOtherInfo5] nvarchar(250), [IdNo5] nvarchar(250), [EntityGUID] nvarchar(50), 
            [Nationality] nvarchar(100), [Citizenship] nvarchar(100), [POB] nvarchar(50), [EntityAliasGUID] nvarchar(50), 
            [WLType1] nvarchar(255), [Nationality1] nvarchar(255), 
            [EntityType_fm] int, [Gender_fm] nvarchar(7), [LastName_fm] nvarchar(150), [SecondName_fm] nvarchar(300), 
            [Title_fm] nvarchar(255), [AddressLine1_fm] nvarchar(200), [AddressLine2_fm] nvarchar(200), 
            [Citizenship_fm] nvarchar(70), [LastUpdatedDate] datetime, [Action] nvarchar(3), [LastUpdatedBy] int, [rn] int
        )
    """)
    
    cursor.execute("""
        INSERT INTO NegativeList_Update_INC1 WITH (TABLOCK) (
            ID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title, DOB,
            ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, WLType, OriginalSource,
            Remark, NationalIDInfo, NationalIDNo, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
            IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID, Nationality, Citizenship, POB, EntityAliasGUID, WLType1, Nationality1,
            EntityType_fm, Gender_fm, LastName_fm, SecondName_fm, Title_fm, AddressLine1_fm, AddressLine2_fm, Citizenship_fm,
            LastUpdatedDate, Action, LastUpdatedBy, rn
        )
        SELECT ID, ReferenceID, EntityType, Gender, FirstName, LastName, SecondName, Title, DOB,
               ALTDOB1, ALTDOB2, ALTDOB3, AddressLine1, AddressLine2, City, Country, WLType, OriginalSource,
               Remark, NationalIDInfo, NationalIDNo, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3,
               IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5, EntityGUID, Nationality, Citizenship, POB, EntityAliasGUID, WLType1, Nationality1,
               EntityType_fm, Gender_fm, LastName_fm, SecondName_fm, Title_fm, AddressLine1_fm, AddressLine2_fm, Citizenship_fm,
               LastUpdatedDate, Action, LastUpdatedBy, rn
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY ID ORDER BY LastUpdatedDate DESC) AS rn 
            FROM NegativeList_Update_INC
        ) SourceData
        WHERE rn = 1
    """)
    
    print("Executing SQL MERGE (UPSERT) into NegativeList...")
    sys.stdout.flush()
    cursor.execute("""
        MERGE INTO NegativeList AS Dest
        USING (SELECT * FROM NegativeList_Update_INC1 WHERE rn = 1) AS source
        ON Dest.ID = source.ID
        WHEN MATCHED THEN
        UPDATE SET 
            Dest.ReferenceID = source.ReferenceID,
            Dest.EntityType = source.EntityType_fm, 
            Dest.Gender = source.Gender_fm,
            Dest.FirstName = source.FirstName,
            Dest.LastName = source.LastName_fm, 
            Dest.SecondName = source.SecondName_fm,
            Dest.Title = source.Title_fm, 
            Dest.DOB = source.DOB,
            Dest.ALTDOB1 = source.ALTDOB1,
            Dest.ALTDOB2 = source.ALTDOB2,
            Dest.ALTDOB3 = source.ALTDOB3, 
            Dest.AddressLine1 = source.AddressLine1_fm,
            Dest.AddressLine2 = source.AddressLine2_fm,
            Dest.City = source.City, 
            Dest.Country = source.Country,
            Dest.WLType = source.WLType,
            Dest.OriginalSource = source.OriginalSource, 
            Dest.NationalIDInfo = source.NationalIDInfo,
            Dest.NationalIDNo = source.NationalIDNo,
            Dest.IdOtherInfo1 = source.IdOtherInfo1, 
            Dest.IdNo1 = source.IdNo1,
            Dest.IdOtherInfo2 = source.IdOtherInfo2,
            Dest.IdNo2 = source.IdNo2, 
            Dest.IdOtherInfo3 = source.IdOtherInfo3,
            Dest.IdNo3 = source.IdNo3,
            Dest.IdOtherInfo4 = source.IdOtherInfo4, 
            Dest.IdNo4 = source.IdNo4,
            Dest.IdOtherInfo5 = source.IdOtherInfo5,
            Dest.IdNo5 = source.IdNo5, 
            Dest.Nationality = source.Nationality,
            Dest.Citizenship = source.Citizenship_fm,
            Dest.POB = source.POB, 
            Dest.LastUpdatedBy = source.LastUpdatedBy,
            Dest.LastUpdatedDate = source.LastUpdatedDate, 
            Dest.Action = source.Action;
    """)

    print("Updating alias change statuses in NegativeList...")
    sys.stdout.flush()
    cursor.execute("""
        UPDATE N 
        SET ReferenceID = NT.ReferenceID, 
            EntityType = CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END,
            Gender = SUBSTRING(NT.Gender,1,7),
            FirstName = NT.FirstName,
            LastName = SUBSTRING(NT.LastName,1,150),
            SecondName = SUBSTRING(NT.SecondName,1,300),
            Title = SUBSTRING(NT.Title,1,255),
            DOB = NT.DOB,
            ALTDOB1 = NT.ALTDOB1,
            ALTDOB2 = NT.ALTDOB2,
            ALTDOB3 = NT.ALTDOB3, 
            AddressLine1 = SUBSTRING(NT.AddressLine1,1,200),
            AddressLine2 = SUBSTRING(NT.AddressLine2,1,200),
            City = NT.City,
            Country = NT.Country,
            WLType = NT.WLType,
            OriginalSource = NT.OriginalSource,
            Remark = NT.Remark,
            NationalIDInfo = NT.NationalIDInfo,
            NationalIDNo = NT.NationalIDNo,
            IdOtherInfo1 = NT.IdOtherInfo1,
            IdNo1 = NT.IdNo1,
            IdOtherInfo2 = NT.IdOtherInfo2,
            IdNo2 = NT.IdNo2,
            IdOtherInfo3 = NT.IdOtherInfo3,
            IdNo3 = NT.IdNo3,
            IdOtherInfo4 = NT.IdOtherInfo4,
            IdNo4 = NT.IdNo4,
            IdOtherInfo5 = NT.IdOtherInfo5,
            IdNo5 = NT.IdNo5,
            Nationality = NT.Nationality,
            Citizenship = SUBSTRING(NT.Citizenship,1,70),
            POB = NT.POB,
            FileName = CONVERT(char(10), GETDATE(), 126),
            LastUpdatedBy = 3,
            LastUpdatedDate = GETDATE(),
            Action = 'chg'
        FROM (SELECT * FROM NegativeList WHERE Alias IS NOT NULL) N 
        INNER JOIN (SELECT * FROM NegativeList_Temp WHERE EntityAliasGUID IS NOT NULL) NT 
          ON N.Basis = NT.EntityGUID AND N.Alias = NT.EntityAliasGUID AND ISNULL(N.Nationality,'ABC') = ISNULL(NT.Nationality,'ABC') AND ISNULL(N.WLType,'ABC') = ISNULL(NT.WLType,'ABC')
    """)

    print("Updating non-alias change statuses in NegativeList...")
    sys.stdout.flush()
    cursor.execute("""
        UPDATE N 
        SET ReferenceID = NT.ReferenceID, 
            EntityType = CASE WHEN NT.EntityType='Individual' THEN 3 WHEN NT.EntityType='Country' THEN 1 WHEN NT.EntityType='Organization' THEN 9 WHEN NT.EntityType='Vessel' THEN 4 ELSE 6 END,
            Gender = SUBSTRING(NT.Gender,1,7),
            FirstName = NT.FirstName,
            LastName = SUBSTRING(NT.LastName,1,150),
            SecondName = SUBSTRING(NT.SecondName,1,300),
            Title = SUBSTRING(NT.Title,1,255),
            DOB = NT.DOB,
            ALTDOB1 = NT.ALTDOB1,
            ALTDOB2 = NT.ALTDOB2,
            ALTDOB3 = NT.ALTDOB3, 
            AddressLine1 = SUBSTRING(NT.AddressLine1,1,200),
            AddressLine2 = SUBSTRING(NT.AddressLine2,1,200),
            City = NT.City,
            Country = NT.Country,
            WLType = NT.WLType,
            OriginalSource = NT.OriginalSource,
            Remark = NT.Remark,
            NationalIDInfo = NT.NationalIDInfo,
            NationalIDNo = NT.NationalIDNo,
            IdOtherInfo1 = NT.IdOtherInfo1,
            IdNo1 = NT.IdNo1,
            IdOtherInfo2 = NT.IdOtherInfo2,
            IdNo2 = NT.IdNo2,
            IdOtherInfo3 = NT.IdOtherInfo3,
            IdNo3 = NT.IdNo3,
            IdOtherInfo4 = NT.IdOtherInfo4,
            IdNo4 = NT.IdNo4,
            IdOtherInfo5 = NT.IdOtherInfo5,
            IdNo5 = NT.IdNo5,
            Nationality = NT.Nationality,
            Citizenship = SUBSTRING(NT.Citizenship,1,70),
            POB = NT.POB,
            FileName = CONVERT(char(10), GETDATE(), 126),
            LastUpdatedBy = 3,
            LastUpdatedDate = GETDATE(),
            Action = 'chg'
        FROM (SELECT * FROM NegativeList WHERE Alias IS NULL) N 
        INNER JOIN (SELECT * FROM NegativeList_Temp WHERE EntityAliasGUID IS NULL) NT 
          ON N.Basis = NT.EntityGUID AND ISNULL(N.Nationality,'ABC') = ISNULL(NT.Nationality,'ABC') AND ISNULL(N.WLType,'ABC') = ISNULL(NT.WLType,'ABC')
    """)

    print("Rebuilding VersionID index & executing batch version updates...")
    sys.stdout.flush()
    cursor.execute("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NegativeList_VersionID' AND object_id = OBJECT_ID('NegativeList')) BEGIN CREATE NONCLUSTERED INDEX IX_NegativeList_VersionID ON NegativeList (VersionID) INCLUDE (CreationDate, LastUpdatedDate) END")
    
    cursor.execute("""
        DECLARE @NewVersionID INT;
        SELECT @NewVersionID = COALESCE(MAX(CAST(VersionID AS INT)), 0) + 1 FROM NegativeList WITH (READPAST);
        
        UPDATE nl WITH (ROWLOCK)
        SET nl.VersionID = @NewVersionID
        FROM NegativeList nl
        WHERE EXISTS (
            SELECT 1 FROM NegativeList n WITH (READPAST)
            WHERE n.ID = nl.ID AND (
                (n.CreationDate >= CAST(GETDATE() AS DATE) AND n.CreationDate < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR
                (n.LastUpdatedDate >= CAST(GETDATE() AS DATE) AND n.LastUpdatedDate < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)))
            )
        );
    """)

    print("Synchronizing search indexing in NegativeListFilter...")
    sys.stdout.flush()
    cursor.execute("IF OBJECT_ID('NegativeListFilter', 'U') IS NULL BEGIN CREATE TABLE NegativeListFilter (ID INT PRIMARY KEY, FirstName NVARCHAR(1000) NULL, LastName NVARCHAR(1000) NULL, Nationality NVARCHAR(255) NULL) END")
    
    cursor.execute("""
        INSERT INTO NegativeListFilter WITH (TABLOCK) (ID, FirstName, LastName, Nationality)
        SELECT i.ID, 
               UPPER(RTRIM(LTRIM(ISNULL(i.FirstName, '')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(i.LastName, '')))), 
               UPPER(RTRIM(LTRIM(ISNULL(i.LastName, '')))) + ' ' + UPPER(RTRIM(LTRIM(ISNULL(i.FirstName, '')))), 
               i.Nationality
        FROM NegativeList i
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
        WHERE NT.Action = 'chg' AND NT.LastUpdatedDate >= CAST(GETDATE() AS DATE) AND NT.LastUpdatedDate < DATEADD(DAY, 1, CAST(GETDATE() AS DATE));
    """)

    print("Writing execution statistics to NegativeList_History_Summary...")
    sys.stdout.flush()
    cursor.execute("IF OBJECT_ID('NegativeList_History_Summary', 'U') IS NULL BEGIN CREATE TABLE [NegativeList_History_Summary] ([Type] varchar(29), [Count] int, [RunDate] datetime) END")
    
    cursor.write = """
        INSERT INTO NegativeList_History_Summary WITH (TABLOCK) (Type, Count, RunDate)
        SELECT 'New Negative List Records', COUNT(*), GETDATE() FROM NegativeList WHERE CONVERT(VARCHAR, CreationDate, 23) = CONVERT(VARCHAR, GETDATE(), 23)
        UNION ALL
        SELECT 'Updated Negative List Records', COUNT(*), GETDATE() FROM NegativeList WHERE CONVERT(VARCHAR, LastUpdatedDate, 23) = CONVERT(VARCHAR, GETDATE(), 23)
        UNION ALL
        SELECT 'Total Negative List Records', COUNT(*), GETDATE() FROM NegativeList WHERE CONVERT(VARCHAR, CreationDate, 23) = CONVERT(VARCHAR, GETDATE(), 23) OR CONVERT(VARCHAR, LastUpdatedDate, 23) = CONVERT(VARCHAR, GETDATE(), 23)
    """
    cursor.execute(cursor.write)
    
    print("Cleaning up staging workspace temp tables...")
    sys.stdout.flush()
    cursor.execute("DROP TABLE IF EXISTS EntityGUID")
    cursor.execute("DROP TABLE IF EXISTS NegativeList_NotNull")
    cursor.execute("DROP TABLE IF EXISTS EntityGUID_Updated")
    cursor.execute("DROP TABLE IF EXISTS NegativeList_Temp")
    cursor.execute("DROP TABLE IF EXISTS NegativeList_Update_INC")
    cursor.execute("DROP TABLE IF EXISTS NegativeList_Update_INC1")
    
    conn.commit()
    print(f"Module 5 completed successfully! Time taken: {time.time() - global_start:.2f} seconds.")
    sys.stdout.flush()
    
except Exception as ex:
    conn.rollback()
    print(f"Module 5 failed! Rolled back changes. Error: {ex}")
    sys.stdout.flush()
    raise ex
    
finally:
    cursor.close()
    conn.close()
