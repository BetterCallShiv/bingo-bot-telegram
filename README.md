# 🎰 Bingo Bot - Telegram Multiplayer Bingo

A fun and interactive Telegram bot that brings the classic game of Bingo to Telegram.

---

## 🚀 Key Features

- **Two Grid Sizes**: Play classic **5x5** or the new larger **6x6 Pro Mode**
- **Custom Cards**: Let the bot generate a random grid or submit your own unique numbers (25 for 5x5 or 36 for 6x6).
- **Rematch System**: Easily start a new game with the previous players in one click now even smoother in groups!
- **Exit Feature**: Users can leave any active game themselves via the 🚪 button or the `/exit` command.
- **Admin Controls**: Includes a `/kick` command for hosts to remove inactive players.
- **Real-time Sync**: Group announcements and live updates for every picked number.

---

## 🕹️ How it Works

1. **Start a Lobby:** Use `/play` for 5x5 or `/play 6` for 6x6 in a group to open a new game lobby.
2. **Join the Game:** Players click the "Join" button in the group. The bot privately sends them their unique Bingo card.
3. **Play:** Players take turns selecting numbers. The bot automatically marks all players' cards and announces picks in the group.
4. **Win:** The bot verifies when a player hits "BINGO" (5 lines) or "BINGOO" (6 lines) and declares the winner!

---

## 🛠️ Setup

### 1. Requirements
* Python 3.8+
* `requirements.txt` dependencies

### 2. Configuration
Create a `.env` file in the root directory with the following variables:
```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

### 3. Install & Run
```bash
pip install -r requirements.txt
python bot.py
```

---

## 🎮 Commands

| Command | Description |
| :--- | :--- |
| `/start` | Start interacting with the bot and view the welcome message. |
| `/play` | Start a classic 5x5 Bingo lobby. |
| `/play 6` | Start a 6x6 Pro Mode Bingo lobby. |
| `/exit` | Leave your current active Bingo game. |
| `/kick` | Remove a player (Host only. Reply to the player's message). |
| `/help` | Detailed rules and how-to-play guide. |
| `/about` | View bot credits and source information. |

---

## 👨‍💻 Author

**Shivam Raj** ([@BetterCallShiv](https://github.com/BetterCallShiv))
- Email: [bettercallshiv@gmail.com](mailto:bettercallshiv@gmail.com)
- GitHub: [github.com/BetterCallShiv](https://github.com/BetterCallShiv)

