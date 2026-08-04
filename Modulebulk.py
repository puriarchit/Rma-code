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
    # 1. Set Recovery Model to SIMPLE
    cursor.execute("ALTER DATABASE LexisNexis_Staging SET RECOVERY SIMPLE")
    # 2. Unlock Data File Growth limits
    cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging, FILEGROWTH = 512MB)")
    # 3. UNLOCK LOG FILE Auto-Growth and MAXSIZE constraints permanently (replaces manual SSMS queries!)
    cursor.execute("ALTER DATABASE LexisNexis_Staging MODIFY FILE (NAME = LexisNexis_Staging_log, FILEGROWTH = 512MB, MAXSIZE = UNLIMITED)")
    cursor.execute("USE LexisNexis_Staging")
    cursor.execute("CHECKPOINT")
    # 4. Shrink log file to clean residual database spaces
    cursor.execute("DBCC SHRINKFILE (LexisNexis_Staging_log, 10)")
    print("Database optimized, set to SIMPLE, log growth unlocked, and shrunk successfully!")
except Exception as e:
    print("Database maintenance warning:", e)

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

print("Starting native SQL Server BULK INSERT Loader (Config Driven)...\n")
global_start = time.time()

for filename, tablename in files_list:
    filepath = os.path.join(paths["unzipped_folder"], filename)
    
    if os.path.exists(filepath):
        print(f"Bulk Ingesting: {filename} ...")
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
            print(f"✅ {tablename} loaded! ({row_count} rows) - Time taken: {time_taken:.2f} seconds\n")
            
        except Exception as ex:
            # Re-raise the exception to stop pipeline in orchestrator if any bulk insert fails!
            print(f"❌ Error loading {filename}: {ex}\n")
            raise ex
    else:
        print(f"⚠️ File not found, skipping: {filename}\n")

cursor.close()
conn.close()

global_end = time.time()
total_time = (global_end - global_start) / 60
print(f"All files loaded successfully! Total time taken: {total_time:.2f} minutes")
