# 🎰 Bingo Bot - Telegram Multiplayer Bingo

A fun and interactive Telegram bot that brings the classic game of Bingo to Telegram.

---

## 🚀 Key Features

- **Dual Mode**: Play seamlessly in group chats or private messages.
- **Custom Cards**: Let the bot generate a random grid for you or submit your own custom 25-number grid.
- **Rematch System**: Easily start a new game with the previous lobby's players in just one click.
- **Admin Controls**: Includes a `/kick` command for hosts to easily remove inactive players.
- **Real-time Sync**: Group announcements and live updates for every picked number.

---

## 🕹️ How it Works

1. **Start a Lobby:** Use `/play` in a group to open a new game lobby.
2. **Join the Game:** Players click the "Join" button in the group. The bot privately sends them their unique Bingo card or let you generate a custom one.
3. **Play:** Players take turns selecting numbers. The bot automatically updates everyone's cards and announces the picks in the group.
4. **Win:** The bot automatically verifies when a player hits "BINGO" and declares the winner!

---

## 🛠️ Installation

### 1. Requirements
* Python 3.8+
* `requirements.txt` dependencies

### 2. Setup

**Clone the repository:**
```bash
git clone https://github.com/BetterCallShiv/bingo-bot-telegram.git
cd bingo-bot-telegram
```

**Configuration:** Create a `.env` file in the root directory with the following variables:
```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

**Install & Run:**
```bash
pip install -r requirements.txt
python bot.py
```

---

## 🎮 Commands

| Command | Description |
| :--- | :--- |
| `/play` | Start a new Bingo lobby in a group. |
| `/restart` | Clear the current game and reset the lobby. |
| `/kick` | Remove a player (Host only. Reply to the player's message). |
| `/help` | Detailed rules and how-to-play guide. |
| `/about` | View bot credits and source information. |

---

## 👨‍💻 Author

**Shivam Raj** ([@BetterCallShiv](https://github.com/BetterCallShiv))
- Email: [bettercallshiv@gmail.com](mailto:bettercallshiv@gmail.com)
- GitHub: [github.com/BetterCallShiv](https://github.com/BetterCallShiv)

