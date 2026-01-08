from sgfmill import sgf, boards

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
        print(f"DEBUG: New {board_size}x{board_size} game initialized.")

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
            print(f"DEBUG ERROR in load_sgf: {e}")
            raise e

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
            print(f"DEBUG: Removed {mark_type} at {point} (local)")
        else:
            current_set.add(point)
            print(f"DEBUG: Added {mark_type} at {point} (local)")
        return True

    def get_marks_at(self, move_idx):
        """Get marks for the given move index from local dictionary."""
        return self.marks_data.get(move_idx, {"SQ": set(), "TR": set(), "MA": set()})

    def add_move(self, move_idx, color, row, col):
        node = self.sgf_game.get_root()
        for _ in range(move_idx):
            try: node = node[0]
            except: break
        
        new_node = node.new_child(0)
        if row is None or col is None:
            new_node.set_move(color.lower(), None)
        else:
            new_node.set_move(color.lower(), (row, col))
        
        self._update_total_moves()
        # Initialize mark entry for the new move (inherited from prev move if desired, but here we start fresh)
        self.marks_data[move_idx + 1] = {"SQ": set(), "TR": set(), "MA": set()}
        return True

    def get_history_up_to(self, move_idx):
        if not self.sgf_game: return []
        history = []
        node = self.sgf_game.get_root()
        for _ in range(move_idx):
            try:
                node = node[0]
                color, move = node.get_move()
                if color:
                    if move:
                        col_s = "ABCDEFGHJKLMNOPQRST"[move[1]]
                        row_s = str(move[0] + 1)
                        history.append(["B" if color == 'b' else "W", col_s + row_s])
                    else:
                        history.append(["B" if color == 'b' else "W", "pass"])
            except: break
        return history

    def get_board_at(self, move_idx):
        b = boards.Board(self.board_size)
        node = self.sgf_game.get_root()
        for _ in range(move_idx):
            try:
                node = node[0]
                color, move = node.get_move()
                if color and move: b.play(move[0], move[1], color)
            except: break
        return b

    def calculate_mistakes(self):
        if not self.moves or len(self.moves) < 2: return [], []
        mb, mw = [], []
        for i in range(1, len(self.moves)):
            prev, curr = self.moves[i-1], self.moves[i]
            wr_before, wr_after = prev.get('winrate', 0.5), curr.get('winrate', 0.5)
            sc_before, sc_after = prev.get('score', 0.0), curr.get('score', 0.0)
            if (i % 2 != 0): # Black
                mb.append((sc_before - (-sc_after), wr_before - (1.0 - wr_after), i))
            else: # White
                mw.append((sc_before - (-sc_after), wr_before - (1.0 - wr_after), i))
        mb.sort(key=lambda x: x[1], reverse=True)
        mw.sort(key=lambda x: x[1], reverse=True)
        return mb[:3], mw[:3]
