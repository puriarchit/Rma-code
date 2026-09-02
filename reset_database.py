# -*- coding: utf-8 -*-


import json
import os
import pyodbc
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s", datefmt="%H:%M:%S")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    config = load_config()
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
    
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    logging.info("=========================================================")
    logging.info("   DATABASE RESET UTILITY                                ")
    logging.info("   Target Database: %s", db["name"])
    logging.info("=========================================================")

 
    logging.info("Dropping search and filter reporting views...")
    cursor.execute("DROP VIEW IF EXISTS dbo.NegativeList_Master;")
    cursor.execute("DROP VIEW IF EXISTS dbo.NegativeListFilter;")

    
    logging.info("Dropping production tables...")
    cursor.execute("DROP TABLE IF EXISTS dbo.NegativeList;")
    cursor.execute("DROP TABLE IF EXISTS dbo.NegativeList_Updated;")

   
    logging.info("Dropping intermediate staging tables...")
    intermediate_tables = [
        "NegativeList_New1", "NegativeList_New1_Temp",
        "EntityAddress_New", "EntityDOB_New", "EntityIdentification_New",
        "EntityIdentification_National_New", "Entity_Citizenship_New",
        "EntityRemark_New", "EntitySourceItem_New"
    ]
    for tbl in intermediate_tables:
        cursor.execute(f"DROP TABLE IF EXISTS dbo.[{tbl}];")

    logging.info("Dropping raw staging tables...")
    raw_tables = [
        "AssociatedEntity", "ConsolidatedSanction", "Entity", "EntityAddress",
        "EntityAdverseMedia", "EntityAdverseMediaSubCategory", "EntityAlias",
        "EntityCountryAssociation", "EntityDeletes", "EntityDOB", "EntityEnforcement",
        "EntityEnforcementSubCategory", "EntityIdentification", "EntityRemark",
        "EntitySanction", "EntitySourceItem"
    ]
    for tbl in raw_tables:
        cursor.execute(f"DROP TABLE IF EXISTS dbo.[{tbl}];")

   
    logging.info("Resetting version sequence...")
    cursor.execute("DROP SEQUENCE IF EXISTS dbo.NegativeListVersionSeq;")

    logging.info("=========================================================")
    logging.info("   DATABASE RESET COMPLETED (100%% Clean State)           ")
    logging.info("=========================================================")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
