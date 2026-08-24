# -*- coding: utf-8 -*-
import json
import os
import sys

# Ensure required libraries are installed
try:
    import pandas as pd
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
except ImportError:
    print("Installing pandas and openpyxl...")
    os.system(f'"{sys.executable}" -m pip install pandas openpyxl')
    import pandas as pd
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

import pyodbc

def load_config() -> dict:
    config_path = r"D:\LexisNexis\config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("Initializing Database Connections...")
    config = load_config()
    db = config["database"]
    
    # Establish connection
    conn_str_data = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Data;Trusted_Connection=yes;"
    conn_str_staging = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Staging;Trusted_Connection=yes;"
    
    try:
        conn_data = pyodbc.connect(conn_str_data, autocommit=True)
        conn_staging = pyodbc.connect(conn_str_staging, autocommit=True)
    except Exception as ex:
        print(f"Error connecting to database: {ex}")
        print("Please run this script on the RDP server where WIN-Q6F1HDK5R4D is accessible.")
        return

    print("Step 1: Fetching Row Counts Summary...")
    # List of tables to count
    tables = [
        "Entity",
        "EntityCountryAssociation",
        "EntityAddress",
        "EntityDOB",
        "EntityIdentification",
        "EntityRemark",
        "EntitySourceItem",
        "EntityEnforcement",
        "EntitySanction",
        "NegativeList_New1"
    ]
    
    summary_data = []
    cursor_data = conn_data.cursor()
    cursor_staging = conn_staging.cursor()
    
    for tbl in tables:
        # Check if table exists in Data
        cursor_data.execute(f"SELECT COUNT(*) FROM sys.tables WHERE name = '{tbl}'")
        data_exists = cursor_data.fetchone()[0] > 0
        data_count = 0
        if data_exists:
            cursor_data.execute(f"SELECT COUNT(*) FROM dbo.[{tbl}]")
            data_count = cursor_data.fetchone()[0]
            
        # Check if table exists in Staging
        cursor_staging.execute(f"SELECT COUNT(*) FROM sys.tables WHERE name = '{tbl}'")
        staging_exists = cursor_staging.fetchone()[0] > 0
        staging_count = 0
        if staging_exists:
            cursor_staging.execute(f"SELECT COUNT(*) FROM dbo.[{tbl}]")
            staging_count = cursor_staging.fetchone()[0]
            
        summary_data.append({
            "TableName": tbl,
            "SSIS (Old)": data_count if data_exists else "N/A",
            "Python (Archit Puri)": staging_count if staging_exists else "N/A",
            "Match?": "YES" if data_count == staging_count else "NO"
        })
    
    df_summary = pd.DataFrame(summary_data)

    print("Step 2: Selecting Sample ReferenceIDs for Detail Comparison...")
    # Fetch 15 reference IDs that exist in both databases (5 PEPs, 5 NULLs, 5 Sanctions)
    cursor_data.execute("""
        SELECT TOP 5 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE WLType = 'PEP' AND ReferenceID IS NOT NULL
    """)
    peps = [row[0] for row in cursor_data.fetchall()]
    
    cursor_data.execute("""
        SELECT TOP 5 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE WLType IS NULL AND ReferenceID IS NOT NULL
    """)
    nulls = [row[0] for row in cursor_data.fetchall()]
    
    cursor_data.execute("""
        SELECT TOP 5 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE WLType IS NOT NULL AND WLType <> 'PEP' AND ReferenceID IS NOT NULL
    """)
    sanctions = [row[0] for row in cursor_data.fetchall()]
    
    sample_ids = peps + nulls + sanctions
    print(f"Sample IDs selected: {sample_ids}")

    if not sample_ids:
        print("No sample ReferenceIDs found in NegativeList_New1!")
        return

    # Define column splits
    all_columns = [
        "EntityGUID", "ReferenceID", "EntityType", "Gender", "FirstName", "LastName", "SecondName", "Title", "DOB", "ALTDOB1", "ALTDOB2", "ALTDOB3",
        "AddressLine1", "AddressLine2", "City", "Country", "POB", "WLType", "OriginalSource", "Remark", "NationalIDInfo", "NationalIDNo", "IdOtherInfo1",
        "IdNo1", "IdOtherInfo2", "IdNo2", "IdOtherInfo3", "IdNo3", "IdOtherInfo4", "IdNo4", "IdOtherInfo5", "IdNo5", "Nationality", "Citizenship"
    ]
    
    first_cols = ["ReferenceID", "EntityGUID", "EntityType", "Gender", "FirstName", "LastName", "SecondName", "Title", "DOB", "ALTDOB1", "ALTDOB2", "ALTDOB3"]
    mid_cols = ["ReferenceID", "AddressLine1", "AddressLine2", "City", "Country", "POB", "WLType", "OriginalSource", "Remark", "NationalIDInfo", "NationalIDNo", "IdOtherInfo1"]
    last_cols = ["ReferenceID", "IdNo1", "IdOtherInfo2", "IdNo2", "IdOtherInfo3", "IdNo3", "IdOtherInfo4", "IdNo4", "IdOtherInfo5", "IdNo5", "Nationality", "Citizenship"]

    def build_comparison_rows(cols):
        rows = []
        for ref_id in sample_ids:
            # Query SSIS
            sql_data = f"SELECT {', '.join(cols)} FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE ReferenceID = ?"
            cursor_data.execute(sql_data, (ref_id,))
            ssis_row = cursor_data.fetchone()
            
            # Query Python
            sql_staging = f"SELECT {', '.join(cols)} FROM LexisNexis_Staging.dbo.NegativeList_New1 WHERE ReferenceID = ?"
            cursor_staging.execute(sql_staging, (ref_id,))
            python_row = cursor_staging.fetchone()
            
            if ssis_row and python_row:
                s_vals = [str(x) if x is not None else "" for x in ssis_row]
                p_vals = [str(x) if x is not None else "" for x in python_row]
                
                # Retrieve WLCharMap
                cursor_data.execute("SELECT Symbol, MapChar FROM dbo.WLCharMap")
                char_map = cursor_data.fetchall()
                
                def apply_wl_map(text):
                    res = text
                    for sym, mc in char_map:
                        res = res.replace(sym, mc)
                    return res

                match_vals = []
                for col_name, sv, pv in zip(cols, s_vals, p_vals):
                    # Clean encoding noise for compare
                    sv_clean = sv.replace("Ã§", "ç").replace("Ãº", "ú").replace("Ã±", "ñ").replace("â€“", "–").replace("Ã³", "ó").replace("Ã©", "é")
                    
                    # Apply translation to names if comparing FirstName, LastName, SecondName
                    if col_name in ["FirstName", "LastName", "SecondName"]:
                        sv_clean = apply_wl_map(sv_clean)
                        pv_clean = apply_wl_map(pv)
                    else:
                        pv_clean = pv
                        
                    if sv_clean.lower().strip() == pv_clean.lower().strip():
                        match_vals.append("MATCH")
                    else:
                        match_vals.append("MISMATCH")
                
                rows.append([ref_id, "SSIS (Old)"] + s_vals[1:])
                rows.append([ref_id, "Python (Archit Puri)"] + p_vals[1:])
                rows.append([ref_id, "Match Status"] + match_vals[1:])
                # Empty spacer row
                rows.append([""] * (len(cols) + 1))
        
        headers = ["ReferenceID", "Database Type"] + cols[1:]
        return pd.DataFrame(rows, columns=headers)

    print("Step 3: Building Side-by-Side Splits...")
    df_first = build_comparison_rows(first_cols)
    df_mid = build_comparison_rows(mid_cols)
    df_last = build_comparison_rows(last_cols)

    output_path = r"D:\LexisNexis\LexisNexis_Comparison_Report.xlsx"
    print(f"Step 4: Writing to Excel file: {output_path}...")
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Table Summary", index=False)
        df_first.to_excel(writer, sheet_name="First 10 Columns", index=False)
        df_mid.to_excel(writer, sheet_name="Middle 10 Columns", index=False)
        df_last.to_excel(writer, sheet_name="Last 10 Columns", index=False)

    print("Step 5: Formatting Excel Sheets...")
    wb = openpyxl.load_workbook(output_path)
    
    # Styles
    font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    font_normal = Font(name="Segoe UI", size=10)
    font_bold = Font(name="Segoe UI", size=10, bold=True)
    fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid") # Dark Blue
    fill_ssis = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid") # Light Gray
    fill_python = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Light Green
    fill_match = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid") # Light Blue
    fill_mismatch = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Light Orange/Red
    
    border_thin = Border(
        left=Side(style='thin', color='BFBFBF'),
        right=Side(style='thin', color='BFBFBF'),
        top=Side(style='thin', color='BFBFBF'),
        bottom=Side(style='thin', color='BFBFBF')
    )

    # Format Table Summary Sheet
    ws_summary = wb["Table Summary"]
    ws_summary.views.sheetView[0].showGridLines = True
    for col_idx in range(1, 5):
        cell = ws_summary.cell(row=1, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center")
    
    for row in range(2, ws_summary.max_row + 1):
        for col in range(1, 5):
            cell = ws_summary.cell(row=row, column=col)
            cell.font = font_normal
            cell.border = border_thin
            if col == 4: # Match Column
                if cell.value == "YES":
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="385723")
                    cell.fill = PatternFill(start_color="E2EFDA", fill_type="solid")
                else:
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="C00000")
                    cell.fill = PatternFill(start_color="FCE4D6", fill_type="solid")
    
    # Format Comparison Sheets
    comp_sheets = ["First 10 Columns", "Middle 10 Columns", "Last 10 Columns"]
    for sname in comp_sheets:
        ws = wb[sname]
        ws.views.sheetView[0].showGridLines = True
        
        # Header formatting
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center")
            
        # Data formatting
        for row in range(2, ws.max_row + 1):
            db_type = ws.cell(row=row, column=2).value
            if not db_type:
                continue # Spacer row
            
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                cell.font = font_normal
                cell.border = border_thin
                
                if db_type == "SSIS (Old)":
                    cell.fill = fill_ssis
                elif db_type == "Python (Archit Puri)":
                    cell.fill = fill_python
                elif db_type == "Match Status":
                    cell.font = font_bold
                    if col >= 3: # Comparison columns
                        if cell.value == "MATCH":
                            cell.value = "MATCH"
                            cell.font = Font(name="Segoe UI", size=10, bold=True, color="385723")
                            cell.fill = PatternFill(start_color="E2EFDA", fill_type="solid")
                        else:
                            cell.value = "MISMATCH"
                            cell.font = Font(name="Segoe UI", size=10, bold=True, color="C00000")
                            cell.fill = PatternFill(start_color="FCE4D6", fill_type="solid")
                    else:
                        cell.fill = fill_match

    # Auto fit column widths
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            for cell in col:
                val = str(cell.value or '')
                if len(val) > max_len:
                    max_len = len(val)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    wb.save(output_path)
    print(f"Success! Report generated successfully at: {output_path}")

if __name__ == "__main__":
    main()
