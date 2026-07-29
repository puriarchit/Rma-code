import os

folder = r"D:\LexisNexis\MWV01TF_WorldCompliancePlus_20260508_075958\MWV01TF_WorldCompliancePlus_20260508_075958"

print("Scanning files for maximum column lengths...\n")

for filename in os.listdir(folder):
    if filename.endswith(".txt"):
        filepath = os.path.join(folder, filename)
        try:
            f = open(filepath, "r", encoding="utf-8", errors="ignore")
            # header columns
            header = f.readline().strip('\n').split('\t')
            
            # initialize max lengths array
            max_lengths = [0] * len(header)
            
            for line in f:
                fields = line.strip('\n').split('\t')
                for i, val in enumerate(fields):
                    if i < len(max_lengths):
                        val_len = len(val.strip()) if val else 0
                        if val_len > max_lengths[i]:
                            max_lengths[i] = val_len
            f.close()
            
            print(f"File: {filename}")
            for col, max_len in zip(header, max_lengths):
                print(f"  - {col}: Max Length = {max_len}")
            print("-" * 40)
            
        except Exception as e:
            print(f"Error reading {filename}: {e}")

print("\nScan completed!")


Get-ChildItem -Path "D:\LexisNexis" -Directory | Select-Object -ExpandProperty Name
