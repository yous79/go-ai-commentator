import os
import subprocess
import sys

def main():
    """
    Automatically launches the Go AI Commentator with 'test.sgf' loaded.
    Assumes 'test.sgf' exists in the current directory.
    """
    # 1. Resolve paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_sgf_path = os.path.join(current_dir, "test.sgf")
    main_script_path = os.path.join(current_dir, "src", "main.py")

    if not os.path.exists(test_sgf_path):
        print(f"Error: test.sgf not found at {test_sgf_path}")
        # Create a dummy test.sgf if not exists for convenience?
        # For now, let's assume it exists or fail.
        # Constructing a minimal SGF just in case:
        with open(test_sgf_path, "w") as f:
            f.write("(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[qp];W[dd])")
        print("Created dummy test.sgf")

    print(f"Launching {main_script_path} with {test_sgf_path}...")

    # 2. Run main.py
    # Use python executable from current environment
    cmd = [sys.executable, main_script_path, test_sgf_path]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nTerminated by user.")
    except Exception as e:
        print(f"Error launching app: {e}")

if __name__ == "__main__":
    main()
