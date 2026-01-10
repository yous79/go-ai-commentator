import subprocess
import sys
import time
import os

def verify():
    # プロジェクトルートのパスを取得
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir) # src/
    main_py = os.path.join(project_root, "main.py")
    
    print(f"Testing startup of {main_py}...")
    
    # タイムアウト設定 (5秒間生存すれば合格)
    timeout = 5
    
    # GUIアプリなので、stdout/stderrをキャプチャしつつ起動
    # shell=False (Windowsでは推奨)
    try:
        proc = subprocess.Popen(
            [sys.executable, main_py],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root # src/ ディレクトリを作業ディレクトリに設定
        )
        
        # 指定時間待機
        time.sleep(timeout)
        
        # プロセスの状態を確認
        if proc.poll() is None:
            print(f"Startup SUCCESS: Application stayed alive for {timeout} seconds.")
            # 正常に動いているので終了させる
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            return True
        else:
            # 5秒以内に終了してしまった場合はエラー
            stdout, stderr = proc.communicate()
            print(f"Startup FAILED: Application exited early with code {proc.returncode}.")
            if stderr:
                print(f"Error output:\n{stderr}")
            return False
            
    except Exception as e:
        print(f"Test execution error: {e}")
        return False

if __name__ == "__main__":
    if verify():
        sys.exit(0)
    else:
        sys.exit(1)
