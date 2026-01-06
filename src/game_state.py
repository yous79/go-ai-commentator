from sgfmill import sgf, boards

class GoGameState:
    def __init__(self):
        self.board_size = 19
        self.moves = [] # List of {"move_number", "winrate", "score", "candidates", ...}
        self.sgf_game = None
        self.sgf_path = None
        self.total_moves = 0
    
    def load_sgf(self, path):
        self.sgf_path = path
        with open(path, "rb") as f:
            self.sgf_game = sgf.Sgf_game.from_bytes(f.read())
        self.board_size = self.sgf_game.get_size()
        
        # Calculate total moves
        node = self.sgf_game.get_root()
        count = 0
        while True:
            try:
                node = node[0]
                count += 1
            except IndexError:
                break
        self.total_moves = count
        self.moves = [] # Clear analysis data

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
        
        for i in range(1, len(self.moves)):
            prev = self.moves[i-1]
            curr = self.moves[i]
            
            # Winrate drop calculation (perspective of Black)
            # prev['winrate'] is at end of move i-1.
            # curr['winrate'] is at end of move i.
            
            # If move i was Black:
            # Drop = (Winrate before move i) - (Winrate after move i)
            # If move i was White:
            # Drop = (Winrate for White before move i) - (Winrate for White after move i)
            #      = (1.0 - prev_black_wr) - (1.0 - curr_black_wr)
            #      = curr_black_wr - prev_black_wr (Wait, this is gain for Black)
            
            # Let's standardize: "How much did the current player hurt their own winrate?"
            
            wr_prev = prev.get('winrate', 0.5)
            wr_curr = curr.get('winrate', 0.5)
            
            is_black_turn = (i % 2 != 0) # Move 1 is Black
            
            if is_black_turn:
                # Black played. Did Black's winrate drop?
                drop = wr_prev - wr_curr
                if drop > 0.05: # Threshold 5%
                    mistakes_b.append((drop, i))
            else:
                # White played. Did White's winrate drop? (i.e., Did Black's winrate rise?)
                # White's WR before: 1.0 - wr_prev
                # White's WR after:  1.0 - wr_curr
                drop = (1.0 - wr_prev) - (1.0 - wr_curr)
                if drop > 0.05:
                    mistakes_w.append((drop, i))
                    
        mistakes_b.sort(key=lambda x: x[0], reverse=True)
        mistakes_w.sort(key=lambda x: x[0], reverse=True)
        return mistakes_b[:3], mistakes_w[:3]
