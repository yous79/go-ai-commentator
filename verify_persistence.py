import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath("src"))

from core.analysis_config import AnalysisConfig

def test_persistence():
    print("=== Starting Config Persistence Verification ===")
    
    config_file = os.path.join("config", "analysis_settings.json")
    if os.path.exists(config_file):
        os.remove(config_file)
        print(f"Removed existing {config_file}")

    # 1. Initialize and change value
    config = AnalysisConfig()
    original_val = config.get("ATSUMI_THRESHOLD")
    new_val = 0.99
    
    print(f"Original ATSUMI_THRESHOLD: {original_val}")
    print(f"Setting ATSUMI_THRESHOLD to {new_val}")
    config.set_param("ATSUMI_THRESHOLD", new_val)
    
    # 2. Check if file exists and has correct value
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            data = json.load(f)
            assert data["ATSUMI_THRESHOLD"] == new_val
            print(f"SUCCESS: File saved with value {new_val}")
    else:
        print("FAILURE: Config file not found after save.")
        return

    # 3. Re-initialize (simulate restart)
    # Since AnalysisConfig is a singleton with class attributes, 
    # we need to force reload or check if it reloads on instantiation.
    # Actually, because it's already in memory, we should clear the state or use a separate process.
    # For a simple test, let's just manually trigger load() call again.
    
    print("Re-loading config...")
    config.load()
    loaded_val = config.get("ATSUMI_THRESHOLD")
    assert loaded_val == new_val
    print(f"SUCCESS: Re-loaded value: {loaded_val}")

    # Cleanup
    # os.remove(config_file)
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    test_persistence()
