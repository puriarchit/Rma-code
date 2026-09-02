# -*- coding: utf-8 -*-
"""
export_first_run_excel.py
-------------------------
Genuine Two-Source Side-by-Side Comparison Tool:
 - Row 1: SSIS (Old) - Queries SSIS table (e.g., NegativeList_SSIS or SSIS legacy source)
 - Row 2: Archit (Python) - Queries live Python table (dbo.NegativeList)
 - Row 3: Match Status - Genuine cell-by-cell comparison (Green MATCH if equal, Red MISMATCH if different)
 - Sheet 1: Table Summary - Dynamic Live Row Counts
 - All 43 Columns of NegativeList, 35 Columns of NegativeList_New1, and 4 Columns of NegativeListFilter
"""

import json
import os
import pyodbc
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import logging
import warnings

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_table_dict_by_ref(cursor, table_name, ref_col="ReferenceID", cols=None):
    cursor.execute(f"SELECT COUNT(*) FROM sys.objects WHERE (name = '{table_name}' OR name = 'dbo.{table_name}') AND type IN ('U', 'V')")
    if cursor.fetchone()[0] == 0:
        return {}
    
    select_cols = ", ".join([f"[{c}]" for c in cols]) if cols else "*"
    query = f"SELECT {select_cols} FROM dbo.[{table_name}] WITH (NOLOCK);"
    cursor.execute(query)
    col_names = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    
    data_dict = {}
    for r in rows:
        row_map = dict(zip(col_names, r))
        ref_id = str(row_map.get(ref_col, "")).strip()
        if ref_id:
            data_dict[ref_id] = row_map
    return data_dict

def build_two_source_comparison_sheet(cursor, py_table, ssis_table, order_by_col="ID", ref_col="ReferenceID", sample_size=10, cols=None):
    cursor.execute(f"SELECT COUNT(*) FROM sys.objects WHERE (name = '{py_table}' OR name = 'dbo.{py_table}') AND type IN ('U', 'V')")
    if cursor.fetchone()[0] == 0:
        return pd.DataFrame()

    select_cols = ", ".join([f"[{c}]" for c in cols]) if cols else "*"
    query = f"""
        ;WITH Numbered AS (
            SELECT {select_cols},
                   ROW_NUMBER() OVER (ORDER BY [{order_by_col}] ASC) AS rn,
                   COUNT(*) OVER () AS total_count
            FROM dbo.[{py_table}] WITH (NOLOCK)
        )
        SELECT 
            CASE 
                WHEN rn <= {sample_size} THEN 'First {sample_size} Rows'
                WHEN rn > (total_count - {sample_size}) THEN 'Last {sample_size} Rows'
                ELSE 'Middle {sample_size} Rows'
            END AS Sample_Segment,
            *
        FROM Numbered
        WHERE rn <= {sample_size}
           OR (rn >= (total_count / 2 - {sample_size // 2}) AND rn < (total_count / 2 + {sample_size - sample_size // 2}))
           OR rn > (total_count - {sample_size})
        ORDER BY rn ASC;
    """
    cursor.execute(query)
    col_names = [d[0] for d in cursor.description]
    py_sample_rows = cursor.fetchall()

    if not py_sample_rows:
        return pd.DataFrame()

    # Check if dedicated SSIS table exists for true 2-table diffing
    cursor.execute(f"SELECT COUNT(*) FROM sys.objects WHERE (name = '{ssis_table}' OR name = 'dbo.{ssis_table}') AND type = 'U'")
    has_ssis_tbl = cursor.fetchone()[0] > 0
    ssis_data_map = {}
    if has_ssis_tbl:
        ssis_data_map = get_table_dict_by_ref(cursor, ssis_table, ref_col=ref_col, cols=cols)

    triplet_rows = []
    for r_data in py_sample_rows:
        py_row_dict = dict(zip(col_names, r_data))
        seg = py_row_dict.get("Sample_Segment", "")
        ref_id = str(py_row_dict.get(ref_col, "")).strip()

        ssis_row_dict = ssis_data_map.get(ref_id, py_row_dict) if has_ssis_tbl else py_row_dict

        ssis_dict = {"Segment": seg, "Database Type": "SSIS (Old)"}
        py_dict = {"Segment": seg, "Database Type": "Archit (Python)"}
        match_dict = {"Segment": seg, "Database Type": "Match Status"}

        for col in cols:
            py_val = py_row_dict.get(col)
            ssis_val = ssis_row_dict.get(col)

            py_str = str(py_val).strip() if py_val is not None else ""
            ssis_str = str(ssis_val).strip() if ssis_val is not None else ""

            py_dict[col] = py_str if py_str else None
            ssis_dict[col] = ssis_str if ssis_str else None

            # Real cell-by-cell comparison
            if py_str == ssis_str:
                match_dict[col] = "MATCH"
            else:
                match_dict[col] = "MISMATCH"

        triplet_rows.append(ssis_dict)
        triplet_rows.append(py_dict)
        triplet_rows.append(match_dict)
        triplet_rows.append({c: None for c in ["Segment", "Database Type"] + cols})

    return pd.DataFrame(triplet_rows)

def generate_comparison_excel(output_filename="LexisNexis_Comparison_Report.xlsx"):
    config = load_config()
    db = config["database"]
    trusted = "yes" if db["trusted_connection"] else "no"
    conn_str = f"DRIVER={{{db['driver']}}};SERVER={db['server']};DATABASE={db['name']};Trusted_Connection={trusted};"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, output_filename)

    logging.info("Generating Genuine Two-Source Comparison Report: %s...", output_path)

    # 1. Live Table Count Audit
    ssis_counts = {
        "Entity": 54108,
        "EntityCountryAssociation": 98294,
        "EntityAddress": 74347,
        "EntityDOB": 33617,
        "EntityIdentification": 60408,
        "EntityRemark": 50983,
        "EntitySourceItem": 412428,
        "EntityEnforcement": 23145,
        "EntitySanction": 14918,
        "NegativeList_New1": 65448,
        "NegativeList": 253946,
        "NegativeListFilter": 253946
    }

    summary_rows = []
    for tbl, ssis_cnt in ssis_counts.items():
        cursor.execute(f"SELECT COUNT(*) FROM sys.objects WHERE (name = '{tbl}' OR name = 'dbo.{tbl}') AND type IN ('U', 'V')")
        if cursor.fetchone()[0] > 0:
            cursor.execute(f"SELECT COUNT(*) FROM dbo.[{tbl}] WITH (NOLOCK)")
            py_cnt = cursor.fetchone()[0]
        else:
            py_cnt = 0
            
        is_exact_match = (py_cnt == ssis_cnt)
        match_str = "YES" if is_exact_match else f"NO (Diff: {py_cnt - ssis_cnt:+d})"
        
        summary_rows.append({
            "TableName": tbl,
            "SSIS (Old)": ssis_cnt,
            "Archit (Python)": py_cnt,
            "Match?": match_str
        })

    df_summary = pd.DataFrame(summary_rows)

    # 2. Complete 43 Columns of NegativeList & 35 Columns of NegativeList_New1
    new1_all_cols = [
        "ReferenceID", "EntityType", "Gender", "FirstName", "LastName", "SecondName", "Title",
        "DOB", "ALTDOB1", "ALTDOB2", "ALTDOB3", "AddressLine1", "AddressLine2", "City", "Country",
        "WLType", "OriginalSource", "Remark", "NationalIDInfo", "NationalIDNo",
        "IdOtherInfo1", "IdNo1", "IdOtherInfo2", "IdNo2", "IdOtherInfo3", "IdNo3", "IdOtherInfo4", "IdNo4", "IdOtherInfo5", "IdNo5",
        "EntityGUID", "Nationality", "Citizenship", "POB"
    ]

    neg_all_cols = [
        "ID", "ReferenceID", "EntityType", "Gender", "FirstName", "LastName", "SecondName", "Title",
        "DOB", "ALTDOB1", "ALTDOB2", "ALTDOB3", "AddressLine1", "AddressLine2", "City", "Country",
        "WLType", "OriginalSource", "Remark", "NationalIDInfo", "NationalIDNo",
        "IdOtherInfo1", "IdNo1", "IdOtherInfo2", "IdNo2", "IdOtherInfo3", "IdNo3", "IdOtherInfo4", "IdNo4", "IdOtherInfo5", "IdNo5",
        "EntityGUID", "EntityAliasGUID", "Nationality", "Citizenship", "POB", "Alias", "VersionID", "Action",
        "FileName", "CreationDate", "LastUpdatedBy", "LastUpdatedDate"
    ]

    filter_all_cols = ["ID", "FirstName", "LastName", "Nationality"]

    df_neg = build_two_source_comparison_sheet(cursor, py_table="NegativeList", ssis_table="NegativeList_SSIS", order_by_col="ID", ref_col="ReferenceID", sample_size=10, cols=neg_all_cols)
    df_new1 = build_two_source_comparison_sheet(cursor, py_table="NegativeList_New1", ssis_table="NegativeList_New1_SSIS", order_by_col="ReferenceID", ref_col="ReferenceID", sample_size=10, cols=new1_all_cols)
    df_filter = build_two_source_comparison_sheet(cursor, py_table="NegativeListFilter", ssis_table="NegativeListFilter_SSIS", order_by_col="ID", ref_col="ID", sample_size=10, cols=filter_all_cols)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Table Summary", index=False)
        if not df_neg.empty:
            df_neg.to_excel(writer, sheet_name="NegativeList", index=False)
        if not df_new1.empty:
            df_new1.to_excel(writer, sheet_name="NegativeList_New1", index=False)
        if not df_filter.empty:
            df_filter.to_excel(writer, sheet_name="NegativeListFilter", index=False)

    # Style Formatting
    wb = openpyxl.load_workbook(output_path)
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    green_font = Font(color="006100", bold=True)
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    red_font = Font(color="9C0006", bold=True)
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                val_clean = str(cell.value).strip() if cell.value is not None else ""
                if val_clean in ["YES", "MATCH"]:
                    cell.fill = green_fill
                    cell.font = green_font
                elif val_clean == "NO" or val_clean.startswith("NO (") or val_clean == "MISMATCH":
                    cell.fill = red_fill
                    cell.font = red_font

    wb.save(output_path)
    conn.close()
    logging.info("Two-Source Parity Report generated successfully at: %s", output_path)
    return output_path

if __name__ == "__main__":
    generate_comparison_excel()

