import json
import os
import pyodbc

# Load configuration from VM path
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]

trusted = "yes" if db["trusted_connection"] else "no"
conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("\n==========================================")
print("1. Checking available Databases on Server:")
print("==========================================")
try:
    cursor.execute("SELECT name FROM sys.databases ORDER BY name")
    for row in cursor.fetchall():
        print("  -", row[0])
except Exception as e:
    print("Error listing databases:", e)

print("\n==========================================")
print("2. Checking tables in LexisNexis_Data database:")
print("==========================================")
try:
    # Query tables directly in LexisNexis_Data
    cursor.execute("SELECT TABLE_NAME FROM LexisNexis_Data.INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
    tables = [row[0] for row in cursor.fetchall()]
    for t in tables:
        print("  -", t)
        
    print("\nSearching for 'Country' matching tables:")
    for t in tables:
        if "country" in t.lower() or "iso" in t.lower():
            print("  * Match found:", t)
except Exception as e:
    print("Error checking LexisNexis_Data tables:", e)

conn.close()

