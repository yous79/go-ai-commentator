import subprocess
import os
import json
import time

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPT_DIR, "katago", "2023-06-15-windows64+katago")
KATAGO_EXE = os.path.join(BASE_DIR, "katago_opencl", "katago.exe")
CONFIG = os.path.join(BASE_DIR, "katago_configs", "analysis.cfg")
MODEL = os.path.join(BASE_DIR, "weights", "kata20bs530.bin.gz")

def test_katago():
    print(f"Script Directory: {SCRIPT_DIR}")
    print("Checking paths...")
    print(f"Exe: {os.path.exists(KATAGO_EXE)} -> {KATAGO_EXE}")
    print(f"Config: {os.path.exists(CONFIG)} -> {CONFIG}")
    print(f"Model: {os.path.exists(MODEL)} -> {MODEL}")

    if not all([os.path.exists(KATAGO_EXE), os.path.exists(CONFIG), os.path.exists(MODEL)]):
        print("Error: Some files are missing.")
        return

    cmd = [
        KATAGO_EXE,
        "analysis",
        "-config", CONFIG,
        "-model", MODEL
    ]

    print(f"Starting KataGo with command: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Give it a moment to initialize
        print("Waiting for initialization...")
        
        # KataGo output its version and info to stderr usually, logic loop listens on stdin
        # Let's send a simple query for an empty 19x19 board
        query = {
            "id": "test_query",
            "moves": [],
            "rules": "japanese",
            "komi": 6.5,
            "boardXSize": 19,
            "boardYSize": 19,
            "includePolicy": False
        }
        
        print("Sending query...")
        process.stdin.write(json.dumps(query) + "\n")
        process.stdin.flush()
        
        print("Reading response...")
        while True:
            line = process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            
            try:
                response = json.loads(line)
                print("Received valid JSON response!")
                # print(json.dumps(response, indent=2)) # Might be too large to print all
                print(f"Response ID: {response.get('id')}")
                if 'rootInfo' in response:
                    print(f"Winrate: {response['rootInfo'].get('winrate')}")
                    print(f"ScoreLead: {response['rootInfo'].get('scoreLead')}")
                break
            except json.JSONDecodeError:
                print(f"Raw output: {line}")

        process.terminate()
        print("Test successful.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_katago()
