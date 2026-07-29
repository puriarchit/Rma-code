import zipfile
import os

# Zip file ka path set kiya hai
zip_path = r"D:\LexisNexis\MWV01TF_WorldCompliancePlus_20260508_075958.zip"

print("Opening ZIP file directly (No extraction needed)...\n")

with zipfile.ZipFile(zip_path, "r") as z:
    for name in z.namelist():
        # Sirf .txt files ko process karna hai
        if name.endswith(".txt"):
            filename = os.path.basename(name)
            print(f"🔍 Scanning file inside ZIP: {filename} ... Please wait...")
            
            try:
                # Zip ke andar file stream open karna
                with z.open(name, "r") as f:
                    # Header line read karna
                    header_line = f.readline().decode("utf-8", errors="ignore")
                    header = header_line.strip('\n').split('\t')
                    
                    max_lengths = [0] * len(header)
                    
                    for line_bytes in f:
                        line = line_bytes.decode("utf-8", errors="ignore")
                        fields = line.strip('\n').split('\t')
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
