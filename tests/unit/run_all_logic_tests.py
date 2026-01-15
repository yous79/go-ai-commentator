import os
import subprocess
import sys

def run_all_strict_tests():
    print("====================================================")
    print("   Go AI Commentator: Strict Logic Tests Suite      ")
    print("====================================================\n")
    
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = [f for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith("_strict.py")]
    
    passed_count = 0
    failed_tests = []

    for test_file in sorted(test_files):
        print(f"Running: {test_file}...")
        test_path = os.path.join(test_dir, test_file)
        
        # 実行環境として PYTHONPATH に src を追加
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(os.path.join(test_dir, "..", "..", "src"))
        
        try:
            # shell=True を使用して Windows での互換性を確保
            result = subprocess.run([sys.executable, test_path], env=env, capture_output=True, text=True, check=True)
            print(result.stdout)
            passed_count += 1
        except subprocess.CalledProcessError as e:
            print(f"\n[FAILED] {test_file}")
            print(e.stdout)
            print(e.stderr)
            failed_tests.append(test_file)

    print("\n" + "=" * 52)
    print(f" SUMMARY: {passed_count} / {len(test_files)} tests passed.")
    print("=" * 52)

    if failed_tests:
        print("\nTHE FOLLOWING TESTS FAILED:")
        for ft in failed_tests:
            print(f"  - {ft}")
        sys.exit(1)
    else:
        print("\nALL STRICT LOGIC TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)

if __name__ == "__main__":
    run_all_strict_tests()
