from sgfmill import sgf, boards

class GoGameState:
    def __init__(self):
        self.board_size = 19
        self.moves = [] # List of {"move_number", "winrate", "score", "candidates", ...}
        self.sgf_game = None
        self.sgf_path = None
        self.total_moves = 0
    
    def new_game(self, board_size=19):
        """Initialize a new empty game with the given board size."""
        self.board_size = board_size
        self.sgf_game = sgf.Sgf_game(size=board_size)
        self.sgf_path = None
        self.total_moves = 0
        self.moves = []
        print(f"DEBUG: New {board_size}x{board_size} game initialized.")

    def load_sgf(self, path):
        print(f"DEBUG: Attempting to load SGF: {path}")
        self.sgf_path = path
        try:
            with open(path, "rb") as f:
                content = f.read()
                print(f"DEBUG: File read successful, size: {len(content)} bytes")
                self.sgf_game = sgf.Sgf_game.from_bytes(content)
            
            self.board_size = self.sgf_game.get_size()
            print(f"DEBUG: Board size detected: {self.board_size}")
            
            self._update_total_moves()
            self.moves = [] # Clear analysis data
            print("DEBUG: SGF loading completed successfully.")
        except Exception as e:
            print(f"DEBUG ERROR in load_sgf: {e}")
            raise e

    def _update_total_moves(self):
        # Calculate total moves in the main branch
        node = self.sgf_game.get_root()
        count = 0
        while True:
            try:
                node = node[0]
                count += 1
            except IndexError:
                break
        self.total_moves = count

    def add_move(self, move_idx, color, row, col):
        """Add a move to the SGF at move_idx. If col is None, it's a pass."""
        if not self.sgf_game:
            return False
        
        # Traverse to the node at move_idx
        node = self.sgf_game.get_root()
        count = 0
        while count < move_idx:
            try:
                node = node[0]
                count += 1
            except IndexError:
                # If we can't reach move_idx, we can't add a move here
                return False
        
        # Add new node as the FIRST child of the current node
        # By using pos=0, this new move becomes the 'main' branch for subsequent 
        # calls to node[0], allowing the UI to follow this variation.
        new_node = node.new_child(0)
        if row is None or col is None:
            new_node.set_move(color.lower(), None)
        else:
            new_node.set_move(color.lower(), (row, col))
        
        self._update_total_moves()
        return True

    def get_history_up_to(self, move_idx):
        if not self.sgf_game:
            return []
        
        history = []
        node = self.sgf_game.get_root()
        # Initial position (if any) handling omitted for simplicity as typical SGF starts empty or with handicap
        
        count = 0
        while count < move_idx:
            try:
                node = node[0]
                count += 1
                color, move = node.get_move()
                if color:
                    if move:
                        col_s = "ABCDEFGHJKLMNOPQRST"[move[1]]
                        row_s = str(move[0] + 1)
                        history.append(["B" if color == 'b' else "W", col_s + row_s])
                    else:
                        history.append(["B" if color == 'b' else "W", "pass"])
            except IndexError:
                break
        return history

    def get_board_at(self, move_idx):
        if not self.sgf_game:
            return boards.Board(19)
            
        b = boards.Board(self.board_size)
        node = self.sgf_game.get_root()
        count = 0
        while count < move_idx:
            try:
                node = node[0]
                count += 1
                color, move = node.get_move()
                if color and move:
                    b.play(move[0], move[1], color)
            except IndexError:
                break
        return b

    def calculate_mistakes(self):
        if not self.moves or len(self.moves) < 2:
            return [], []
            
        mistakes_b = []
        mistakes_w = []
        
        # moves[i] is the analysis result AFTER move i has been played.
        # moves[i]['winrate'] is the winrate for the NEXT player.
        # moves[i]['score'] is the score lead for the NEXT player.

        for i in range(1, len(self.moves)):
            prev_data = self.moves[i-1]
            curr_data = self.moves[i]
            
            # The player who just played move 'i'
            is_black_just_played = (i % 2 != 0)
            
            wr_before = prev_data.get('winrate', 0.5)
            wr_after = curr_data.get('winrate', 0.5)
            
            sc_before = prev_data.get('score', 0.0)
            sc_after = curr_data.get('score', 0.0)
            
            if is_black_just_played:
                # Black played.
                wr_drop = wr_before - (1.0 - wr_after)
                # Score Lead: + is good for next player.
                # If Black played, sc_before was Black's lead.
                # sc_after is White's lead.
                sc_drop = sc_before - (-sc_after) 
                mistakes_b.append((sc_drop, wr_drop, i))
            else:
                # White played.
                wr_drop = wr_before - (1.0 - wr_after)
                sc_drop = sc_before - (-sc_after)
                mistakes_w.append((sc_drop, wr_drop, i))
                    
        # Sort by winrate drop amount (largest drop first) as requested
        # Each element is (score_drop, winrate_drop, move_number)
        mistakes_b.sort(key=lambda x: x[1], reverse=True)
        mistakes_w.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 3
        return mistakes_b[:3], mistakes_w[:3]
