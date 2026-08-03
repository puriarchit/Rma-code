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

# Query all base tables in current staging database
cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
tables = [row[0] for row in cursor.fetchall()]

print("\n==========================================")
print("Available tables in database:")
print("==========================================")
for t in tables:
    print("  -", t)

print("\n==========================================")
print("Searching for tables related to country:")
print("==========================================")
for t in tables:
    if "country" in t.lower() or "nation" in t.lower() or "iso" in t.lower():
        print("  * Match found:", t)
print("==========================================\n")
        
conn.close()


