import os

# Base Directories
# src folder
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
# Project root (one level up)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

OUTPUT_BASE_DIR = os.path.join(PROJECT_ROOT, "output_images")

# KataGo Settings
KATAGO_BASE_DIR = os.path.join(PROJECT_ROOT, "katago", "2023-06-15-windows64+katago")
KATAGO_EXE = os.path.join(KATAGO_BASE_DIR, "katago_opencl", "katago.exe")
KATAGO_CONFIG = os.path.join(KATAGO_BASE_DIR, "katago_configs", "analysis.cfg")
KATAGO_MODEL = os.path.join(KATAGO_BASE_DIR, "weights", "kata20bs530.bin.gz")

# API Keys
API_KEY_PATH = os.path.join(PROJECT_ROOT, "api_key.txt")

# Knowledge Base
KNOWLEDGE_DIR = os.path.join(PROJECT_ROOT, "knowledge")

# Helper Functions
def load_api_key():
    if os.path.exists(API_KEY_PATH):
        try:
            with open(API_KEY_PATH, "r") as f:
                return f.read().strip()
        except:
            return None
    return None
