---
description: Ensure thorough codebase review before implementation
---

# 実装前チェックリスト

新機能追加やリファクタリング作業を開始する前にこのワークフローを実行し、重複防止とアーキテクチャの一貫性を確認すること。

1. **先行実装の確認 (Check Prior Art)**:
   - [ ] `PROJECT_STRUCTURE.md` を検索し、関連コンポーネントを確認する。
   - [ ] `grep` や `find` を実行し、類似ロジックの既存実装を特定する。
   - [ ] _特定チェック_: `src/core` や `src/services` に既にロジックが存在しないか？

2. **MCP整合性の確認 (Verify MCP Alignment)**:
   - [ ] `src/mcp_modules/` を確認し、その機能がMCPツールであるべきか判断する。
   - [ ] `design_mcp_engine.md` との整合性を確認する。

3. **ルールと制約 (Rules & Constraints)**:
   - [ ] `.agent/rules.md` をレビューする。
   - [ ] **古いモデル名の参照（Gemini 1.5, -exp など）が混入しないことを確認する。**

4. **影響分析 (Impact Analysis)**:
   - [ ] 影響を受ける可能性のある共有コンポーネント（EventBus, Renderer）を特定する。
   - [ ] 退行（ゾンビ購読など）を防ぐための検証手順を計画する。

// turbo
5. **出力要件**:
   - [ ] このチェックの要約を「実装計画書 (Implementation Plan)」に追加する。
