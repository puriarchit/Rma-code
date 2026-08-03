import json
import os
import pyodbc
import time
from collections import defaultdict

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]

trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

conn_insert = pyodbc.connect(conn_str)
insert_cursor = conn_insert.cursor()
insert_cursor.fast_executemany = True

print("Starting Module 3 processing...")
global_start = time.time()

print("Running address formatting...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityAddress_Dup', 'U') IS NOT NULL DROP TABLE EntityAddress_Dup")
cursor.execute("CREATE TABLE [dbo].[EntityAddress_Dup]([EntityGUID] [nvarchar](50) NULL, [AddressLine1] [nvarchar](255) NULL, [AddressLine2] [nvarchar](255) NULL, [City] [nvarchar](50) NULL, [CountryCode] [nvarchar](50) NULL, [AddressLength] [int] NULL)")

cursor.execute("IF OBJECT_ID('EntityAddress_New', 'U') IS NOT NULL DROP TABLE EntityAddress_New")
cursor.execute("CREATE TABLE [dbo].[EntityAddress_New]([EntityGUID] [nvarchar](50) NULL, [AddressLine1] [nvarchar](255) NULL, [AddressLine2] [nvarchar](255) NULL, [City] [nvarchar](50) NULL, [CountryCode] [nvarchar](50) NULL, [POB] [nvarchar](50) NULL, [Country] [nvarchar](100) NULL)")

cursor.execute("IF OBJECT_ID('EntityAddress1', 'U') IS NOT NULL DROP TABLE EntityAddress1")
cursor.execute("CREATE TABLE [dbo].[EntityAddress1]([EntityGUID] [nvarchar](50) NULL, [AddressLine1] [nvarchar](255) NULL, [AddressLine2] [nvarchar](255) NULL, [City] [nvarchar](50) NULL, [CountryCode] [nvarchar](50) NULL)")

cursor.execute("IF OBJECT_ID('EntityAddress2', 'U') IS NOT NULL DROP TABLE EntityAddress2")
cursor.execute("CREATE TABLE [dbo].[EntityAddress2]([EntityGUID] [nvarchar](50) NULL, [AddressLine1] [nvarchar](255) NULL, [AddressLine2] [nvarchar](255) NULL, [City] [nvarchar](50) NULL, [CountryCode] [nvarchar](50) NULL, [AddressLength] [int] NULL, [Rank] [bigint] NULL)")

cursor.execute("IF OBJECT_ID('EntityAddress3', 'U') IS NOT NULL DROP TABLE EntityAddress3")
cursor.execute("CREATE TABLE [dbo].[EntityAddress3]([EntityGUID] [nvarchar](50) NULL, [AddressLine1] [nvarchar](255) NULL, [AddressLine2] [nvarchar](255) NULL, [City] [nvarchar](50) NULL, [CountryCode] [nvarchar](50) NULL, [AddressLength] [int] NULL, [rn] [bigint] NULL)")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, Address1, Address2, City, ISOStandard,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityAddress
        WHERE AddressTypeDesc != 'Place Of Birth'
    )
    INSERT INTO EntityAddress1 (EntityGUID, AddressLine1, AddressLine2, City, CountryCode)
    SELECT EntityGUID, Address1, Address2, City, ISOStandard
    FROM Scanned
    WHERE cnt = 1
""")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, Address1, Address2, City, ISOStandard,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityAddress
        WHERE AddressTypeDesc != 'Place Of Birth'
    )
    INSERT INTO EntityAddress_Dup (EntityGUID, AddressLine1, AddressLine2, City, CountryCode, AddressLength)
    SELECT EntityGUID, Address1, Address2, City, ISOStandard,
           ISNULL(LEN(Address1),0) + ISNULL(LEN(Address2),0) + ISNULL(LEN(City),0) + ISNULL(LEN(ISOStandard),0)
    FROM Scanned
    WHERE cnt > 1
""")
conn.commit()

cursor.execute("""
    INSERT INTO EntityAddress2 (EntityGUID, AddressLine1, AddressLine2, City, CountryCode, AddressLength, Rank)
    SELECT EntityGUID, AddressLine1, AddressLine2, City, CountryCode, AddressLength,
           RANK() OVER(PARTITION BY EntityGUID ORDER BY AddressLength DESC)
    FROM EntityAddress_Dup
""")
conn.commit()

cursor.execute("""
    ;WITH RankCounts AS (
        SELECT *, COUNT(*) OVER (PARTITION BY EntityGUID) as rank_count
        FROM EntityAddress2
        WHERE Rank = 1
    )
    INSERT INTO EntityAddress3 (EntityGUID, AddressLine1, AddressLine2, City, CountryCode, AddressLength, rn)
    SELECT EntityGUID, AddressLine1, AddressLine2, City, CountryCode, AddressLength,
           ROW_NUMBER() OVER (PARTITION BY EntityGUID ORDER BY AddressLength DESC) as rn
    FROM RankCounts
    WHERE rank_count > 1
""")
conn.commit()

# Optimization: Local Country reference lookup is now active!
cursor.execute("""
    ;WITH AllAddresses AS (
        SELECT EntityGUID, AddressLine1, AddressLine2, City, CountryCode
        FROM EntityAddress1
        UNION ALL
        SELECT EntityGUID, AddressLine1, AddressLine2, City, CountryCode
        FROM EntityAddress2 e
        WHERE Rank = 1 
          AND NOT EXISTS (
              SELECT 1 
              FROM EntityAddress3 a 
              WHERE a.EntityGUID = e.EntityGUID
          )
        UNION ALL
        SELECT EntityGUID, AddressLine1, AddressLine2, City, CountryCode
        FROM EntityAddress3
    ),
    POB_Data AS (
        SELECT EntityGUID, City AS POB
        FROM EntityAddress
        WHERE AddressTypeDesc = 'Place Of Birth'
        GROUP BY EntityGUID, City
    ),
    Country_Data AS (
        SELECT tCountry AS CountryName, tISO
        FROM Country
        GROUP BY tCountry, tISO
    )
    INSERT INTO EntityAddress_New (EntityGUID, AddressLine1, AddressLine2, City, CountryCode, POB, Country)
    SELECT 
        a.EntityGUID, 
        a.AddressLine1, 
        a.AddressLine2, 
        a.City, 
        a.CountryCode,
        p.POB,
        c.CountryName
    FROM AllAddresses a
    LEFT JOIN POB_Data p ON a.EntityGUID = p.EntityGUID
    LEFT JOIN Country_Data c ON a.CountryCode = c.tISO
""")
conn.commit()
print(f"Address formatting completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running citizenship mapping...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('Entity_Citizenship_Duplicate', 'U') IS NOT NULL DROP TABLE Entity_Citizenship_Duplicate")
cursor.execute("CREATE TABLE [dbo].[Entity_Citizenship_Duplicate]([EntityGUID] [nvarchar](50) NULL, [Rank] [bigint] NULL, [ISOStandard] [nvarchar](50) NULL, [AdministrativeUnitName] [nvarchar](200) NULL, [Citizenship] [nvarchar](100) NULL)")

cursor.execute("IF OBJECT_ID('Entity_Citizenship_New', 'U') IS NOT NULL DROP TABLE Entity_Citizenship_New")
cursor.execute("CREATE TABLE [dbo].[Entity_Citizenship_New]([EntityGUID] [nvarchar](50) NULL, [ISOStandard] [nvarchar](50) NULL, [Citizenship] [nvarchar](100) NULL)")
conn.commit()

# Optimization: Local Country reference lookup is now active!
cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, ISOStandard,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityCountryAssociation
        WHERE AssociationTypeDesc = 'Citizenship'
    )
    INSERT INTO Entity_Citizenship_New (EntityGUID, ISOStandard, Citizenship)
    SELECT s.EntityGUID, s.ISOStandard, c.tCountry
    FROM Scanned s
    LEFT JOIN Country c ON s.ISOStandard = c.tISO
    WHERE s.cnt = 1
""")
conn.commit()

# Optimization: Local Country reference lookup is now active!
cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, ISOStandard, AdministrativeUnitName,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityCountryAssociation
        WHERE AssociationTypeDesc = 'Citizenship'
    )
    INSERT INTO Entity_Citizenship_Duplicate (EntityGUID, ISOStandard, AdministrativeUnitName, Rank)
    SELECT EntityGUID, ISOStandard, AdministrativeUnitName,
           RANK() OVER(PARTITION BY EntityGUID ORDER BY AdministrativeUnitName DESC)
    FROM Scanned
    WHERE cnt > 1
""")
conn.commit()

# Optimization: Local Country reference lookup is now active!
cursor.execute("""
    INSERT INTO Entity_Citizenship_New (EntityGUID, ISOStandard, Citizenship)
    SELECT d.EntityGUID, d.ISOStandard, c.tCountry
    FROM (
        SELECT DISTINCT EntityGUID, ISOStandard
        FROM Entity_Citizenship_Duplicate
        WHERE Rank = 1
    ) d
    LEFT JOIN Country c ON d.ISOStandard = c.tISO
""")
conn.commit()
print(f"Citizenship mapping completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running nationalities merge...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityCountryAssociation_New', 'U') IS NOT NULL DROP TABLE EntityCountryAssociation_New")
cursor.execute("CREATE TABLE [dbo].[EntityCountryAssociation_New]([EntityGUID] [nvarchar](50) NULL, [Nationality] [nvarchar](4000) NULL)")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, AdministrativeUnitName,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityCountryAssociation
        WHERE AssociationTypeDesc = 'Nationality'
    )
    INSERT INTO EntityCountryAssociation_New (EntityGUID, Nationality)
    SELECT EntityGUID, AdministrativeUnitName
    FROM Scanned
    WHERE cnt = 1
""")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, AdministrativeUnitName,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityCountryAssociation
        WHERE AssociationTypeDesc = 'Nationality'
    )
    SELECT EntityGUID, AdministrativeUnitName
    FROM Scanned
    WHERE cnt > 1
    ORDER BY EntityGUID
""")

current_guid = None
current_nations = []
batch_to_insert = []
batch_size = 50000

while True:
    rows = cursor.fetchmany(batch_size)
    if not rows:
        break
    for guid, nation in rows:
        if guid != current_guid:
            if current_guid is not None:
                unique_nations = list(dict.fromkeys(current_nations))
                merged_nations = "; ".join(unique_nations)[:4000]
                batch_to_insert.append((current_guid, merged_nations))
                
                if len(batch_to_insert) >= batch_size:
                    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 4000, 0)])
                    insert_cursor.executemany("INSERT INTO EntityCountryAssociation_New (EntityGUID, Nationality) VALUES (?, ?)", batch_to_insert)
                    conn_insert.commit()
                    batch_to_insert = []
            current_guid = guid
            current_nations = [nation] if nation else [""]
        else:
            if nation:
                current_nations.append(nation)

if current_guid is not None:
    unique_nations = list(dict.fromkeys(current_nations))
    merged_nations = "; ".join(unique_nations)[:4000]
    batch_to_insert.append((current_guid, merged_nations))

if batch_to_insert:
    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 4000, 0)])
    insert_cursor.executemany("INSERT INTO EntityCountryAssociation_New (EntityGUID, Nationality) VALUES (?, ?)", batch_to_insert)
    conn_insert.commit()

print(f"Nationalities merge completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running DOB pivoting...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityDOB_Test', 'U') IS NOT NULL DROP TABLE EntityDOB_Test")
cursor.execute("CREATE TABLE [dbo].[EntityDOB_Test]([EntityGUID] [nvarchar](50) NULL, [DOB] [nvarchar](92) NULL, [row_rank] [bigint] NULL)")

cursor.execute("IF OBJECT_ID('EntityDOB_New', 'U') IS NOT NULL DROP TABLE EntityDOB_New")
cursor.execute("CREATE TABLE [dbo].[EntityDOB_New]([EntityGUID] [nvarchar](50) NULL, [DOB] [nvarchar](92) NULL, [ALTDOB1] [datetime] NULL, [ALTDOB2] [datetime] NULL, [ALTDOB3] [datetime] NULL)")
conn.commit()

cursor.execute("""
    INSERT INTO EntityDOB_Test (EntityGUID, DOB, row_rank)
    SELECT P.EntityGUID, p.DOB, 
           ROW_NUMBER() OVER (PARTITION BY P.EntityGUID ORDER BY p.DOB DESC) as row_rank
    FROM (
        SELECT EntityGUID, 
               DOB = CASE 
                   WHEN LEN(RTRIM(LTRIM(BirthMonth))) < 1 AND LEN(RTRIM(LTRIM(BirthDay))) < 1 THEN CAST(BirthYear as nvarchar) 
                   ELSE CAST(BirthYear as nvarchar) + '-' + CAST(BirthMonth as nvarchar) + '-' + CAST(BirthDay as nvarchar) 
               END 
        FROM EntityDOB
    ) p
    GROUP BY P.EntityGUID, p.DOB
""")
conn.commit()

cursor.execute("""
    INSERT INTO EntityDOB_New (EntityGUID, DOB, ALTDOB1, ALTDOB2, ALTDOB3)
    SELECT A.EntityGUID, A.DOB,
           CASE WHEN ISDATE(B.ALTDOB1) = 1 THEN CAST(B.ALTDOB1 AS DATETIME) ELSE NULL END,
           CASE WHEN ISDATE(C.ALTDOB2) = 1 THEN CAST(C.ALTDOB2 AS DATETIME) ELSE NULL END,
           CASE WHEN ISDATE(D.ALTDOB3) = 1 THEN CAST(D.ALTDOB3 AS DATETIME) ELSE NULL END
    FROM (SELECT EntityGUID, DOB FROM EntityDOB_Test WHERE row_rank = 1) A
    LEFT JOIN (SELECT EntityGUID, DOB AS ALTDOB1 FROM EntityDOB_Test WHERE row_rank = 2 AND LEN(DOB) > 7) B ON A.EntityGUID = B.EntityGUID
    LEFT JOIN (SELECT EntityGUID, DOB AS ALTDOB2 FROM EntityDOB_Test WHERE row_rank = 3 AND LEN(DOB) > 7) C ON A.EntityGUID = C.EntityGUID
    LEFT JOIN (SELECT EntityGUID, DOB AS ALTDOB3 FROM EntityDOB_Test WHERE row_rank = 4 AND LEN(DOB) > 7) D ON A.EntityGUID = D.EntityGUID
""")
conn.commit()
print(f"DOB pivoting completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running identification cards pivoting...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityIdentification_National', 'U') IS NOT NULL DROP TABLE EntityIdentification_National")
cursor.execute("CREATE TABLE [dbo].[EntityIdentification_National]([EntityGUID] [nvarchar](50) NULL, [IdentificationTypeDesc] [nvarchar](85) NULL, [IdentificationNumber] [nvarchar](50) NULL)")

cursor.execute("IF OBJECT_ID('EntityIdentification_National_New', 'U') IS NOT NULL DROP TABLE EntityIdentification_National_New")
cursor.execute("CREATE TABLE [dbo].[EntityIdentification_National_New]([EntityGUID] [nvarchar](50) NULL, [IdentificationNumber] [nvarchar](50) NULL, [IdentificationTypeDesc] [nvarchar](250) NULL)")

cursor.execute("IF OBJECT_ID('EntityIdentification_New', 'U') IS NOT NULL DROP TABLE EntityIdentification_New")
cursor.execute("CREATE TABLE [dbo].[EntityIdentification_New]([EntityGUID] [nvarchar](50) NULL, [IdOtherInfo1] [nvarchar](250) NULL, [IdNo1] [nvarchar](250) NULL, [IdOtherInfo2] [nvarchar](250) NULL, [IdNo2] [nvarchar](250) NULL, [IdOtherInfo3] [nvarchar](250) NULL, [IdNo3] [nvarchar](250) NULL, [IdOtherInfo4] [nvarchar](250) NULL, [IdNo4] [nvarchar](250) NULL, [IdOtherInfo5] [nvarchar](250) NULL, [IdNo5] [nvarchar](250) NULL)")

cursor.execute("IF OBJECT_ID('EntityIdentification_Test', 'U') IS NOT NULL DROP TABLE EntityIdentification_Test")
cursor.execute("CREATE TABLE [dbo].[EntityIdentification_Test]([EntityGUID] [nvarchar](50) NULL, [IdentificationTypeDesc] [nvarchar](85) NULL, [IdentificationNumber] [nvarchar](50) NULL, [row_rank] [bigint] NULL)")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, IdentificationTypeDesc, IdentificationNumber,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityIdentification
        WHERE IdentificationTypeDesc LIKE 'National Id%'
    )
    INSERT INTO EntityIdentification_National (EntityGUID, IdentificationTypeDesc, IdentificationNumber)
    SELECT EntityGUID, IdentificationTypeDesc, IdentificationNumber
    FROM Scanned
    WHERE cnt = 1
""")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, IdentificationTypeDesc, IdentificationNumber,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityIdentification
        WHERE IdentificationTypeDesc LIKE 'National Id%'
    )
    SELECT EntityGUID, IdentificationTypeDesc, IdentificationNumber
    FROM Scanned
    WHERE cnt > 1
    ORDER BY EntityGUID
""")

current_guid = None
current_types = []
current_numbers = []
batch_national = []

while True:
    rows = cursor.fetchmany(batch_size)
    if not rows:
        break
    for guid, id_type, id_num in rows:
        if guid != current_guid:
            if current_guid is not None:
                uniq_types = list(dict.fromkeys(current_types))
                uniq_nums = list(dict.fromkeys(current_numbers))
                merged_types = "; ".join(uniq_types)[:85]
                merged_nums = "; ".join(uniq_nums)[:50]
                batch_national.append((current_guid, merged_types, merged_nums))
                
                if len(batch_national) >= batch_size:
                    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 85, 0), (pyodbc.SQL_WVARCHAR, 50, 0)])
                    insert_cursor.executemany("INSERT INTO EntityIdentification_National (EntityGUID, IdentificationTypeDesc, IdentificationNumber) VALUES (?, ?, ?)", batch_national)
                    conn_insert.commit()
                    batch_national = []
            current_guid = guid
            current_types = [id_type] if id_type else [""]
            current_numbers = [id_num] if id_num else [""]
        else:
            if id_type: current_types.append(id_type)
            if id_num: current_numbers.append(id_num)

if current_guid is not None:
    uniq_types = list(dict.fromkeys(current_types))
    uniq_nums = list(dict.fromkeys(current_numbers))
    merged_types = "; ".join(uniq_types)[:85]
    merged_nums = "; ".join(uniq_nums)[:50]
    batch_national.append((current_guid, merged_types, merged_nums))

if batch_national:
    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 85, 0), (pyodbc.SQL_WVARCHAR, 50, 0)])
    insert_cursor.executemany("INSERT INTO EntityIdentification_National (EntityGUID, IdentificationTypeDesc, IdentificationNumber) VALUES (?, ?, ?)", batch_national)
    conn_insert.commit()

cursor.execute("""
    INSERT INTO EntityIdentification_National_New (EntityGUID, IdentificationNumber, IdentificationTypeDesc)
    SELECT EntityGUID, IdentificationNumber, 
           CASE WHEN LEN(IdentificationTypeDesc) < 250 THEN IdentificationTypeDesc ELSE SUBSTRING(IdentificationTypeDesc, 1, 250) END
    FROM (
        SELECT SS.EntityGUID, SS.IdentificationNumber,
               STUFF((SELECT '; ' + US.IdentificationTypeDesc 
                      FROM (SELECT * FROM EntityIdentification_National WHERE EntityGUID IN (
                          SELECT EntityGUID FROM EntityIdentification_National GROUP BY EntityGUID HAVING COUNT(*) > 1
                      )) US WHERE US.EntityGUID = SS.EntityGUID FOR XML PATH('')), 1, 1, '') IdentificationTypeDesc
        FROM (SELECT * FROM EntityIdentification_National WHERE EntityGUID IN (
            SELECT EntityGUID FROM EntityIdentification_National GROUP BY EntityGUID HAVING COUNT(*) > 1
        )) SS GROUP BY SS.EntityGUID, SS.IdentificationNumber
    ) A
    UNION ALL
    SELECT EntityGUID, IdentificationNumber, IdentificationTypeDesc
    FROM EntityIdentification_National
    WHERE EntityGUID NOT IN (
        SELECT EntityGUID FROM EntityIdentification_National GROUP BY EntityGUID HAVING COUNT(*) > 1
    )
""")
conn.commit()

cursor.execute("""
    INSERT INTO EntityIdentification_Test (EntityGUID, IdentificationTypeDesc, IdentificationNumber, row_rank)
    SELECT P.EntityGUID, P.IdentificationTypeDesc, P.IdentificationNumber,
           ROW_NUMBER() OVER (PARTITION BY P.EntityGUID ORDER BY P.IdentificationNumber DESC) as row_rank
    FROM (
        SELECT EntityGUID, 
               CASE WHEN LEN(IdentificationTypeDesc) < 85 THEN IdentificationTypeDesc ELSE SUBSTRING(IdentificationTypeDesc, 1, 85) END AS IdentificationTypeDesc, 
               CASE WHEN LEN(IdentificationNumber) < 50 THEN IdentificationNumber ELSE SUBSTRING(IdentificationNumber, 1, 50) END AS IdentificationNumber
        FROM EntityIdentification e
        WHERE NOT EXISTS (
            SELECT 1 
            FROM EntityIdentification_National_New n 
            WHERE n.EntityGUID = e.EntityGUID
        )
    ) P
""")
conn.commit()

cursor.execute("""
    INSERT INTO EntityIdentification_New (EntityGUID, IdOtherInfo1, IdNo1, IdOtherInfo2, IdNo2, IdOtherInfo3, IdNo3, IdOtherInfo4, IdNo4, IdOtherInfo5, IdNo5)
    SELECT A.EntityGUID, A.IdOtherInfo1, A.IdNo1,
           B.IdOtherInfo2, B.IdNo2,
           C.IdOtherInfo3, C.IdNo3,
           D.IdOtherInfo4, D.IdNo4,
           E.IdOtherInfo5, E.IdNo5
    FROM (SELECT EntityGUID, IdentificationTypeDesc IdOtherInfo1, IdentificationNumber IdNo1 FROM EntityIdentification_Test WHERE row_rank = 1) A
    LEFT JOIN (SELECT EntityGUID, IdentificationTypeDesc IdOtherInfo2, IdentificationNumber IdNo2 FROM EntityIdentification_Test WHERE row_rank = 2) B ON A.EntityGUID = B.EntityGUID
    LEFT JOIN (SELECT EntityGUID, IdentificationTypeDesc IdOtherInfo3, IdentificationNumber IdNo3 FROM EntityIdentification_Test WHERE row_rank = 3) C ON A.EntityGUID = C.EntityGUID
    LEFT JOIN (SELECT EntityGUID, IdentificationTypeDesc IdOtherInfo4, IdentificationNumber IdNo4 FROM EntityIdentification_Test WHERE row_rank = 4) D ON A.EntityGUID = D.EntityGUID
    LEFT JOIN (SELECT EntityGUID, IdentificationTypeDesc IdOtherInfo5, IdentificationNumber IdNo5 FROM EntityIdentification_Test WHERE row_rank = 5) E ON A.EntityGUID = E.EntityGUID
""")
conn.commit()
print(f"Identification cards pivoting completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running remarks merge...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityRemark_DUP', 'U') IS NOT NULL DROP TABLE EntityRemark_DUP")
cursor.execute("CREATE TABLE [dbo].[EntityRemark_DUP]([EntityGUID] [nvarchar](50) NULL, [EntityRemarkGUID] [nvarchar](50) NULL, [Remark] [nvarchar](4000) NULL, [LastUpdated] [datetime] NULL)")

cursor.execute("IF OBJECT_ID('EntityRemark_New', 'U') IS NOT NULL DROP TABLE EntityRemark_New")
cursor.execute("CREATE TABLE [dbo].[EntityRemark_New]([EntityGUID] [nvarchar](50) NULL, [Remark] [nvarchar](4000) NULL)")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, Remark,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityRemark
    )
    INSERT INTO EntityRemark_New (EntityGUID, Remark)
    SELECT EntityGUID, Remark
    FROM Scanned
    WHERE cnt = 1
""")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, EntityRemarkGUID, Remark, LastUpdated,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityRemark
    )
    INSERT INTO EntityRemark_DUP (EntityGUID, EntityRemarkGUID, Remark, LastUpdated)
    SELECT EntityGUID, EntityRemarkGUID, Remark, LastUpdated
    FROM Scanned
    WHERE cnt > 1
""")
conn.commit()

cursor.execute("""
    SELECT EntityGUID, Remark
    FROM EntityRemark_DUP
    ORDER BY EntityGUID
""")

current_guid = None
current_remarks = []
batch_remark = []

while True:
    rows = cursor.fetchmany(batch_size)
    if not rows:
        break
    for guid, remark in rows:
        if guid != current_guid:
            if current_guid is not None:
                unique_remarks = list(dict.fromkeys(current_remarks))
                merged_remarks = "; ".join(unique_remarks)[:4000]
                batch_remark.append((current_guid, merged_remarks))
                
                if len(batch_remark) >= batch_size:
                    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 4000, 0)])
                    insert_cursor.executemany("INSERT INTO EntityRemark_New (EntityGUID, Remark) VALUES (?, ?)", batch_remark)
                    conn_insert.commit()
                    batch_remark = []
            current_guid = guid
            current_remarks = [remark] if remark else [""]
        else:
            if remark:
                current_remarks.append(remark)

if current_guid is not None:
    unique_remarks = list(dict.fromkeys(current_remarks))
    merged_remarks = "; ".join(unique_remarks)[:4000]
    batch_remark.append((current_guid, merged_remarks))

if batch_remark:
    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 4000, 0)])
    insert_cursor.executemany("INSERT INTO EntityRemark_New (EntityGUID, Remark) VALUES (?, ?)", batch_remark)
    conn_insert.commit()

print(f"Remarks merge completed. Time taken: {time.time() - start_time:.2f} seconds")

conn_insert.close()
conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60

print(f"Process completed. Total time: {total_time:.2f} minutes.")


