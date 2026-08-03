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
print("Checking for table 'Country' in staging database:")
print("==========================================")
try:
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Country'")
    row = cursor.fetchone()
    if row:
        print(f"  Success! Table '{row[0]}' exists in LexisNexis_Staging!")
        
        # Test reading from it
        cursor.execute("SELECT TOP 5 tISO, tCountry FROM Country")
        print("  Read Test Success! First 5 rows:")
        for r in cursor.fetchall():
            print(f"    - {r[0]}: {r[1]}")
    else:
        print("  Table 'Country' does NOT exist in LexisNexis_Staging database!")
        print("  Let's print all tables starting with C or similar:")
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'C%' ORDER BY TABLE_NAME")
        for r in cursor.fetchall():
            print("    -", r[0])
except Exception as e:
    print("Error checking local Country table:", e)

conn.close()


