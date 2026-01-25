import subprocess
import sys
import time
import os
import importlib.util

def check_imports(project_root):
    """
    動的インポートにより、アプリ起動時ではなく操作時に発生する可能性のある
    ImportError / ModuleNotFoundError を事前に検知する。
    """
    print("\n[V1] Starting Import Smoke Test...")
    modules_to_test = [
        "gui.app",
        "gui.test_play_app",
        "gui.master",
        "services.analysis_service",
        "utils.renderer.renderer"
    ]
    
    # PYTHONPATH に src を追加してインポート可能にする
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    success = True
    for mod_name in modules_to_test:
        try:
            # 実際にロードを試みる
            importlib.import_module(mod_name)
            print(f"  OK: {mod_name}")
        except Exception as e:
            print(f"  FAILED: {mod_name} -> {e}")
            success = False
            
    return success

def verify_startup():
    # プロジェクトルートのパスを取得
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir) # src/
    main_py = os.path.join(project_root, "main.py")
    
    # 1. インポート・スモークテスト
    if not check_imports(project_root):
        print("\n[V1] Import Test FAILED. Correct the missing modules before proceeding.")
        return False
    print("[V1] Import Test PASSED.")

    # 2. 実行時起動テスト
    print(f"\n[V2] Testing runtime startup of {main_py}...")
    timeout = 5
    try:
        proc = subprocess.Popen(
            [sys.executable, main_py],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root
        )
        
        time.sleep(timeout)
        
        if proc.poll() is None:
            print(f"[V2] Startup SUCCESS: Application stayed alive for {timeout} seconds.")
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            return True
        else:
            stdout, stderr = proc.communicate()
            print(f"[V2] Startup FAILED: Application exited early with code {proc.returncode}.")
            if stderr:
                print(f"Error output:\n{stderr}")
            return False
            
    except Exception as e:
        print(f"Test execution error: {e}")
        return False

if __name__ == "__main__":
    if verify_startup():
        print("\nALL VERIFICATIONS PASSED.")
        sys.exit(0)
    else:
        print("\nVERIFICATION FAILED.")
        sys.exit(1)
