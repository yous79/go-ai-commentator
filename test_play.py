import sys
import os
import subprocess

def main():
    """
    Legacy wrapper for launching Test Play Mode.
    Redirects to the new unified entry point: src/main.py --test-play
    """
    print("Redirecting to unified entry point: src/main.py --test-play")
    
    # Get the python executable
    python_exe = sys.executable
    
    # Construct the command
    script_path = os.path.join("src", "main.py")
    cmd = [python_exe, script_path, "--test-play"]
    
    # Run the command
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error launching application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
