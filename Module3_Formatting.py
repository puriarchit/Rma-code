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

cursor.execute("SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' ORDER BY name")
databases = [row[0] for row in cursor.fetchall()]

print("\nScanning databases for 'Country' table...")
print("==========================================")

found = False
for db_name in databases:
    if db_name.lower() in ["master", "tempdb", "model", "msdb"]:
        continue
    try:
        query = f"SELECT TABLE_SCHEMA, TABLE_NAME FROM [{db_name}].INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%Country%' OR TABLE_NAME LIKE '%Nation%'"
        cursor.execute(query)
        rows = cursor.fetchall()
        if rows:
            for schema, table in rows:
                print(f"  [FOUND in metadata] Database: {db_name} -> Table: {schema}.{table}")
                found = True
    except:
        pass

    try:
        cursor.execute(f"SELECT TOP 1 * FROM [{db_name}].dbo.Country")
        print(f"  [READ SUCCESS] Database: {db_name} -> Table: dbo.Country exists and is READABLE!")
        found = True
    except:
        pass

if not found:
    print("  No 'Country' table found or accessible in any database.")
print("==========================================\n")
conn.close()
