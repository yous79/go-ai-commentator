# エラー修正レポート: 対局レポート生成エラー

## 📋 エラー概要

```
[2026-01-26 13:38:34] [ASYNC] [ERROR] Async task failed: 'MoveCandidate' object has no attribute 'get'
Exception in Tkinter callback
...
NameError: cannot access free variable 'e' where it is not associated with a value in enclosing scope
```

## 🔍 原因分析

### 1. **主要エラー: `MoveCandidate` オブジェクトの誤った使用**
- **場所**: `src/services/report_generator.py:80`
- **問題**: `MoveCandidate` オブジェクトを辞書として扱い、`.get('move', 'なし')` でアクセスしていた
- **原因**: `MoveCandidate` は `@dataclass` で定義されたオブジェクトであり、辞書メソッドは持たない

### 2. **副次的エラー: クロージャのスコープ問題**
- **場所**: `src/services/async_task_manager.py:59`
- **問題**: `lambda: on_error(e)` で変数 `e` が正しくキャプチャされていなかった
- **原因**: Pythonのクロージャは遅延バインディングを使用するため、ループ変数や例外変数は正しくキャプチャされない

### 3. **潜在的エラー: `show_pv` メソッドの型不一致**
- **場所**: `src/gui/app.py:381-388`
- **問題**: `AnalysisResult` オブジェクトと辞書の両方が混在する可能性があるが、辞書としてのみ扱っていた

## 🔧 修正内容

### ✅ 修正1: `report_generator.py` (80行目)

**修正前:**
```python
r_md += f"### 手数 {m_idx} (黒番のミス)\n- **AI推奨**: {best.get('move', 'なし')}\n..."
```

**修正後:**
```python
r_md += f"### 手数 {m_idx} (黒番のミス)\n- **AI推奨**: {best.move}\n..."
```

**理由**: `best` は `MoveCandidate` オブジェクトなので、属性アクセス `.move` を使用

---

### ✅ 修正2: `async_task_manager.py` (59行目)

**修正前:**
```python
if on_error:
    self.root.after(0, lambda: on_error(e))
```

**修正後:**
```python
if on_error:
    self.root.after(0, lambda err=e: on_error(err))
```

**理由**: デフォルト引数 `err=e` を使用することで、例外オブジェクトを即座にキャプチャ

---

### ✅ 修正3: `app.py` (381-388行目)

**修正前:**
```python
def show_pv(self):
    curr = self.controller.current_move
    if curr < len(self.game.moves):
        d = self.game.moves[curr]
        if d:
            cands = d.get('candidates', []) or d.get('top_candidates', [])
            if cands and 'pv' in cands[0]:
                self._show_pv_window("Variation", cands[0]['pv'])
```

**修正後:**
```python
def show_pv(self):
    curr = self.controller.current_move
    if curr < len(self.game.moves):
        d = self.game.moves[curr]
        if d:
            # AnalysisResultオブジェクトか辞書かを判別
            if hasattr(d, 'candidates'):
                cands = d.candidates
            else:
                cands = d.get('candidates', []) or d.get('top_candidates', [])
            
            if cands:
                # 候補手がMoveCandidate オブジェクトか辞書かを判別
                first_cand = cands[0]
                if hasattr(first_cand, 'pv'):
                    pv_list = first_cand.pv
                elif isinstance(first_cand, dict) and 'pv' in first_cand:
                    pv_list = first_cand['pv']
                else:
                    return
                
                if pv_list:
                    self._show_pv_window("Variation", pv_list)
```

**理由**: オブジェクトと辞書の両方に対応し、型安全性を向上

## ✅ 検証結果

### 構文チェック
```bash
python -m py_compile src/services/report_generator.py src/services/async_task_manager.py src/gui/app.py
```
✅ **成功**: 構文エラーなし

### アプリケーション起動テスト
```bash
python src/main.py
```
✅ **成功**: アプリケーションが正常に起動

## 📊 影響範囲

| ファイル                | 修正箇所    | 影響度 | 説明                             |
| ----------------------- | ----------- | ------ | -------------------------------- |
| `report_generator.py`   | 80行目      | **高** | 対局レポート生成の主要エラー修正 |
| `async_task_manager.py` | 59行目      | **中** | エラーハンドリングの安定性向上   |
| `app.py`                | 381-403行目 | **中** | PV表示機能の堅牢性向上           |

## 🎯 今後の推奨事項

1. **型ヒントの追加**: `MoveCandidate` や `AnalysisResult` を使用する箇所に型ヒントを追加
2. **統一的なデータ処理**: オブジェクトと辞書が混在しないよう、データ構造を統一
3. **ユニットテスト**: 対局レポート生成機能のテストケースを追加

## 📝 まとめ

- ✅ `MoveCandidate` オブジェクトの属性アクセスを修正
- ✅ クロージャのスコープ問題を解決
- ✅ 型安全性を向上させ、潜在的なバグを防止
- ✅ 構文チェックとアプリケーション起動テストに合格

**修正完了日時**: 2026-01-26 13:41
