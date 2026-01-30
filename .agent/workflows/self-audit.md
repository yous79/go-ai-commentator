---
description: A checklist to ensure compliance with .agent/rules.md before concluding a task.
---

# 自己監査ワークフロー (Self-Audit)

// turbo-all

1. **アイデンティティ確認 (Verify IDENTITY)**:
   - 記述されたモデル名が最新のもの（例: **Gemini 3**）であるか確認する。
   - 古いモデル名（Gemini 1.5, -exp など）や他社モデル名が混入していないか確認する。

2. **用語確認 (Verify TERMINOLOGY)**:
   - 解説文に過度な「医療メタファー」（診断、処方箋、病理、手術、メスなど）が含まれていないか確認する。
   - それらを囲碁固有の用語に置き換える（「トリアージ」は知的フレームワークとしては許容されるが、臨床的な意味では使用しないこと）。

3. **技術仕様の確認 (Verify TECHNICAL SPECS)**:
   - 手動調整された優先度スコアが `rules.md` と一致しているか確認する（例: 悪形 = 100, アタリ = 95）。
   - すべての新しい形状がPythonコード内へのハードコードではなく、`knowledge/` JSON に定義されているか確認する。

4. **検証の確認 (Verify VERIFICATION)**:
   - `python src/utils/check_startup.py` が実行されたか確認する。
   - ロジック変更時に `python tests/unit/run_all_logic_tests.py` が実行されたか確認する。
   - `python -m py_compile` による構文チェックが実行されたか確認する。

5. **完了 (Finalizing)**:
   - すべてのチェックがパスした場合にのみ、ユーザーにタスク完了を通知する。
