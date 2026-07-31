import json
import os
import pyodbc
import time
from collections import defaultdict

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]
paths = config["paths"]

trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("Starting Module 2: Merging duplicate web source links...\n")
global_start = time.time()

print("Step 1: Recreating staging helper and target tables...")
step_start = time.time()
cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_Dup]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](4000) NULL)")

cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_Uniqrecord]([EntityGUID] [nvarchar](50) NULL)")

cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL)")
conn.commit()
print(f"✅ Staging tables reset! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 2: Identifying unique records (no duplicates)...")
step_start = time.time()
cursor.execute("""
    INSERT INTO EntitySourceItem_Uniqrecord (EntityGUID)
    SELECT EntityGUID 
    FROM EntitySourceItem 
    GROUP BY EntityGUID 
    HAVING COUNT(*) = 1
""")
conn.commit()
uniq_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_Uniqrecord").fetchone()[0]
print(f"✅ Found {uniq_count} unique records! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 3: Creating duplicates workspace backup...")
step_start = time.time()
cursor.execute("""
    INSERT INTO EntitySourceItem_Dup (EntityGUID, SourceURI)
    SELECT EntityGUID, SourceURI 
    FROM EntitySourceItem
""")
conn.commit()
print(f"✅ Backup created! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 4: Isolating duplicate records in workspace...")
step_start = time.time()
cursor.execute("""
    DELETE FROM EntitySourceItem_Dup 
    WHERE EntityGUID IN (SELECT EntityGUID FROM EntitySourceItem_Uniqrecord)
""")
conn.commit()
dup_rows = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_Dup").fetchone()[0]
print(f"✅ Isolated {dup_rows} raw duplicate rows! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 5: Loading unique records directly to target table...")
step_start = time.time()
cursor.execute("""
    INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
    SELECT EntityGUID, SourceURI 
    FROM EntitySourceItem 
    WHERE EntityGUID IN (SELECT EntityGUID FROM EntitySourceItem_Uniqrecord)
""")
conn.commit()
print(f"✅ Unique records loaded to target table! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 6: Merging duplicate web links in batches...")
batch_size = 100000
processed_count = 0
cursor.fast_executemany = True

while True:
    cursor.execute(f"SELECT TOP {batch_size} EntityGUID FROM EntitySourceItem_Dup GROUP BY EntityGUID")
    batch_guids = [row[0] for row in cursor.fetchall()]
    
    if not batch_guids:
        break
        
    print(f"Processing batch of {len(batch_guids)} duplicate GUIDs...")
    batch_start = time.time()
    
    cursor.execute("CREATE TABLE #BatchGUIDs (EntityGUID NVARCHAR(50))")
    cursor.executemany("INSERT INTO #BatchGUIDs (EntityGUID) VALUES (?)", [(g,) for g in batch_guids])
    conn.commit()
    
    cursor.execute("""
        SELECT d.EntityGUID, d.SourceURI 
        FROM EntitySourceItem_Dup d
        INNER JOIN #BatchGUIDs b ON d.EntityGUID = b.EntityGUID
    """)
    rows = cursor.fetchall()
    
    groups = defaultdict(list)
    for guid, uri in rows:
        if uri:
            groups[guid].append(uri)
        else:
            groups[guid].append("")
            
    merged_data = []
    for guid, uris in groups.items():
        unique_uris = list(dict.fromkeys(uris))
        merged_links = "; ".join(unique_uris)
        merged_data.append((guid, merged_links))
        
    cursor.executemany("""
        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
        VALUES (?, ?)
    """, merged_data)
    
    cursor.execute("""
        DELETE FROM EntitySourceItem_Dup 
        WHERE EntityGUID IN (SELECT EntityGUID FROM #BatchGUIDs)
    """)
    
    cursor.execute("DROP TABLE #BatchGUIDs")
    conn.commit()
    
    processed_count += len(batch_guids)
    print(f"✅ Merged {processed_count} duplicate groups... (Batch time: {time.time() - batch_start:.2f} seconds)")

global_end = time.time()
total_time = (global_end - global_start) / 60
final_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New").fetchone()[0]

print(f"\n==========================================")
print(f"🎉 Module 2 completed successfully!")
print(f"Total merged records: {final_count}")
print(f"Total time taken: {total_time:.2f} minutes")
print(f"==========================================")

