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
cursor = conn.cursor()

print("Starting Optimized Module 2: Merging duplicate web source links...\n")
global_start = time.time()

print("Step 1: Recreating target table and dropping old helper tables...")
step_start = time.time()
cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL)")

# Drop old helper tables to free up gigabytes of database space!
cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
conn.commit()
print(f"✅ Target table reset & space cleared! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 1.5: Creating Non-Clustered Index on source table (EntitySourceItem)...")
step_start = time.time()
cursor.execute("""
    IF NOT EXISTS (
        SELECT * FROM sys.indexes 
        WHERE object_id = OBJECT_ID('EntitySourceItem') AND name = 'IX_EntitySourceItem_EntityGUID'
    )
    CREATE NONCLUSTERED INDEX IX_EntitySourceItem_EntityGUID ON EntitySourceItem(EntityGUID)
""")
conn.commit()
print(f"✅ Non-Clustered Index created successfully! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 2: Identifying unique records (no duplicates)...")
step_start = time.time()
cursor.execute("IF OBJECT_ID('tempdb..#UniqGUIDs', 'U') IS NOT NULL DROP TABLE #UniqGUIDs")
cursor.execute("CREATE TABLE #UniqGUIDs (EntityGUID NVARCHAR(50))")
cursor.execute("""
    INSERT INTO #UniqGUIDs (EntityGUID)
    SELECT EntityGUID
    FROM EntitySourceItem WITH (INDEX(IX_EntitySourceItem_EntityGUID))
    GROUP BY EntityGUID
    HAVING COUNT(*) = 1
""")
conn.commit()
uniq_count = cursor.execute("SELECT COUNT(*) FROM #UniqGUIDs").fetchone()[0]
print(f"✅ Identified {uniq_count} unique records! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 2.5: Loading unique records directly to target...")
step_start = time.time()
cursor.execute("""
    INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
    SELECT e.EntityGUID, e.SourceURI
    FROM EntitySourceItem e WITH (INDEX(IX_EntitySourceItem_EntityGUID))
    INNER JOIN #UniqGUIDs u ON e.EntityGUID = u.EntityGUID
""")
conn.commit()
print(f"✅ Unique records loaded directly to target! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 3: Streaming, merging, and loading duplicate records...")
step_start = time.time()

# We select the duplicate records ordered by EntityGUID so they appear sequentially
cursor.execute("""
    SELECT e.EntityGUID, e.SourceURI
    FROM EntitySourceItem e WITH (INDEX(IX_EntitySourceItem_EntityGUID))
    INNER JOIN (
        SELECT EntityGUID 
        FROM EntitySourceItem WITH (INDEX(IX_EntitySourceItem_EntityGUID))
        GROUP BY EntityGUID 
        HAVING COUNT(*) > 1
    ) d ON e.EntityGUID = d.EntityGUID
    ORDER BY e.EntityGUID
""")

current_guid = None
current_uris = []
batch_to_insert = []
batch_size = 50000
processed_groups = 0

insert_cursor = conn.cursor()
insert_cursor.fast_executemany = True

while True:
    rows = cursor.fetchmany(batch_size)
    if not rows:
        break
        
    for guid, uri in rows:
        if guid != current_guid:
            if current_guid is not None:
                unique_uris = list(dict.fromkeys(current_uris))
                merged_links = "; ".join(unique_uris)
                batch_to_insert.append((current_guid, merged_links))
                processed_groups += 1
                
                if len(batch_to_insert) >= batch_size:
                    insert_cursor.executemany("""
                        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
                        VALUES (?, ?)
                    """, batch_to_insert)
                    conn.commit()
                    print(f"✅ Loaded {processed_groups} merged duplicate profiles...")
                    batch_to_insert = []
            
            current_guid = guid
            current_uris = [uri] if uri else [""]
        else:
            if uri:
                current_uris.append(uri)
            else:
                current_uris.append("")

# Insert remaining records
if current_guid is not None:
    unique_uris = list(dict.fromkeys(current_uris))
    merged_links = "; ".join(unique_uris)
    batch_to_insert.append((current_guid, merged_links))
    processed_groups += 1

if batch_to_insert:
    insert_cursor.executemany("""
        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
        VALUES (?, ?)
    """, batch_to_insert)
    conn.commit()

print(f"✅ All {processed_groups} duplicate profiles merged and loaded successfully! (Time taken: {time.time() - step_start:.2f} seconds)\n")

global_end = time.time()
total_time = (global_end - global_start) / 60
final_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New").fetchone()[0]

print(f"\n==========================================")
print(f"🎉 Optimized Module 2 completed successfully!")
print(f"Total merged records in target: {final_count}")
print(f"Total time taken: {total_time:.2f} minutes")
print(f"==========================================")




