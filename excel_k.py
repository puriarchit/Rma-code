# -*- coding: utf-8 -*-
import json
import os
import sys

try:
    import pandas as pd
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
except ImportError:
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
    trusted = "yes" if db["trusted_connection"] else "no"
    
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Data;Trusted_Connection={trusted};"
    conn_str_staging = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Staging;Trusted_Connection={trusted};"
    
    try:
        conn_data = pyodbc.connect(conn_str, autocommit=True)
        conn_staging = pyodbc.connect(conn_str_staging, autocommit=True)
    except Exception as ex:
        print(f"Error connecting to database: {ex}")
        return

    cursor_data = conn_data.cursor()
    cursor_staging = conn_staging.cursor()

    tables = [
        "Entity", "EntityCountryAssociation", "EntityAddress", "EntityDOB",
        "EntityIdentification", "EntityRemark", "EntitySourceItem",
        "EntityEnforcement", "EntitySanction", "NegativeList_New1"
    ]
    summary_data = []
    for tbl in tables:
        cursor_data.execute(f"SELECT COUNT(*) FROM sys.tables WHERE name = '{tbl}'")
        data_exists = cursor_data.fetchone()[0] > 0
        data_count = 0
        if data_exists:
            cursor_data.execute(f"SELECT COUNT(*) FROM dbo.[{tbl}]")
            data_count = cursor_data.fetchone()[0]
            
        cursor_staging.execute(f"SELECT COUNT(*) FROM sys.tables WHERE name = '{tbl}'")
        staging_exists = cursor_staging.fetchone()[0] > 0
        staging_count = 0
        if staging_exists:
            cursor_staging.execute(f"SELECT COUNT(*) FROM dbo.[{tbl}]")
            staging_count = cursor_staging.fetchone()[0]
            
        summary_data.append({
            "TableName": tbl,
            "SSIS (Old)": data_count if data_exists else "N/A",
            "Python (Staging)": staging_count if staging_exists else "N/A",
            "Match?": "YES" if data_count == staging_count else "NO"
        })
    df_summary = pd.DataFrame(summary_data)

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

    def clean_val(v):
        if v is None or v == "None":
            return ""
        val = str(v).strip()
        val = val.replace("\r\n", "Â¶").replace("\r", "Â¶").replace("\n", "Â¶").replace("", "Â¶")
        return val

    mismatches_summary = []

    def build_comparison_rows(sample_ids, sheet_name):
        def row_sort_key(row):
            wl = clean_val(row[15])
            src = "".join(sorted([x.strip() for x in clean_val(row[16]).split(";") if x.strip()]))
            rem = "".join(clean_val(row[17]).split())
            return (wl.lower(), src.lower(), rem)

        rows = []
        for ref_id in sample_ids:
            sql_data = f"SELECT {', '.join(all_columns)} FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE ReferenceID = ?"
            cursor_data.execute(sql_data, (ref_id,))
            ssis_rows = cursor_data.fetchall()
            
            sql_staging = f"SELECT {', '.join(all_columns)} FROM LexisNexis_Staging.dbo.NegativeList_New1 WHERE ReferenceID = ?"
            cursor_staging.execute(sql_staging, (ref_id,))
            python_rows = cursor_staging.fetchall()
            
            ssis_rows = sorted(ssis_rows, key=row_sort_key)
            python_rows = sorted(python_rows, key=row_sort_key)
            
            max_len = max(len(ssis_rows), len(python_rows))
            for i in range(max_len):
                ssis_row = ssis_rows[i] if i < len(ssis_rows) else None
                python_row = python_rows[i] if i < len(python_rows) else None
                
                s_vals = [str(x) if x is not None else "" for x in ssis_row] if ssis_row else [""] * len(all_columns)
                p_vals = [str(x) if x is not None else "" for x in python_row] if python_row else [""] * len(all_columns)
                
                match_vals = []
                mismatched_cols = []
                for col_idx, col_name in enumerate(all_columns):
                    sv = clean_val(s_vals[col_idx])
                    pv = clean_val(p_vals[col_idx])
                    
                    if col_name == "OriginalSource":
                        # Sort URLs
                        s_urls = sorted([x.strip() for x in sv.split(";") if x.strip()])
                        p_urls = sorted([x.strip() for x in pv.split(";") if x.strip()])
                        if s_urls == p_urls:
                            sv = pv # Treat as match
                    
                    if sv == pv:
                        match_vals.append("MATCH")
                    else:
                        match_vals.append("MISMATCH")
                        mismatched_cols.append(col_name)
                
                if mismatched_cols:
                    mismatches_summary.append({
                        "Sheet": sheet_name,
                        "ReferenceID": ref_id,
                        "RowIndex": i + 1,
                        "Mismatches": mismatched_cols
                    })
                
                rows.append([ref_id, "SSIS (Old)"] + s_vals[1:])
                rows.append([ref_id, "Python (Staging)"] + p_vals[1:])
                rows.append([ref_id, "Match Status"] + match_vals[1:])
                rows.append([""] * (len(all_columns) + 1))
                
        headers = ["ReferenceID", "Database Type"] + all_columns[1:]
        return pd.DataFrame(rows, columns=headers)

    print("Building Sheet Dataframes...")
    df_first = build_comparison_rows(first_ids, "First 10 Rows")
    df_mid = build_comparison_rows(middle_ids, "Middle 10 Rows")
    df_last = build_comparison_rows(last_ids, "Last 10 Rows")

    output_path = r"D:\LexisNexis\LexisNexis_Comparison_Report.xlsx"
    print(f"Writing to Excel file: {output_path}...")
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Table Summary", index=False)
        df_first.to_excel(writer, sheet_name="First 10 Rows", index=False)
        df_mid.to_excel(writer, sheet_name="Middle 10 Rows", index=False)
        df_last.to_excel(writer, sheet_name="Last 10 Rows", index=False)

    print("Formatting sheets...")
    wb = openpyxl.load_workbook(output_path)
    
    font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    font_normal = Font(name="Segoe UI", size=10)
    font_bold = Font(name="Segoe UI", size=10, bold=True)
    fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_ssis = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    fill_python = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    fill_match = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    border_thin = Border(
        left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'),
        top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF')
    )

    ws_summary = wb["Table Summary"]
    ws_summary.views.sheetView[0].showGridLines = True
    for col_idx in range(1, 5):
        cell = ws_summary.cell(row=1, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center")
    for r in range(2, ws_summary.max_row + 1):
        for c in range(1, 5):
            cell = ws_summary.cell(row=r, column=c)
            cell.font = font_normal
            cell.border = border_thin
            if c == 4:
                if cell.value == "YES":
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="385723")
                    cell.fill = PatternFill(start_color="E2EFDA", fill_type="solid")
                else:
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="C00000")
                    cell.fill = PatternFill(start_color="FCE4D6", fill_type="solid")

    for sname in ["First 10 Rows", "Middle 10 Rows", "Last 10 Rows"]:
        ws = wb[sname]
        ws.views.sheetView[0].showGridLines = True
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center")
        for r in range(2, ws.max_row + 1):
            db_type = ws.cell(row=r, column=2).value
            if not db_type:
                continue
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(row=r, column=c)
                cell.font = font_normal
                cell.border = border_thin
                if db_type == "SSIS (Old)":
                    cell.fill = fill_ssis
                elif db_type == "Python (Staging)":
                    cell.fill = fill_python
                elif db_type == "Match Status":
                    cell.font = font_bold
                    if c >= 3:
                        if cell.value == "MATCH":
                            cell.font = Font(name="Segoe UI", size=10, bold=True, color="385723")
                            cell.fill = PatternFill(start_color="E2EFDA", fill_type="solid")
                        else:
                            cell.font = Font(name="Segoe UI", size=10, bold=True, color="C00000")
                            cell.fill = PatternFill(start_color="FCE4D6", fill_type="solid")
                    else:
                        cell.fill = fill_match

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
    print("\nReport successfully generated!")
    print(f"=== Total Mismatches: {len(mismatches_summary)} ===")
    for item in mismatches_summary:
        print(f"Sheet: {item['Sheet']} | ReferenceID: {item['ReferenceID']} | Row Index: {item['RowIndex']} | Mismatches: {item['Mismatches']}")

    cursor_data.close()
    conn_data.close()
    cursor_staging.close()
    conn_staging.close()

if __name__ == "__main__":
    main()
