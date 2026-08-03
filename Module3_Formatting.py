import xml.etree.ElementTree as ET
import os

package_path = r"C:\Users\LENOVO\OneDrive\Desktop\RMA Project 1\Packages_Set2\Packages_Set2\EntityAddress.dtsx"

if os.path.exists(package_path):
    print("Parsing EntityAddress.dtsx connection managers...")
    with open(package_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Let's search for ConnectionString or DB name inside the DTSX XML
    import re
    connections = re.findall(r'ConnectionString="([^"]+)"', content, re.IGNORECASE)
    print("Found Connection Strings:")
    for c in connections:
        print("  ", c)
        
    # Search for any lookup database catalog names
    catalogs = re.findall(r'Initial Catalog=([^;"]+)', content, re.IGNORECASE)
    print("\nFound Initial Catalogs (databases):")
    print(set(catalogs))
else:
    print("EntityAddress.dtsx not found.")

