import zipfile
import os

zip_path = r"D:\LexisNexis\MWV01TF_WorldCompliancePlus_20260508_075958.zip"

print("Opening ZIP file directly (No extraction needed)...\n")

with zipfile.ZipFile(zip_path, "r") as z:
    for name in z.namelist():
        if name.endswith(".txt"):
            filename = os.path.basename(name)
            print(f"🔍 Scanning file inside ZIP: {filename} ... Please wait...")
            
            try:
                with z.open(name, "r") as f:
                    # Pipe '|' se split kiya
                    header_line = f.readline().decode("utf-8", errors="ignore")
                    header = header_line.strip('\n').split('|')
                    
                    max_lengths = [0] * len(header)
                    
                    for line_bytes in f:
                        line = line_bytes.decode("utf-8", errors="ignore")
                        # Pipe '|' se split kiya
                        fields = line.strip('\n').split('|')
                        for i, val in enumerate(fields):
                            if i < len(max_lengths):
                                val_len = len(val.strip()) if val else 0
                                if val_len > max_lengths[i]:
                                    max_lengths[i] = val_len
                                    
                print(f"✅ COMPLETED: {filename}")
                for col, max_len in zip(header, max_lengths):
                    print(f"  - {col}: Max Length = {max_len}")
                print("-" * 50)
                
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")

print("\nAll files scanned inside ZIP successfully!")
