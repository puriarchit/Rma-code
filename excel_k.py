# -*- coding: utf-8 -*-
import json
import os
import pandas as pd
import pyodbc
import openpyxl

def load_config() -> dict:
    config_path = r"D:\LexisNexis\config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("Connecting to databases...")
    config = load_config()
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    
    conn_data = pyodbc.connect(f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Data;Trusted_Connection={trusted};")
    cursor_data = conn_data.cursor()
    
    conn_staging = pyodbc.connect(f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Staging;Trusted_Connection={trusted};")
    cursor_staging = conn_staging.cursor()

    # Step 1: Fetch ReferenceIDs
    cursor_data.execute("SELECT TOP 10 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 GROUP BY ReferenceID ORDER BY ReferenceID")
    first_ids = [row[0] for row in cursor_data.fetchall()]
    
    cursor_data.execute("SELECT ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 GROUP BY ReferenceID ORDER BY ReferenceID OFFSET 30000 ROWS FETCH NEXT 10 ROWS ONLY")
    middle_ids = [row[0] for row in cursor_data.fetchall()]
    
    cursor_data.execute("SELECT TOP 10 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 GROUP BY ReferenceID ORDER BY ReferenceID DESC")
    last_ids = sorted([row[0] for row in cursor_data.fetchall()])

    all_columns = [
        "ReferenceID", "EntityType", "Gender", "FirstName", "LastName", "SecondName", "Title",
        "DOB", "ALTDOB1", "ALTDOB2", "ALTDOB3", "AddressLine1", "AddressLine2", "City", "Country",
        "WLType", "OriginalSource", "Remark", "NationalIDInfo", "NationalIDNo",
        "IdOtherInfo1", "IdNo1", "IdOtherInfo2", "IdNo2", "IdOtherInfo3", "IdNo3",
        "IdOtherInfo4", "IdNo4", "IdOtherInfo5", "IdNo5", "EntityGUID", "Nationality", "Citizenship", "POB"
    ]

    def build_raw_rows(sample_ids):
        rows = []
        headers = ["ReferenceID", "Database Type"] + all_columns[1:]
        for ref_id in sample_ids:
            # Query SSIS
            sql_data = f"SELECT {', '.join(all_columns)} FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE ReferenceID = ?"
            cursor_data.execute(sql_data, (ref_id,))
            ssis_rows = cursor_data.fetchall()
            
            # Query Python
            sql_staging = f"SELECT {', '.join(all_columns)} FROM LexisNexis_Staging.dbo.NegativeList_New1 WHERE ReferenceID = ?"
            cursor_staging.execute(sql_staging, (ref_id,))
            python_rows = cursor_staging.fetchall()
            
            max_len = max(len(ssis_rows), len(python_rows))
            for i in range(max_len):
                ssis_row = ssis_rows[i] if i < len(ssis_rows) else None
                python_row = python_rows[i] if i < len(python_rows) else None
                
                s_vals = [str(x) if x is not None else "" for x in ssis_row] if ssis_row else [""] * len(all_columns)
                p_vals = [str(x) if x is not None else "" for x in python_row] if python_row else [""] * len(all_columns)
                
                rows.append([ref_id, "SSIS (Old Raw)"] + s_vals[1:])
                rows.append([ref_id, "Python (Staging Raw)"] + p_vals[1:])
                rows.append([""] * len(headers)) # Spacer row (must match header count)
        
        return pd.DataFrame(rows, columns=headers)

    print("Building raw lists...")
    df_first = build_raw_rows(first_ids)
    df_mid = build_raw_rows(middle_ids)
    df_last = build_comparison_rows = build_raw_rows(last_ids)

    output_path = r"D:\LexisNexis\LexisNexis_Raw_Dump.xlsx"
    print(f"Writing Excel to: {output_path}...")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_first.to_excel(writer, sheet_name="First 10 Rows", index=False)
        df_mid.to_excel(writer, sheet_name="Middle 10 Rows", index=False)
        df_last.to_excel(writer, sheet_name="Last 10 Rows", index=False)

    print("Formatting sheets...")
    wb = openpyxl.load_workbook(output_path)
    for sname in ["First 10 Rows", "Middle 10 Rows", "Last 10 Rows"]:
        ws = wb[sname]
        ws.views.sheetView[0].showGridLines = True
        for row in range(2, ws.max_row + 1):
            db_type = ws.cell(row=row, column=2).value
            if db_type == "SSIS (Old Raw)":
                fill = openpyxl.styles.PatternFill(start_color="F2F2F2", fill_type="solid")
            elif db_type == "Python (Staging Raw)":
                fill = openpyxl.styles.PatternFill(start_color="E2EFDA", fill_type="solid")
            else:
                continue
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                cell.fill = fill
                cell.font = openpyxl.styles.Font(name="Segoe UI", size=10)
    
    wb.save(output_path)
    print("Dump completed successfully!")

    cursor_data.close()
    conn_data.close()
    cursor_staging.close()
    conn_staging.close()

if __name__ == "__main__":
    main()
