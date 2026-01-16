# 囲碁AI解説システム 統合仕様書 (Gemini.md) - Rev. 35.0

## 0. モデル名称・認識に関する絶対規約 (Model Identification Protocol) - [改定不可]
1.  **最新モデルの正確な認識**: 本システムが使用する最新の戦略的知性モデルは **Gemini 3 Flash Preview** である。
2.  (以下省略)

## 1. ビジョンと絶対目標
- **Gemini 3 Flash Preview** の戦略的知性と KataGo の精密な計算を融合させ、級位者が論理的に「納得」できる対話型解説体験を提供する。
- **ペルソナの統合**: AIアシスタントは「囲碁ドクター」としての人格を持ち、論理性・効率性・再現性を重視した指導を行う。

## 2. 形状検知ロジック：完全データ駆動型 (Data-Driven Shape Engine) [REVISED]
形状検知は、Python コードによる実装を完全に廃止し、JSON による**宣言的パターン定義**へと 100% 移行した。

### 2.1 汎用パターン照合エンジン
- **データ駆動**: `knowledge/` 配下の `pattern.json` を動的に読み込み、`GenericPatternDetector` が全ての照合を担当する。
- **幾何学的網羅性**: 8方向の回転・反転を自動適用。
- **動的サイズ同期**: 盤面サイズ（9, 13, 19）に応じて境界チェックを自動調整する。

## 3. 高度な解析アーキテクチャ (Purified Architecture) [NEW]
解析と解説の責務を分離し、論理的な一貫性を担保する。

### 3.1 AnalysisOrchestrator (解析指揮官)
- **集約**: KataGo, 形状検知, 安定度, 緊急度の全解析工程を統括する。
- **出力**: 解析結果を `FactCollector` に集約し、構造化された「事実セット」を生成する。

### 3.2 SimulationContext & InferenceFact
- **SimulationContext**: 局面の状態（盤面、履歴、手番色）をカプセル化し、現在および未来の局面を同一のインターフェースで扱う。
- **InferenceFact**: 解析事実を重要度（Severity）付きのオブジェクトとして管理し、情報のトリアージ（優先順位付け）を実現する。

## 4. AI解説生成：事実先行・人格統合プロトコル
- **確定事実の優先**: Orchestrator から提供された「トリアージ済み事実」をプロンプト最上部に配置。
- **解説への専念**: AI は自らツールを呼び出すのではなく、与えられた事実の言語化（意味付け）に集中する。

## 5. アーキテクチャと信頼性
- **MVCパターンの徹底**: View (app.py), Controller (controller.py), Orchestrator (analysis_orchestrator.py), API (api_client.py) の疎結合を維持。
- **サーキット・ブレーカー**: 通信障害時の自動遮断。

## 6. 開発デバッグ・堅牢性指針
- **二重検証義務**: コード変更後は必ず以下を実行し、合格を確認すること。
    1. `python src/utils/check_startup.py` (インフラ確認)
    2. `python tests/unit/run_all_logic_tests.py` (厳密論理テスト環境)

(以下省略)