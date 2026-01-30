---
name: go_logic
description: Specialized geometric and strategic logic for Go board analysis.
---

# 囲碁ロジックスキル

このスキルは、囲碁の「形」を特定し、盤面状態を評価するための技術仕様を提供します。

## 形状定義 (Shape Definitions)
- **アキ三角 (Aki-sankaku)**: 2x2 のマスのうち3箇所に自分の石があり、1箇所が空点の形。高優先度の警告対象。
- **サカレ形 (Sakare-gata)**: 分断された形。物理的/論理的な連絡を確認するために経路探索（BFS）を使用する。
- **カタツギ (Kata-tsugi)**: 相手の石1つに対して2x2を完成させるL字型の連絡。
- **カケツギ (Kake-tsugi)**: 内側の純度（Purity）と相手からの圧力を考慮したV字型（虎の口）の連絡。

## 解析ロジック
- **安定度スコア (Stability Score)**: Ownership（占有率）データに基づく5段階評価（死 / 危険 / 弱い / 安定 / 厚い）。
- **ヨセ認識 (Endgame Recognition)**: 地域的な占有率の確実性（閾値 > 0.9）に基づく進行フェーズの検出。
- **カス石 (Junk Stone)**: 既に Ownership > 0.8 で死んでいる石の近くに打たれた着手の干渉検出。

## リソース
- パターン定義: `knowledge/` ディレクトリ。
- 検証: `test_play.py` および単体テスト。
