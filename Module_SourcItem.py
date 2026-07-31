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

# Open a separate independent connection for inserts to prevent "Connection is busy" conflicts
conn_insert = pyodbc.connect(conn_str)
insert_cursor = conn_insert.cursor()
insert_cursor.fast_executemany = True

print("Starting Optimized Module 2: Merging duplicate web source links...\n")
global_start = time.time()

print("Step 1: Recreating target table and dropping old helper tables...")
step_start = time.time()
cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New](<[EntityGUID] [nvarchar](50>) NULL, [SourceURI] [nvarchar](max) NULL)")

# Drop old helper tables to free up gigabytes of database space!
cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
conn.commit()
print(f"✅ Target table reset & space cleared! (Time taken: {time.time() - step_start:.2f} seconds)\n")

print("Step 2: Streaming, merging, and loading all records in a single pass...")
step_start = time.time()

# We perform a single sequential scan and sort on the server.
# Python processes and merges both uniques and duplicates on-the-fly.
cursor.execute("""
    SELECT EntityGUID, SourceURI 
    FROM EntitySourceItem WITH (INDEX(0))
    ORDER BY EntityGUID
""")

current_guid = None
current_uris = []
batch_to_insert = []
batch_size = 50000
processed_count = 0

while True:
    rows = cursor.fetchmany(batch_size)
    if not rows:
        break
        
    for guid, uri in rows:
        if guid != current_guid:
            if current_guid is not None:
                # Merge the accumulated URIs
                unique_uris = list(dict.fromkeys(current_uris))
                merged_links = "; ".join(unique_uris)
                batch_to_insert.append((current_guid, merged_links))
                processed_count += 1
                
                if len(batch_to_insert) >= batch_size:
                    # Set inputsizes to SQL_WVARCHAR with length 0 to prevent driver precision/length errors
                    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 0, 0)])
                    insert_cursor.executemany("""
                        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
                        VALUES (?, ?)
                    """, batch_to_insert)
                    conn_insert.commit()
                    print(f"✅ Loaded {processed_count} unique merged profiles...")
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
    processed_count += 1

if batch_to_insert:
    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 0, 0)])
    insert_cursor.executemany("""
        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
        VALUES (?, ?)
    """, batch_to_insert)
    conn_insert.commit()

# Close separate connection
conn_insert.close()

print(f"✅ All {processed_count} profiles merged and loaded successfully! (Time taken: {time.time() - step_start:.2f} seconds)\n")

global_end = time.time()
total_time = (global_end - global_start) / 60
final_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New").fetchone()[0]

print(f"\n==========================================")
print(f"🎉 Optimized Module 2 completed successfully!")
print(f"Total merged records in target: {final_count}")
print(f"Total time taken: {total_time:.2f} minutes")
print(f"==========================================")
conn.close()







