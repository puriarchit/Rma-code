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
            "Python (Archit Puri)": staging_count if staging_exists else "N/A",
            "Match?": "YES" if data_count == staging_count else "NO"
        })
    
    df_summary = pd.DataFrame(summary_data)

    print("Step 2: Fetching ReferenceIDs for First 10, Middle 10, and Last 10 Rows...")
    # Get First 10
    cursor_data.execute("""
        SELECT TOP 10 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 GROUP BY ReferenceID ORDER BY ReferenceID
    """)
    first_ids = [row[0] for row in cursor_data.fetchall()]
    
    # Get Middle 10 (offset around middle row 30000)
    cursor_data.execute("""
        SELECT ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 GROUP BY ReferenceID ORDER BY ReferenceID OFFSET 30000 ROWS FETCH NEXT 10 ROWS ONLY
    """)
    middle_ids = [row[0] for row in cursor_data.fetchall()]
    
    # Get Last 10
    cursor_data.execute("""
        SELECT TOP 10 ReferenceID FROM LexisNexis_Data.dbo.NegativeList_New1 GROUP BY ReferenceID ORDER BY ReferenceID DESC
    """)
    last_ids = sorted([row[0] for row in cursor_data.fetchall()])

    # All columns in table sequence
    all_columns = [
        "ReferenceID", "EntityType", "Gender", "FirstName", "LastName", "SecondName", "Title",
        "DOB", "ALTDOB1", "ALTDOB2", "ALTDOB3", "AddressLine1", "AddressLine2", "City", "Country",
        "WLType", "OriginalSource", "Remark", "NationalIDInfo", "NationalIDNo",
        "IdOtherInfo1", "IdNo1", "IdOtherInfo2", "IdNo2", "IdOtherInfo3", "IdNo3",
        "IdOtherInfo4", "IdNo4", "IdOtherInfo5", "IdNo5", "EntityGUID", "Nationality", "Citizenship", "POB"
    ]
    
    # Load character translation map for comparison cleaning
    cursor_data.execute("SELECT Symbol, MapChar FROM dbo.WLCharMap")
    char_map = cursor_data.fetchall()
    
    import re

    def wildcard_match(s1, s2):
        def clean_for_wildcard(text):
            if not text:
                return ""
            return "".join(c for c in text if c.isalnum() or c == "\ufffd").lower()
        
        c1 = clean_for_wildcard(s1)
        c2 = clean_for_wildcard(s2)
        
        if c1 == c2:
            return True
            
        # Prefix match for truncated remarks (min length 20)
        if len(c1) >= 20 and len(c2) >= 20:
            if c2.startswith(c1) or c1.startswith(c2):
                return True
                
        if "\ufffd" in c1 or "\ufffd" in c2:
            pattern = re.escape(c2).replace("\ufffd", ".")
            if re.match("^" + pattern + "$", c1):
                return True
                
            pattern2 = re.escape(c1).replace("\ufffd", ".")
            if re.match("^" + pattern2 + "$", c2):
                return True
                
        return False

    raw_ids_cache = {}

    def get_raw_ids(ref_id, cursor_data):
        ref_str = str(ref_id)
        if ref_str.endswith(".0"):
            ref_str = ref_str[:-2]
        if ref_str in raw_ids_cache:
            return raw_ids_cache[ref_str]
        
        cursor_data.execute("""
            SELECT DISTINCT IdentificationNumber 
            FROM LexisNexis_Data.dbo.EntityIdentification 
            WHERE EntityGUID = (SELECT EntityGUID FROM LexisNexis_Data.dbo.Entity WHERE EntityID = ?)
        """, (ref_str,))
        raw_ids = {r[0].strip().lower() for r in cursor_data.fetchall() if r[0]}
        
        raw_ids_cache[ref_str] = raw_ids
        return raw_ids

    def normalize_text(text):
        if not text:
            return ""
        text = text.replace("&amp;", "&")
        replacements = {
            "\u00c3\u00a1": "\u00e1",
            "\u00c3\u00a9": "\u00e9",
            "\u00c3\u00ad": "\u00ed",
            "\u00c3\u00b3": "\u00f3",
            "\u00c3\u00ba": "\u00fa",
            "\u00c3\u00b1": "\u00f1",
            "\u00c3\u0081": "\u00c1",
            "\u00c3\u0089": "\u00c9",
            "\u00c3\u008d": "\u00cd",
            "\u00c3\u0093": "\u00d3",
            "\u00c3\u009a": "\u00da",
            "\u00c3\u0091": "\u00d1",
            "\u00c3\u00bc": "\u00fc",
            "\u00c3\u009c": "\u00dc",
            "\u00e2\u0080\u0093": "\u2013",
            "\u00e2\u0080\u0094": "\u2014",
            "\u00e2\u0080\u009c": "\u201c",
            "\u00e2\u0080\u009d": "\u201d",
            "\u00e2\u0080\u0098": "\u2018",
            "\u00e2\u0080\u0099": "\u2019",
            "\u00c2\u00b6": "\u00b6",
            "\u00c2": ""
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = text.replace("\u00c2", "")
        return text

    def apply_wl_map(text):
        res = text
        for sym, mc in char_map:
            res = res.replace(sym, mc)
        return res

    def clean_compare_text(text):
        if not text:
            return ""
        return "".join(c for c in text if c.isalnum()).lower()

    def sort_dobs(vals):
        # DOB columns are at indices 7, 8, 9, 10
        dob_vals = [vals[7], vals[8], vals[9], vals[10]]
        cleaned_dobs = sorted([d for d in dob_vals if d and d != "None" and d.strip()])
        cleaned_dobs += [""] * (4 - len(cleaned_dobs))
        vals[7], vals[8], vals[9], vals[10] = cleaned_dobs[0], cleaned_dobs[1], cleaned_dobs[2], cleaned_dobs[3]

    def sort_ids(vals):
        # ID columns are at indices 20 to 29 (pairs of Info and No)
        id_pairs = []
        for idx in [20, 22, 24, 26, 28]:
            info = vals[idx]
            no = vals[idx+1]
            if (info and info != "None" and info.strip()) or (no and no != "None" and no.strip()):
                id_pairs.append((info, no))
        id_pairs = sorted(id_pairs, key=lambda x: (x[0] or "", x[1] or ""))
        id_pairs += [("", "")] * (5 - len(id_pairs))
        for i, idx in enumerate([20, 22, 24, 26, 28]):
            vals[idx] = id_pairs[i][0]
            vals[idx+1] = id_pairs[i][1]

    def build_comparison_rows(sample_ids):
        rows = []
        for ref_id in sample_ids:
            # Query SSIS
            sql_data = f"SELECT {', '.join(all_columns)} FROM LexisNexis_Data.dbo.NegativeList_New1 WHERE ReferenceID = ? ORDER BY WLType, CAST(OriginalSource AS NVARCHAR(MAX)), CAST(Remark AS NVARCHAR(MAX))"
            cursor_data.execute(sql_data, (ref_id,))
            ssis_rows = cursor_data.fetchall()
            
            # Query Python
            sql_staging = f"SELECT {', '.join(all_columns)} FROM LexisNexis_Staging.dbo.NegativeList_New1 WHERE ReferenceID = ? ORDER BY WLType, CAST(OriginalSource AS NVARCHAR(MAX)), CAST(Remark AS NVARCHAR(MAX))"
            cursor_staging.execute(sql_staging, (ref_id,))
            python_rows = cursor_staging.fetchall()
            
            # Map by matching unique row (we can have duplicates due to enforcements, so map them row by row)
            max_len = max(len(ssis_rows), len(python_rows))
            ref_written = False
            for i in range(max_len):
                ssis_row = ssis_rows[i] if i < len(ssis_rows) else None
                python_row = python_rows[i] if i < len(python_rows) else None
                
                s_vals = [str(x) if x is not None else "" for x in ssis_row] if ssis_row else [""] * len(all_columns)
                p_vals = [str(x) if x is not None else "" for x in python_row] if python_row else [""] * len(all_columns)
                
                # Sort DOBs and IDs to handle non-deterministic order
                sort_dobs(s_vals)
                sort_dobs(p_vals)
                sort_ids(s_vals)
                sort_ids(p_vals)
                
                match_vals = []
                for col_idx, (col_name, sv, pv) in enumerate(zip(all_columns, s_vals, p_vals)):
                    # Clean encoding noise for compare
                    sv_clean = normalize_text(sv)
                    pv_clean = normalize_text(pv)
                    
                    if col_name in ["FirstName", "LastName", "SecondName"]:
                        sv_clean = apply_wl_map(sv_clean)
                        pv_clean = apply_wl_map(pv_clean)
                    elif col_name == "OriginalSource":
                        # Sort URLs to bypass order difference
                        s_urls = sorted([x.strip() for x in sv_clean.split(";") if x.strip()])
                        p_urls = sorted([x.strip() for x in pv_clean.split(";") if x.strip()])
                        sv_clean = "; ".join(s_urls)
                        pv_clean = "; ".join(p_urls)
                        # Write back sorted raw URLs so they look visually matching in Excel
                        s_vals[col_idx] = "; ".join(sorted([x.strip() for x in sv.split(";") if x.strip()]))
                        p_vals[col_idx] = "; ".join(sorted([x.strip() for x in pv.split(";") if x.strip()]))
                    elif col_name == "Remark":
                        if wildcard_match(sv_clean, pv_clean):
                            sv_clean = pv_clean
                    elif col_name in ["IdNo1", "IdNo2", "IdNo3", "IdNo4", "IdNo5"]:
                        if sv_clean.lower().strip() != pv_clean.lower().strip():
                            raw_ids = get_raw_ids(ref_id, cursor_data)
                            sv_stripped = sv_clean.lower().strip()
                            pv_stripped = pv_clean.lower().strip()
                            if (not sv_stripped or sv_stripped in raw_ids) and (not pv_stripped or pv_stripped in raw_ids):
                                sv_clean = pv_clean
                    
                    if sv_clean.lower().strip() == pv_clean.lower().strip():
                        match_vals.append("MATCH")
                    else:
                        match_vals.append("MISMATCH")
                
                if not ref_written:
                    rows.append([ref_id, "SSIS (Old)"] + s_vals[1:])
                    rows.append([ref_id, "Python (Archit Puri)"] + p_vals[1:])
                    rows.append([ref_id, "Match Status"] + match_vals[1:])
                    rows.append([""] * (len(all_columns) + 1)) # Spacer
                    ref_written = True
                
        headers = ["ReferenceID", "Database Type"] + all_columns[1:]
        return pd.DataFrame(rows, columns=headers)

    print("Step 3: Building Row Splits...")
    df_first = build_comparison_rows(first_ids)
    df_mid = build_comparison_rows(middle_ids)
    df_last = build_comparison_rows(last_ids)

    output_path = r"D:\LexisNexis\LexisNexis_Comparison_Report.xlsx"
    print(f"Step 4: Writing to Excel file: {output_path}...")
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Table Summary", index=False)
        df_first.to_excel(writer, sheet_name="First 10 Rows", index=False)
        df_mid.to_excel(writer, sheet_name="Middle 10 Rows", index=False)
        df_last.to_excel(writer, sheet_name="Last 10 Rows", index=False)

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
    comp_sheets = ["First 10 Rows", "Middle 10 Rows", "Last 10 Rows"]
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
                            cell.font = Font(name="Segoe UI", size=10, bold=True, color="385723")
                            cell.fill = PatternFill(start_color="E2EFDA", fill_type="solid")
                        else:
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
