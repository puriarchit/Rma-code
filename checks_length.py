import zipfile
import os

zip_path = r"D:\LexisNexis\MWV01TF_WorldCompliancePlus_20260508_075958.zip"
output_file = r"D:\LexisNexis\max_lengths.txt"

print("Opening ZIP file directly (No extraction needed)...\n")
out_lines = []

with zipfile.ZipFile(zip_path, "r") as z:
    for name in z.namelist():
        if name.endswith(".txt"):
            filename = os.path.basename(name)
            print(f"🔍 Scanning file inside ZIP: {filename} ... Please wait...")
            out_lines.append(f"File: {filename}\n")
            
            try:
                with z.open(name, "r") as f:
                    # Clean carriage returns and split by pipe
                    header_line = f.readline().decode("utf-8", errors="ignore")
                    header = header_line.strip('\r\n').split('|')
                    
                    max_lengths = [0] * len(header)
                    
                    for line_bytes in f:
                        line = line_bytes.decode("utf-8", errors="ignore")
                        fields = line.strip('\r\n').split('|')
                        for i, val in enumerate(fields):
                            if i < len(max_lengths):
                                val_len = len(val.strip()) if val else 0
                                if val_len > max_lengths[i]:
                                    max_lengths[i] = val_len
                                    
                print(f"✅ COMPLETED: {filename}\n")
                for col, max_len in zip(header, max_lengths):
                    res_line = f"  - {col}: Max Length = {max_len}"
                    print(res_line)
                    out_lines.append(res_line + "\n")
                print("-" * 50)
                out_lines.append("-" * 50 + "\n")
                
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}\n")
                out_lines.append(f"Error reading {filename}: {e}\n")

# Save all results to a text file
with open(output_file, "w", encoding="utf-8") as out_f:
    out_f.writelines(out_lines)

print(f"\nAll files scanned! Results saved in: {output_file}")
