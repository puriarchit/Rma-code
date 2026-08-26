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
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("Initializing Database Connections...")
    config = load_config()
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    
    conn_str_staging = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Staging;Trusted_Connection={trusted};"
    conn_str_ssis_data = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=LexisNexis_Data;Trusted_Connection={trusted};"
    conn_str_ssis_prod = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE=MoneyWaveRemit;Trusted_Connection={trusted};"
    
    try:
        conn_py = pyodbc.connect(conn_str_staging, autocommit=True)
        conn_ssis_data = pyodbc.connect(conn_str_ssis_data, autocommit=True)
        conn_ssis_prod = pyodbc.connect(conn_str_ssis_prod, autocommit=True)
    except Exception as ex:
        print(f"Error connecting to databases: {ex}")
        return

    cursor_py = conn_py.cursor()
    cursor_ssis_data = conn_ssis_data.cursor()
    cursor_ssis_prod = conn_ssis_prod.cursor()

    # 1. TABLE SUMMARY SHEET
    print("Gathering table row counts...")
    summary_tables = [
        # (Table Name, Py DB, SSIS DB, SSIS Connection)
        ("Entity", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityCountryAssociation", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityAddress", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityDOB", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityIdentification", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityRemark", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntitySourceItem", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityEnforcement", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntitySanction", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("EntityAlias", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("NegativeList_New1", "LexisNexis_Staging", "LexisNexis_Data", cursor_ssis_data),
        ("NegativeList", "LexisNexis_Staging", "MoneyWaveRemit", cursor_ssis_prod),
        ("NegativeListFilter", "LexisNexis_Staging", "MoneyWaveRemit", cursor_ssis_prod),
        ("NegativeList_Master", "LexisNexis_Staging", "MoneyWaveRemit", cursor_ssis_prod)
    ]

    summary_data = []
    for tbl, py_db, ssis_db, ssis_cursor in summary_tables:
        # Get Python Row Count
        cursor_py.execute(f"SELECT COUNT(*) FROM sys.objects WHERE name = '{tbl}' AND (type = 'U' OR type = 'V')")
        py_exists = cursor_py.fetchone()[0] > 0
        py_count = 0
        if py_exists:
            cursor_py.execute(f"SELECT COUNT(*) FROM [{py_db}].dbo.[{tbl}]")
            py_count = cursor_py.fetchone()[0]

        # Get SSIS Row Count
        ssis_cursor.execute(f"SELECT COUNT(*) FROM sys.objects WHERE name = '{tbl}' AND (type = 'U' OR type = 'V')")
        ssis_exists = ssis_cursor.fetchone()[0] > 0
        ssis_count = 0
        if ssis_exists:
            ssis_cursor.execute(f"SELECT COUNT(*) FROM [{ssis_db}].dbo.[{tbl}]")
            ssis_count = ssis_cursor.fetchone()[0]

        summary_data.append({
            "Database Object / Table": tbl,
            "Python (LexisNexis_Staging)": py_count if py_exists else "N/A",
            f"SSIS ({ssis_db})": ssis_count if ssis_exists else "N/A",
            "Match?": "YES" if py_count == ssis_count else "NO"
        })
    df_summary = pd.DataFrame(summary_data)

    # Helper function to clean values
    def clean_val(v):
        if v is None or v == "None":
            return ""
        val = str(v).strip()
        val = val.replace("\r\n", "¶").replace("\r", "¶").replace("\n", "¶")
        return val

    # Helper function to sort rows during comparison
    def row_sort_key(row):
        return tuple(clean_val(x).lower() for x in row)

    # 2. COMPARISON BUILDER
    def build_comparison_sheet(tbl_name, is_view=False, ssis_cursor=cursor_ssis_prod, columns=[], id_col="ID"):
        print(f"Sampling IDs for table: {tbl_name}...")
        
        # Get sample IDs (First, Middle, Last 10)
        cursor_py.execute(f"SELECT TOP 10 {id_col} FROM LexisNexis_Staging.dbo.[{tbl_name}] ORDER BY {id_col}")
        first_ids = [row[0] for row in cursor_py.fetchall()]
        
        cursor_py.execute(f"SELECT COUNT(*) FROM LexisNexis_Staging.dbo.[{tbl_name}]")
        total_rows = cursor_py.fetchone()[0]
        mid_offset = max(0, (total_rows // 2) - 5)
        
        cursor_py.execute(f"SELECT {id_col} FROM LexisNexis_Staging.dbo.[{tbl_name}] ORDER BY {id_col} OFFSET {mid_offset} ROWS FETCH NEXT 10 ROWS ONLY")
        middle_ids = [row[0] for row in cursor_py.fetchall()]
        
        cursor_py.execute(f"SELECT TOP 10 {id_col} FROM LexisNexis_Staging.dbo.[{tbl_name}] ORDER BY {id_col} DESC")
        last_ids = sorted([row[0] for row in cursor_py.fetchall()])

        def fetch_and_compare(ids, label):
            rows = []
            for item_id in ids:
                # Fetch SSIS rows
                sql_ssis = f"SELECT {', '.join(columns)} FROM MoneyWaveRemit.dbo.[{tbl_name}] WHERE {id_col} = ?"
                ssis_cursor.execute(sql_ssis, (item_id,))
                ssis_rows = ssis_cursor.fetchall()

                # Fetch Python rows
                sql_py = f"SELECT {', '.join(columns)} FROM LexisNexis_Staging.dbo.[{tbl_name}] WHERE {id_col} = ?"
                cursor_py.execute(sql_py, (item_id,))
                py_rows = cursor_py.fetchall()

                # Sort for alignment
                ssis_rows = sorted(ssis_rows, key=row_sort_key)
                py_rows = sorted(py_rows, key=row_sort_key)

                max_len = max(len(ssis_rows), len(py_rows))
                for i in range(max_len):
                    s_row = ssis_rows[i] if i < len(ssis_rows) else None
                    p_row = py_rows[i] if i < len(py_rows) else None

                    s_vals = [str(x) if x is not None else "" for x in s_row] if s_row else [""] * len(columns)
                    p_vals = [str(x) if x is not None else "" for x in p_row] if p_row else [""] * len(columns)

                    match_vals = []
                    for col_idx, col_name in enumerate(columns):
                        sv = clean_val(s_vals[col_idx])
                        pv = clean_val(p_vals[col_idx])
                        if sv == pv:
                            match_vals.append("MATCH")
                        else:
                            match_vals.append("MISMATCH")

                    rows.append([item_id, "SSIS (Old)"] + s_vals[1:])
                    rows.append([item_id, "Python (Staging)"] + p_vals[1:])
                    rows.append([item_id, "Match Status"] + match_vals[1:])
                    rows.append([""] * (len(columns) + 1))

            headers = [id_col, "Database Type"] + columns[1:]
            return pd.DataFrame(rows, columns=headers)

        return fetch_and_compare(first_ids, "First"), fetch_and_compare(middle_ids, "Middle"), fetch_and_compare(last_ids, "Last")

    # Define columns for the 3 verified tables
    neg_columns = [
        "ID", "ReferenceID", "WLType", "FileName", "VersionID", "EntityType", "Gender", 
        "LastName", "FirstName", "SecondName", "POB", "DOB", "Nationality", "Citizenship", 
        "Alias", "Title", "AddressLine1", "AddressLine2", "City", "IdNo1", "IdOtherInfo1", 
        "IdNo2", "IdOtherInfo2", "IdNo3", "IdOtherInfo3", "IdNo4", "IdOtherInfo4", "IdNo5", 
        "IdOtherInfo5", "NationalIDNo", "NationalIDInfo", "EntityGUID", "EntityAliasGUID", 
        "Remark", "Country", "CreationDate", "LastUpdatedBy", "LastUpdatedDate"
    ]

    filter_columns = ["ID", "FirstName", "LastName", "Nationality"]

    master_columns = [
        "ID", "ReferenceID", "WLType", "FileName", "VersionID", "EntityType", "Gender", 
        "LastName", "FirstName", "SecondName", "POB", "DOB", "Nationality", "Citizenship", 
        "Alias", "Title", "AddressLine1", "AddressLine2", "City", "IdNo1", "IdOtherInfo1", 
        "IdNo2", "IdOtherInfo2", "IdNo3", "IdOtherInfo3", "IdNo4", "IdOtherInfo4", "IdNo5", 
        "IdOtherInfo5", "NationalIDNo", "NationalIDInfo", "Basis", "Remarks", "Country", 
        "CreationDate", "LastUpdatedBy", "LastUpdatedDate"
    ]

    # Build sheets dataframes
    print("Processing NegativeList data...")
    neg_first, neg_mid, neg_last = build_comparison_sheet("NegativeList", columns=neg_columns)
    
    print("Processing NegativeListFilter data...")
    filt_first, filt_mid, filt_last = build_comparison_sheet("NegativeListFilter", columns=filter_columns)
    
    print("Processing NegativeList_Master data...")
    mast_first, mast_mid, mast_last = build_comparison_sheet("NegativeList_Master", columns=master_columns)

    # 3. WRITE TO EXCEL
    output_path = r"D:\LexisNexis\LexisNexis_Incremental_Comparison_Report.xlsx"
    print(f"Writing all 10 sheets to: {output_path}...")
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Table Summary", index=False)
        neg_first.to_excel(writer, sheet_name="NegList First 10", index=False)
        neg_mid.to_excel(writer, sheet_name="NegList Middle 10", index=False)
        neg_last.to_excel(writer, sheet_name="NegList Last 10", index=False)
        
        filt_first.to_excel(writer, sheet_name="Filter First 10", index=False)
        filt_mid.to_excel(writer, sheet_name="Filter Middle 10", index=False)
        filt_last.to_excel(writer, sheet_name="Filter Last 10", index=False)
        
        mast_first.to_excel(writer, sheet_name="Master First 10", index=False)
        mast_mid.to_excel(writer, sheet_name="Master Middle 10", index=False)
        mast_last.to_excel(writer, sheet_name="Master Last 10", index=False)

    # 4. FORMATTING EXCEL WITH STYLES
    print("Styling sheets...")
    wb = openpyxl.load_workbook(output_path)
    
    font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    font_normal = Font(name="Segoe UI", size=10)
    font_bold = Font(name="Segoe UI", size=10, bold=True)
    fill_header = PatternFill(start_color="1F4E78", fill_type="solid")
    fill_ssis = PatternFill(start_color="F2F2F2", fill_type="solid")
    fill_python = PatternFill(start_color="E2EFDA", fill_type="solid")
    fill_match = PatternFill(start_color="D9E1F2", fill_type="solid")
    border_thin = Border(
        left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'),
        top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF')
    )

    # Style Table Summary sheet
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

    # Style Data sheets
    data_sheets = [
        "NegList First 10", "NegList Middle 10", "NegList Last 10",
        "Filter First 10", "Filter Middle 10", "Filter Last 10",
        "Master First 10", "Master Middle 10", "Master Last 10"
    ]

    for sname in data_sheets:
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

    # Auto-adjust column width
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
    print("\nExcel Verification Report successfully generated!")
    print(f"Saved to: {output_path}")

    # Close connections
    cursor_py.close()
    conn_py.close()
    cursor_ssis_data.close()
    conn_ssis_data.close()
    cursor_ssis_prod.close()
    conn_ssis_prod.close()

if __name__ == "__main__":
    main()
