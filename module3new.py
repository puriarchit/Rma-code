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
    print("Database optimized, set to SIMPLE, and log file shrunk successfully!")
except Exception as e:
    print("Database maintenance warning:", e)

cursor.execute("IF OBJECT_ID('Country', 'U') IS NULL BEGIN CREATE TABLE Country (tISO nvarchar(10) NULL, tCountry nvarchar(100) NULL) END")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM Country")
if cursor.fetchone()[0] == 0:
    countries = [
        ('AF', 'Afghanistan'), ('AL', 'Albania'), ('DZ', 'Algeria'), ('AS', 'American Samoa'), 
        ('AD', 'Andorra'), ('AO', 'Angola'), ('AI', 'Anguilla'), ('AQ', 'Antarctica'), 
        ('AG', 'Antigua and Barbuda'), ('AR', 'Argentina'), ('AM', 'Armenia'), ('AW', 'Aruba'), 
        ('AU', 'Australia'), ('AT', 'Austria'), ('AZ', 'Azerbaijan'), ('BS', 'Bahamas'), 
        ('BH', 'Bahrain'), ('BD', 'Bangladesh'), ('BB', 'Barbados'), ('BY', 'Belarus'), 
        ('BE', 'Belgium'), ('BZ', 'Belize'), ('BJ', 'Benin'), ('BM', 'Bermuda'), 
        ('BT', 'Bhutan'), ('BO', 'Bolivia'), ('BA', 'Bosnia and Herzegovina'), ('BW', 'Botswana'), 
        ('BR', 'Brazil'), ('IO', 'British Indian Ocean Territory'), ('VG', 'British Virgin Islands'), 
        ('BN', 'Brunei'), ('BG', 'Bulgaria'), ('BF', 'Burkina Faso'), ('BI', 'Burundi'), 
        ('KH', 'Cambodia'), ('CM', 'Cameroon'), ('CA', 'Canada'), ('CV', 'Cape Verde'), 
        ('KY', 'Cayman Islands'), ('CF', 'Central African Republic'), ('TD', 'Chad'), 
        ('CL', 'Chile'), ('CN', 'China'), ('CX', 'Christmas Island'), ('CC', 'Cocos Islands'), 
        ('CO', 'Colombia'), ('KM', 'Comoros'), ('CK', 'Cook Islands'), ('CR', 'Costa Rica'), 
        ('HR', 'Croatia'), ('CU', 'Cuba'), ('CY', 'Cyprus'), ('CZ', 'Czech Republic'), 
        ('CD', 'Democratic Republic of the Congo'), ('DK', 'Denmark'), ('DJ', 'Djibouti'), 
        ('DM', 'Dominica'), ('DO', 'Dominican Republic'), ('TL', 'East Timor'), ('EC', 'Ecuador'), 
        ('EG', 'Egypt'), ('SV', 'El Salvador'), ('GQ', 'Equatorial Guinea'), ('ER', 'Eritrea'), 
        ('EE', 'Estonia'), ('ET', 'Ethiopia'), ('FK', 'Falkland Islands'), ('FO', 'Faroe Islands'), 
        ('FJ', 'Fiji'), ('FI', 'Finland'), ('FR', 'France'), ('GF', 'French Guiana'), 
        ('PF', 'French Polynesia'), ('GA', 'Gabon'), ('GM', 'Gambia'), ('GE', 'Georgia'), 
        ('DE', 'Germany'), ('GH', 'Ghana'), ('GI', 'Gibraltar'), ('GR', 'Greece'), 
        ('GL', 'Greenland'), ('GD', 'Grenada'), ('GP', 'Guadeloupe'), ('GU', 'Guam'), 
        ('GT', 'Guatemala'), ('GN', 'Guinea'), ('GW', 'Guinea-Bissau'), ('GY', 'Guyana'), 
        ('HT', 'Haiti'), ('HN', 'Honduras'), ('HK', 'Hong Kong'), ('HU', 'Hungary'), 
        ('IS', 'Iceland'), ('IN', 'India'), ('ID', 'Indonesia'), ('IR', 'Iran'), 
        ('IQ', 'Iraq'), ('IE', 'Ireland'), ('IL', 'Israel'), ('IT', 'Italy'), 
        ('CI', 'Ivory Coast'), ('JM', 'Jamaica'), ('JP', 'Japan'), ('JO', 'Jordan'), 
        ('KZ', 'Kazakhstan'), ('KE', 'Kenya'), ('KI', 'Kiribati'), ('XK', 'Kosovo'), 
        ('KW', 'Kuwait'), ('KG', 'Kyrgyzstan'), ('LA', 'Laos'), ('LV', 'Latvia'), 
        ('LB', 'Lebanon'), ('LS', 'Lesotho'), ('LR', 'Liberia'), ('LY', 'Libya'), 
        ('LI', 'Liechtenstein'), ('LT', 'Lithuania'), ('LU', 'Luxembourg'), ('MO', 'Macau'), 
        ('MK', 'Macedonia'), ('MG', 'Madagascar'), ('MW', 'Malawi'), ('MY', 'Malaysia'), 
        ('MV', 'Maldives'), ('ML', 'Mali'), ('MT', 'Malta'), ('MH', 'Marshall Islands'), 
        ('MQ', 'Martinique'), ('MR', 'Mauritania'), ('MU', 'Mauritius'), ('YT', 'Mayotte'), 
        ('MX', 'Mexico'), ('FM', 'Micronesia'), ('MD', 'Moldova'), ('MC', 'Monaco'), 
        ('MN', 'Mongolia'), ('ME', 'Montenegro'), ('MS', 'Montserrat'), ('MA', 'Morocco'), 
        ('MZ', 'Mozambique'), ('MM', 'Myanmar'), ('NA', 'Namibia'), ('NR', 'Nauru'), 
        ('NP', 'Nepal'), ('NL', 'Netherlands'), ('AN', 'Netherlands Antilles'), 
        ('NC', 'New Caledonia'), ('NZ', 'New Zealand'), ('NI', 'Nicaragua'), ('NE', 'Niger'), 
        ('NG', 'Nigeria'), ('NU', 'Niue'), ('KP', 'North Korea'), ('MP', 'Northern Mariana Islands'), 
        ('NO', 'Norway'), ('OM', 'Oman'), ('PK', 'Pakistan'), ('PW', 'Palau'), 
        ('PS', 'Palestine'), ('PA', 'Panama'), ('PG', 'Papua New Guinea'), ('PY', 'Paraguay'), 
        ('PE', 'Peru'), ('PH', 'Philippines'), ('PN', 'Pitcairn'), ('PL', 'Poland'), 
        ('PT', 'Portugal'), ('PR', 'Puerto Rico'), ('QA', 'Qatar'), ('CG', 'Republic of the Congo'), 
        ('RE', 'Reunion'), ('RO', 'Romania'), ('RU', 'Russia'), ('RW', 'Rwanda'), 
        ('BL', 'Saint Barthelemy'), ('SH', 'Saint Helena'), ('KN', 'Saint Kitts and Nevis'), 
        ('LC', 'Saint Lucia'), ('MF', 'Saint Martin'), ('PM', 'Saint Pierre and Miquelon'), 
        ('VC', 'Saint Vincent and the Grenadines'), ('WS', 'Samoa'), ('SM', 'San Marino'), 
        ('ST', 'Sao Tome and Principe'), ('SA', 'Saudi Arabia'), ('SN', 'Senegal'), 
        ('RS', 'Serbia'), ('SC', 'Segoe UI'), ('SL', 'Sierra Leone'), ('SG', 'Singapore'), 
        ('SX', 'Sint Maarten'), ('SK', 'Slovakia'), ('SI', 'Slovenia'), ('SB', 'Solomon Islands'), 
        ('SO', 'Solomons'), ('ZA', 'South Africa'), ('GS', 'South Georgia'), 
        ('KR', 'South Korea'), ('SS', 'South Sudan'), ('ES', 'Spain'), ('LK', 'Sri Lanka'), 
        ('SD', 'Sudan'), ('SR', 'Suriname'), ('SJ', 'Svalbard'), ('SZ', 'Swaziland'), 
        ('SE', 'Sweden'), ('CH', 'Switzerland'), ('SY', 'Syria'), ('TW', 'Taiwan'), 
        ('TJ', 'Tajikistan'), ('TZ', 'Tanzania'), ('TH', 'Thailand'), ('TG', 'Togo'), 
        ('TK', 'Tokelau'), ('TO', 'Tonga'), ('TT', 'Trinidad and Tobago'), ('TN', 'Tunisia'), 
        ('TR', 'Turkey'), ('TM', 'Turkmenistan'), ('TC', 'Turks and Caicos'), 
        ('TV', 'Tuvalu'), ('VI', 'U.S. Virgin Islands'), ('UG', 'Uganda'), ('UA', 'Ukraine'), 
        ('AE', 'United Arab Emirates'), ('GB', 'United Kingdom'), ('US', 'United States'), 
        ('UY', 'Uruguay'), ('UZ', 'Uzbekistan'), ('VU', 'Vanuatu'), ('VA', 'Vatican City'), 
        ('VE', 'Venezuela'), ('VN', 'Vietnam'), ('WF', 'Wallis and Futuna'), ('EH', 'Western Sahara'), 
        ('YE', 'Yemen'), ('ZM', 'Zambia'), ('ZW', 'Zimbabwe')
    ]
    insert_cursor = conn.cursor()
    insert_cursor.fast_executemany = True
    insert_cursor.executemany("INSERT INTO Country (tISO, tCountry) VALUES (?, ?)", countries)
    conn.commit()

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

cursor.execute("DROP TABLE IF EXISTS EntityAddress1")
cursor.execute("DROP TABLE IF EXISTS EntityAddress2")
cursor.execute("DROP TABLE IF EXISTS EntityAddress3")
cursor.execute("DROP TABLE IF EXISTS EntityAddress_Dup")
conn.commit()

print(f"Address formatting completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running citizenship mapping...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('Entity_Citizenship_Duplicate', 'U') IS NOT NULL DROP TABLE Entity_Citizenship_Duplicate")
cursor.execute("CREATE TABLE [dbo].[Entity_Citizenship_Duplicate]([EntityGUID] [nvarchar](50) NULL, [Rank] [bigint] NULL, [ISOStandard] [nvarchar](50) NULL, [AdministrativeUnitName] [nvarchar](200) NULL, [Citizenship] [nvarchar](100) NULL)")

cursor.execute("IF OBJECT_ID('Entity_Citizenship_New', 'U') IS NOT NULL DROP TABLE Entity_Citizenship_New")
cursor.execute("CREATE TABLE [dbo].[Entity_Citizenship_New]([EntityGUID] [nvarchar](50) NULL, [ISOStandard] [nvarchar](50) NULL, [Citizenship] [nvarchar](100) NULL)")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, ISOStandard,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityCountryAssociation
        WHERE AssociationTypeDesc = 'Citizenship'
    )
    INSERT INTO Entity_Citizenship_New (EntityGUID, ISOStandard, Citizenship)
    SELECT s.EntityGUID, s.ISOStandard, SUBSTRING(c.tCountry, 1, 100)
    FROM Scanned s
    LEFT JOIN Country c ON s.ISOStandard = c.tISO
    WHERE s.cnt = 1
""")
conn.commit()

cursor.execute("""
    ;WITH Scanned AS (
        SELECT EntityGUID, ISOStandard, AdministrativeUnitName,
               COUNT(*) OVER (PARTITION BY EntityGUID) as cnt
        FROM EntityCountryAssociation
        WHERE AssociationTypeDesc = 'Citizenship'
    )
    INSERT INTO Entity_Citizenship_Duplicate (EntityGUID, ISOStandard, AdministrativeUnitName, Rank)
    SELECT EntityGUID, ISOStandard, SUBSTRING(AdministrativeUnitName, 1, 200),
           RANK() OVER(PARTITION BY EntityGUID ORDER BY AdministrativeUnitName DESC)
    FROM Scanned
    WHERE cnt > 1
""")
conn.commit()

cursor.execute("""
    INSERT INTO Entity_Citizenship_New (EntityGUID, ISOStandard, Citizenship)
    SELECT d.EntityGUID, d.ISOStandard, SUBSTRING(c.tCountry, 1, 100)
    FROM (
        SELECT DISTINCT EntityGUID, ISOStandard
        FROM Entity_Citizenship_Duplicate
        WHERE Rank = 1
    ) d
    LEFT JOIN Country c ON d.ISOStandard = c.tISO
""")
conn.commit()

cursor.execute("DROP TABLE IF EXISTS Entity_Citizenship_Duplicate")
conn.commit()

print(f"Citizenship mapping completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running nationalities merge (Optimized via STRING_AGG)...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityCountryAssociation_New', 'U') IS NOT NULL DROP TABLE EntityCountryAssociation_New")
cursor.execute("CREATE TABLE [dbo].[EntityCountryAssociation_New]([EntityGUID] [nvarchar](50) NULL, [Nationality] [nvarchar](4000) NULL)")
conn.commit()

# Single-pass high-performance aggregation directly in SQL Server (replaces the slow python batching loop!)
cursor.execute("""
    ;WITH DistinctNations AS (
        SELECT DISTINCT A.EntityGUID, B.tCountry AS Nationality
        FROM EntityCountryAssociation A
        LEFT JOIN Country B ON A.ISOStandard = B.tISO
        WHERE A.AssociationTypeDesc = 'Nationality'
          AND B.tCountry IS NOT NULL
    )
    INSERT INTO EntityCountryAssociation_New (EntityGUID, Nationality)
    SELECT 
        EntityGUID,
        SUBSTRING(STRING_AGG(CAST(Nationality AS VARCHAR(MAX)), '; '), 1, 4000)
    FROM DistinctNations
    GROUP BY EntityGUID
""")
conn.commit()

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

cursor.execute("DROP TABLE IF EXISTS EntityDOB_Test")
conn.commit()

print(f"DOB pivoting completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running identification cards pivoting (Optimized via STRING_AGG)...")
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

# Single-pass high-performance identification mapping (replaces the slow python loop)
cursor.execute("""
    ;WITH DistinctIDs AS (
        SELECT DISTINCT EntityGUID, IdentificationTypeDesc, IdentificationNumber
        FROM EntityIdentification
        WHERE IdentificationTypeDesc LIKE 'National Id%'
          AND IdentificationNumber IS NOT NULL
    )
    INSERT INTO EntityIdentification_National (EntityGUID, IdentificationTypeDesc, IdentificationNumber)
    SELECT 
        EntityGUID,
        SUBSTRING(STRING_AGG(CAST(IdentificationTypeDesc AS VARCHAR(MAX)), '; '), 1, 85),
        SUBSTRING(STRING_AGG(CAST(IdentificationNumber AS VARCHAR(MAX)), '; '), 1, 50)
    FROM DistinctIDs
    GROUP BY EntityGUID
""")
conn.commit()

# Single-pass high-performance STUFF XML replacement via STRING_AGG (takes seconds instead of 9 minutes!)
cursor.execute("""
    ;WITH GroupedIDs AS (
        SELECT 
            EntityGUID, 
            IdentificationNumber,
            SUBSTRING(STRING_AGG(CAST(IdentificationTypeDesc AS VARCHAR(MAX)), '; '), 1, 250) AS IdentificationTypeDesc
        FROM EntityIdentification_National
        GROUP BY EntityGUID, IdentificationNumber
    )
    INSERT INTO EntityIdentification_National_New (EntityGUID, IdentificationNumber, IdentificationTypeDesc)
    SELECT EntityGUID, IdentificationNumber, IdentificationTypeDesc
    FROM GroupedIDs
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

cursor.execute("DROP TABLE IF EXISTS EntityIdentification_National")
cursor.execute("DROP TABLE IF EXISTS EntityIdentification_Test")
conn.commit()

print(f"Identification cards pivoting completed. Time taken: {time.time() - start_time:.2f} seconds")

print("Running remarks merge (Optimized via STRING_AGG)...")
start_time = time.time()

cursor.execute("IF OBJECT_ID('EntityRemark_DUP', 'U') IS NOT NULL DROP TABLE EntityRemark_DUP")
cursor.execute("IF OBJECT_ID('EntityRemark_New', 'U') IS NOT NULL DROP TABLE EntityRemark_New")
cursor.execute("CREATE TABLE [dbo].[EntityRemark_New]([EntityGUID] [nvarchar](50) NULL, [Remark] [nvarchar](4000) NULL)")
conn.commit()

# Clustered Temp Table Optimization to force Stream Aggregate (replaces slow tempdb page-spills!)
cursor.execute("DROP TABLE IF EXISTS #TempRemarks")
cursor.execute("""
    SELECT EntityGUID, CAST(SUBSTRING(Remark, 1, 4000) AS NVARCHAR(4000)) AS Remark
    INTO #TempRemarks
    FROM EntityRemark
    WHERE Remark IS NOT NULL
""")
conn.commit()

print("Sorting and indexing remarks...")
cursor.execute("CREATE CLUSTERED INDEX IX_TempRemarks_EntityGUID ON #TempRemarks(EntityGUID)")
conn.commit()

print("Merging aggregated remarks...")
cursor.execute("""
    INSERT INTO EntityRemark_New (EntityGUID, Remark)
    SELECT 
        EntityGUID,
        SUBSTRING(STRING_AGG(CAST(Remark AS VARCHAR(MAX)), '; '), 1, 4000)
    FROM #TempRemarks
    GROUP BY EntityGUID
""")
conn.commit()

cursor.execute("DROP TABLE IF EXISTS #TempRemarks")
conn.commit()

print(f"Remarks merge completed. Time taken: {time.time() - start_time:.2f} seconds")

conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60

print(f"Process completed. Total time: {total_time:.2f} minutes.")

