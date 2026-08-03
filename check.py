import json
import os
import pyodbc

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]

trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("\n==========================================")
print("Checking Active Sessions and Blocking on SQL Server:")
print("==========================================")

query = """
SELECT 
    r.session_id,
    r.status,
    r.blocking_session_id,
    r.wait_type,
    r.wait_time,
    r.percent_complete,
    SUBSTRING(st.text, (r.statement_start_offset/2)+1, 
        ((CASE r.statement_end_offset 
          WHEN -1 THEN DATALENGTH(st.text) 
          ELSE r.statement_end_offset 
         END - r.statement_start_offset)/2) + 1) AS statement_text
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) AS st
WHERE r.session_id != @@SPID
"""

try:
    cursor.execute(query)
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(f"Session ID: {r[0]}")
            print(f"  Status: {r[1]}")
            print(f"  Blocking Session: {r[2]} (0 means not blocked)")
            print(f"  Wait Type: {r[3]} | Wait Time: {r[4]} ms")
            print(f"  Percent Complete: {r[5]}%")
            print(f"  Executing Statement:\n{r[6]}\n")
    else:
        print("No active executing requests found (script might have completed or is waiting for input).")
except Exception as e:
    print("Error querying active requests:", e)

conn.close()
