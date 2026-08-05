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

conn_insert = pyodbc.connect(conn_str)
insert_cursor = conn_insert.cursor()
insert_cursor.fast_executemany = True

print("starting module 2...")
global_start = time.time()

print("recreating target table...")
step_start = time.time()
cursor.execute("IF OBJECT_ID('EntitySourceItem_New', 'U') IS NOT NULL DROP TABLE EntitySourceItem_New")
cursor.execute("CREATE TABLE [dbo].[EntitySourceItem_New]([EntityGUID] [nvarchar](50) NULL, [SourceURI] [nvarchar](max) NULL)")

cursor.execute("IF OBJECT_ID('EntitySourceItem_Dup', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Dup")
cursor.execute("IF OBJECT_ID('EntitySourceItem_Uniqrecord', 'U') IS NOT NULL DROP TABLE EntitySourceItem_Uniqrecord")
conn.commit()
print(f"target table reset, took {time.time() - step_start:.2f} seconds.")

print("merging and loading records...")
step_start = time.time()

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
                unique_uris = list(dict.fromkeys(current_uris))
                merged_links = "; ".join(unique_uris)
                batch_to_insert.append((current_guid, merged_links))
                processed_count += 1
                
                if len(batch_to_insert) >= batch_size:
                    insert_cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 50, 0), (pyodbc.SQL_WVARCHAR, 0, 0)])
                    insert_cursor.executemany("""
                        INSERT INTO EntitySourceItem_New (EntityGUID, SourceURI)
                        VALUES (?, ?)
                    """, batch_to_insert)
                    conn_insert.commit()
                    print(f"loaded {processed_count} profiles...")
                    batch_to_insert = []
            
            current_guid = guid
            current_uris = [uri] if uri else [""]
        else:
            if uri:
                current_uris.append(uri)
            else:
                current_uris.append("")

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

conn_insert.close()

print(f"all profiles merged and loaded in {time.time() - step_start:.2f} seconds.")

global_end = time.time()
total_time = (global_end - global_start) / 60
final_count = cursor.execute("SELECT COUNT(*) FROM EntitySourceItem_New").fetchone()[0]

print(f"module 2 completed in {total_time:.2f} minutes.")
print(f"total merged records: {final_count}")
conn.close()








