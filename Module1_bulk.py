import json
import os
import pyodbc
import time

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)

db = config["database"]
paths = config["paths"]

trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
conn = pyodbc.connect(conn_str)
conn.autocommit = True
cursor = conn.cursor()

try:
    cursor.execute("ALTER DATABASE LexisNexis_Staging SET RECOVERY SIMPLE")
    cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging, FILEGROWTH = 512MB)")
    cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging_log, FILEGROWTH = 512MB, MAXSIZE = UNLIMITED)")
    cursor.execute("USE LexisNexis_Staging")
    cursor.execute("CHECKPOINT")
    cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging_log, 10)")
    print("database optimized and log file shrunk.")
except Exception as e:
    print("db maintenance alert:", e)

files_list = [
    ("AssociatedEntity.txt", "AssociatedEntity"),
    ("ConsolidatedSanction.txt", "ConsolidatedSanction"),
    ("Entity.txt", "Entity"),
    ("EntityAddress.txt", "EntityAddress"),
    ("EntityAdverseMedia.txt", "EntityAdverseMedia"),
    ("EntityAdverseMediaSubCategory.txt", "EntityAdverseMediaSubCategory"),
    ("EntityAlias.txt", "EntityAlias"),
    ("EntityCountryAssociation.txt", "EntityCountryAssociation"),
    ("EntityDeletes.txt", "EntityDeletes"),
    ("EntityDOB.txt", "EntityDOB"),
    ("EntityEnforcement.txt", "EntityEnforcement"),
    ("EntityEnforcementSubCategory.txt", "EntityEnforcementSubCategory"),
    ("EntityIdentification.txt", "EntityIdentification"),
    ("EntityRemark.txt", "EntityRemark"),
    ("EntitySanction.txt", "EntitySanction"),
    ("EntitySourceItem.txt", "EntitySourceItem")
]

print("starting bulk load...")
global_start = time.time()

for filename, tablename in files_list:
    filepath = os.path.join(paths["unzipped_folder"], filename)
    
    if os.path.exists(filepath):
        print(f"ingesting {filename}...")
        file_start = time.time()
        
        try:
            cursor.execute(f"TRUNCATE TABLE {tablename}")
            
            bulk_query = f"""
                BULK INSERT {tablename}
                FROM '{filepath}'
                WITH (
                    FIELDTERMINATOR = '|',
                    ROWTERMINATOR = '0x0a',
                    FIRSTROW = 2,
                    CODEPAGE = '65001',
                    TABLOCK,
                    BATCHSIZE = 100000
                );
            """
            cursor.execute(bulk_query)
            
            cursor.execute(f"SELECT COUNT(*) FROM {tablename}")
            row_count = cursor.fetchone()[0]
            
            file_end = time.time()
            time_taken = file_end - file_start
            print(f"loaded {tablename} ({row_count} rows) in {time_taken:.2f} seconds.\n")
            
        except Exception as ex:
            print(f"failed to load {filename}: {ex}")
            raise ex
    else:
        print(f"skipping {filename}, file not found\n")

cursor.close()
conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60
print(f"bulk load completed in {total_time:.2f} minutes.")
