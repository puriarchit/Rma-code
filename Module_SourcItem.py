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

print("Starting Optimized Module 2: Merging duplicate web source links...\n")
global_start = time.time()

print("Step 1: Recreating clean target table...")
step_start = time.time()
cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL)")
conn.commit()
print(f"✅ Target table reset! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 2: Loading unique records (no duplicates) directly to target...")
step_start = time.time()
cursor.execute("""
    INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
    SELECT EntityGUID, MIN(SourceURI)
    FROM EntitySourceItem 
    GROUP BY EntityGUID
    HAVING COUNT(*) = 1
""")
conn.commit()
uniq_count = cursor.rowcount
print(f"✅ Loaded {uniq_count} unique records directly! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 3: Fetching duplicate keys...")
step_start = time.time()
cursor.execute("""
    SELECT EntityGUID 
    FROM EntitySourceItem 
    GROUP BY EntityGUID 
    HAVING COUNT(*) > 1
""")
duplicate_guids = [row[0] for row in cursor.fetchall()]
print(f"✅ Found {len(duplicate_guids)} duplicate profiles to merge! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 4: Merging duplicate links in memory-safe batches...")
batch_size = 50000
processed_count = 0
cursor.fast_executemany = True

for i in range(0, len(duplicate_guids), batch_size):
    batch = duplicate_guids[i:i + batch_size]
    batch_start = time.time()
    
    cursor.execute("CREATE TABLE #BatchGUIDs (EntityGUID NVARCHAR(50))")
    cursor.executemany("INSERT INTO #BatchGUIDs (EntityGUID) VALUES (?)", [(g,) for g in batch])
    conn.commit()
    
    cursor.execute("""
        SELECT d.EntityGUID, d.SourceURI 
        FROM EntitySourceItem d
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
    
    cursor.execute("DROP TABLE #BatchGUIDs")
    conn.commit()
    
    processed_count += len(batch)
    print(f"✅ Merged {processed_count}/{len(duplicate_guids)} duplicate groups... (Batch time: {time.time() - batch_start:.2f} seconds)")

global_end = time.time()
total_time = (global_end - global_start) / 60
final_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New").fetchone()[0]

print(f"\n==========================================")
print(f"🎉 Optimized Module 2 completed successfully!")
print(f"Total merged records in target: {final_count}")
print(f"Total time taken: {total_time:.2f} minutes")
print(f"==========================================")


