import json
import os

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    print("\n==========================================")
    print("Database Settings in config.json:")
    print("==========================================")
    for k, v in config["database"].items():
        if k.lower() == "password":
            print(f"  {k}: {'*' * len(str(v))} (hidden)")
        else:
            print(f"  {k}: {v}")
    print("==========================================\n")
else:
    print("config.json not found next to this script.")

