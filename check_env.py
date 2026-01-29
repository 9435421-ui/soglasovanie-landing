import os
import sys
from dotenv import load_dotenv
def check():
    if not os.path.exists(".env"): return False
    load_dotenv()
    required_keys = ["BOT_TOKEN", "OPENROUTER_API_KEY", "ADMIN_ID"]
    for key in required_keys:
        val = os.getenv(key)
        if not val or "your_" in val: return False
    return True
if __name__ == "__main__":
    if check(): sys.exit(0)
    else: sys.exit(1)
