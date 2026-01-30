---
description: Standard workflow for developing new features and techniques.
---

# 新機能開発ワークフロー

// turbo-all

1. 機能ブランチを作成する:
   `git checkout -b feat/[feature-name]`

2. ロジックを調査し、実装計画を定義する（`IMPLEMENTATION_PLAN.md` を使用）。

3. ロジックを実装し、必要に応じてパターンを `knowledge/` に追加する。

4. 静的検証を実行する:
   `python -m py_compile [modified_files]`

5. 自動ロジックテストを実行する:
   `$env:PYTHONPATH="src"; python tests/unit/run_all_logic_tests.py`

6. 起動検証を実行する:
   `python src/utils/check_startup.py`

7. 完了と検証結果をユーザーに通知する。
