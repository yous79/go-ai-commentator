from sgfmill import sgf, boards
from core.game_board import GameBoard, Color
from core.point import Point
from utils.logger import logger
import sys

class GoGameState:
    def __init__(self):
        self.board_size = 19
        self.moves = [] 
        self.sgf_game = None
        self.sgf_path = None
        self.total_moves = 0
        
        # New: Robust mark management (not relying strictly on SGF properties during session)
        # { move_index: {"SQ": set(), "TR": set(), "MA": set()} }
        self.marks_data = {} 

    def new_game(self, board_size=19):
        self.board_size = board_size
        self.sgf_game = sgf.Sgf_game(size=board_size)
        self.sgf_path = None
        self.total_moves = 0
        self.moves = []
        self.marks_data = {0: {"SQ": set(), "TR": set(), "MA": set()}}
        logger.info(f"New {board_size}x{board_size} game initialized.", layer="CORE")

    def load_sgf(self, path):
        self.sgf_path = path
        try:
            with open(path, "rb") as f:
                content = f.read()
                self.sgf_game = sgf.Sgf_game.from_bytes(content)
            self.board_size = self.sgf_game.get_size()
            self._update_total_moves()
            self._import_marks_from_sgf()
            self.moves = []
        except Exception as e:
            logger.error(f"Failed to load SGF: {e}", layer="CORE")
            raise e

    def get_metadata(self):
        """SGFのルートノードから対局者名やコミなどのメタデータを取得する"""
        if not self.sgf_game:
            return {}
        root = self.sgf_game.get_root()
        metadata = {}
        for key in ["PB", "PW", "KM", "RE", "DT", "EV"]:
            if root.has_property(key):
                metadata[key] = root.get(key)
        return metadata

    def _import_marks_from_sgf(self):
        """Extract marks from the SGF tree into our dictionary."""
        self.marks_data = {}
        node = self.sgf_game.get_root()
        idx = 0
        while True:
            self.marks_data[idx] = {
                "SQ": set(node.get("SQ")) if node.has_property("SQ") else set(),
                "TR": set(node.get("TR")) if node.has_property("TR") else set(),
                "MA": set(node.get("MA")) if node.has_property("MA") else set(),
            }
            try:
                node = node[0]
                idx += 1
            except (IndexError, KeyError):
                break

    def _update_total_moves(self):
        if not self.sgf_game: return
        node = self.sgf_game.get_root()
        count = 0
        while True:
            try:
                node = node[0]
                count += 1
            except (IndexError, KeyError):
                break
        self.total_moves = count

    def toggle_mark(self, move_idx, row, col, mark_type):
        """Robust mark toggling using local dictionary."""
        prop = {"square": "SQ", "triangle": "TR", "cross": "MA"}.get(mark_type)
        if not prop: return False
        
        if move_idx not in self.marks_data:
            self.marks_data[move_idx] = {"SQ": set(), "TR": set(), "MA": set()}
            
        current_set = self.marks_data[move_idx][prop]
        point = (row, col)
        
        if point in current_set:
            current_set.remove(point)
            logger.debug(f"Removed {mark_type} at {point} (local)", layer="CORE")
        else:
            current_set.add(point)
            logger.debug(f"Added {mark_type} at {point} (local)", layer="CORE")
        return True

    def get_marks_at(self, move_idx):
        """Get marks for the given move index from local dictionary."""
        return self.marks_data.get(move_idx, {"SQ": set(), "TR": set(), "MA": set()})

    def add_move(self, move_idx, color, row, col):
        # 1. 合法手チェック (自殺手、コウなど)
        if row is not None and col is not None:
            curr_board = self.get_board_at(move_idx)
            if not curr_board.is_legal(Point(row, col), color):
                logger.warning(f"Illegal move rejected: {color}[{row},{col}]", layer="CORE")
                return False

        # 2. 指定された手数まで移動
        node = self.sgf_game.get_root()
        for _ in range(move_idx):
            try:
                node = node[0]
            except:
                break
        
        # 2. もし既存の子ノード（次の一手）がある場合は、それを削除して上書きする
        while len(node) > 0:
            node[0].delete()
            
        # 3. 新しい着手ノードを作成
        new_node = node.new_child(0)
        c_val = color.value if hasattr(color, 'value') else color.lower()
        if row is None or col is None:
            new_node.set_move(c_val, None)
        else:
            new_node.set_move(c_val, (row, col))
        
        # 4. 全手数を更新
        self._update_total_moves()
        self.marks_data[self.total_moves] = {"SQ": set(), "TR": set(), "MA": set()}
        logger.debug(f"Added move at {move_idx}. New total_moves: {self.total_moves}", layer="CORE")
        return True

    def remove_last_move(self) -> bool:
        """最新の着手（末尾ノード）を削除する"""
        if self.total_moves == 0:
            return False
            
        node = self.sgf_game.get_root()
        # 末尾の親ノードまで移動
        for _ in range(self.total_moves - 1):
            try: node = node[0]
            except: return False
            
        # 子ノード（最新手）を削除
        if len(node) > 0:
            node.delete()
            self._update_total_moves()
            # マークデータも削除
            if (self.total_moves + 1) in self.marks_data:
                del self.marks_data[self.total_moves + 1]
            return True
        return False

    def get_history_up_to(self, move_idx):
        if not self.sgf_game: return []
        history = []
        node = self.sgf_game.get_root()
        for _ in range(move_idx):
            try:
                node = node[0]
                color, move = node.get_move()
                if color:
                    c_str = "B" if color == 'b' else "W"
                    if move:
                        col_s = "ABCDEFGHJKLMNOPQRST"[move[1]]
                        row_s = str(move[0] + 1)
                        history.append([c_str, col_s + row_s])
                    else:
                        history.append([c_str, "pass"])
            except: break
        return history

    def get_board_at(self, move_idx) -> GameBoard:
        b = GameBoard(self.board_size)
        node = self.sgf_game.get_root()
        for i in range(move_idx):
            try:
                node = node[0]
                color, move = node.get_move()
                if color:
                    color_obj = Color.from_str(color)
                    if move:
                        pt = Point(move[0], move[1])
                        # SGFの着手なので基本は合法のはずだが、エラー時はログを出す
                        if not b.is_legal(pt, color_obj):
                            sys.stderr.write(f"[CORE] Replay Warning: Move {i} ({color_obj.label}{pt.to_gtp()}) is illegal according to current state.\n")
                        b.play(pt, color_obj)
                    else:
                        b.apply_pass()
            except Exception as e:
                sys.stderr.write(f"[CORE] Replay Error at move {i}: {e}\n")
                break
        return b

    def calculate_mistakes(self):
        if not self.moves or len(self.moves) < 2: 
            return [], []
        
        mb, mw = [], []
        # インデックス範囲を moves の長さに厳密に合わせる
        max_idx = len(self.moves)
        for i in range(1, max_idx):
            try:
                prev, curr = self.moves[i-1], self.moves[i]
                if prev is None or curr is None:
                    continue # まだ解析が終わっていない手はスキップ
                
                wr_before = prev.get('winrate', prev.get('winrate_black', 0.5))
                wr_after = curr.get('winrate', curr.get('winrate_black', 0.5))
                sc_before = prev.get('score', prev.get('score_lead_black', 0.0))
                sc_after = curr.get('score', curr.get('score_lead_black', 0.0))
                
                if (i % 2 != 0): # Black
                    mb.append((sc_before - sc_after, wr_before - wr_after, i))
                else: # White
                    mw.append((sc_before - sc_after, wr_before - wr_after, i))
            except (IndexError, KeyError):
                continue
                
        mb.sort(key=lambda x: x[1], reverse=True)
        mw.sort(key=lambda x: x[1], reverse=True)
        return mb[:3], mw[:3]
