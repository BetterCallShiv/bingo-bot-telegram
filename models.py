# Author: Shivam Raj (@BetterCallShiv)

import random
import time
import logging
from utils import generate_card_data, check_win_condition
logger = logging.getLogger(__name__)
SESSION_TTL_SECONDS = 7200


class BingoCard:
    def __init__(self, user_id, user_name, custom_data=None, grid_size=5):
        self.user_id = user_id
        self.user_name = user_name
        self.grid_size = grid_size
        self.data = custom_data if custom_data else generate_card_data(self.grid_size)
        self.marked = set()
        self.last_card_msg_id = None
        self.match_log_msg_id = None

    def toggle_mark(self, row, col):
        if (row, col) in self.marked:
            self.marked.remove((row, col))
        else:
            self.marked.add((row, col))

    def is_win(self):
        count, patterns = check_win_condition(self.data, self.marked, self.grid_size)
        return count >= self.grid_size, count, patterns
    

class GameSession:
    def __init__(self, session_id, grid_size=5, group_chat_id=None):
        self.session_id = session_id
        self.grid_size = grid_size
        self.group_chat_id = group_chat_id
        self.players = {}
        self.player_order = []
        self.current_turn_index = 0
        self.called_numbers = set()
        self.available_numbers = list(range(1, (self.grid_size * self.grid_size) + 1))
        self.game_started = False
        self.game_over = False
        self.lobby_header_id = None
        self.inline_message_id = None
        self.admin_id = None
        self.winners = []
        self.picks = {}
        self.user_names = {}
        self.last_activity = time.time()

    def touch(self):
        self.last_activity = time.time()

    def add_player(self, user_id, user_name):
        self.user_names[user_id] = user_name
        if user_id not in self.players:
            self.player_order.append(user_id)
            self.players[user_id] = None 
            return True
        return False

    def kick_player(self, user_id):
        if user_id not in self.players:
            return False
        self.players.pop(user_id)
        if user_id in self.player_order:
            idx = self.player_order.index(user_id)
            self.player_order.remove(user_id)
            if self.player_order:
                if self.current_turn_index >= len(self.player_order):
                    self.current_turn_index = 0
                elif idx < self.current_turn_index:
                    self.current_turn_index -= 1
            else:
                self.current_turn_index = 0
        return True

    def get_current_player_id(self):
        if not self.player_order:
            return None
        return self.player_order[self.current_turn_index]

    def next_turn(self):
        if not self.player_order:
            return
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_order)

    def draw_number(self, num, picker_id=None):
        if num in self.available_numbers:
            self.available_numbers.remove(num)
            self.called_numbers.add(num)
            if picker_id:
                if picker_id not in self.picks:
                    self.picks[picker_id] = []
                self.picks[picker_id].append(num)
            for player in self.players.values():
                if player is None: continue
                for r in range(self.grid_size):
                    for c in range(self.grid_size):
                        if player.data[r][c] == num:
                            player.marked.add((r, c))
            return True
        return False

    def reset(self):
        self.called_numbers = set()
        self.available_numbers = list(range(1, (self.grid_size * self.grid_size) + 1))
        self.players = {}
        self.player_order = []
        self.current_turn_index = 0
        self.game_started = False
        self.game_over = False
        self.lobby_header_id = None
        self.inline_message_id = None
        self.admin_id = None
        self.winners = []
        self.picks = {}
        self.user_names = {}
        self.last_activity = time.time()


class GameManager:
    def __init__(self):
        self.sessions = {}

    def get_session(self, session_id, grid_size=5, group_chat_id=None):
        if session_id not in self.sessions:
            self.sessions[session_id] = GameSession(session_id, grid_size=grid_size, group_chat_id=group_chat_id)
        session = self.sessions[session_id]
        session.touch()
        return session

    def get_sessions_for_group(self, chat_id):
        return [(sid, s) for sid, s in self.sessions.items() if s.group_chat_id == chat_id]

    def remove_session(self, session_id):
        if session_id in self.sessions:
            self.sessions.pop(session_id, None)

    def cleanup_old_sessions(self):
        now = time.time()
        stale = [
            sid for sid, s in self.sessions.items()
            if (now - s.last_activity) > SESSION_TTL_SECONDS
        ]
        for sid in stale:
            self.sessions.pop(sid, None)
            logger.info(f"Cleaned up stale session: {sid}")
        if stale:
            logger.info(f"Session cleanup: removed {len(stale)} stale session(s). Active: {len(self.sessions)}")
