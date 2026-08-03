import json
import os
import pyodbc

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
db = config["database"]

trusted = "yes" if db["trusted_connection"] else "no"

# Attempt 1: Connect directly to LexisNexis_Staging and query LexisNexis_Data with dbo
print("Testing direct select from LexisNexis_Staging connection:")
try:
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 5 * FROM LexisNexis_Data.dbo.Country")
    print("  Success! First country:", cursor.fetchone())
    conn.close()
except Exception as e:
    print("  Direct select failed:", e)

# Attempt 2: Connect directly to LexisNexis_Data database catalog
print("\nTesting connection directly to LexisNexis_Data catalog:")
try:
    conn_str_data = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Data;Trusted_Connection={trusted};"
    conn = pyodbc.connect(conn_str_data)
    cursor = conn.cursor()
    print("  Connection to LexisNexis_Data succeeded!")
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    tables = [row[0] for row in cursor.fetchall()]
    print("  Tables in LexisNexis_Data:", tables)
    conn.close()
except Exception as e:
    print("  Connection directly to LexisNexis_Data failed:", e)
