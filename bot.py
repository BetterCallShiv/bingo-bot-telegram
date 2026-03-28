# Author: Shivam Raj (@BetterCallShiv)

import os
import random
import logging
import asyncio
import signal
import string
from dotenv import load_dotenv
from pyrogram.errors import FloodWait
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, BotCommand
from models import GameManager, BingoCard, GameSession
from utils import format_cell_text, parse_custom_grid

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Please set API_ID, API_HASH, and BOT_TOKEN in your .env file.")
    exit(1)
app = Client("BCS-Bingo-Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
gm = GameManager()
BOT_USERNAME = None
_processing_callbacks: set = set()


def generate_session_id():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))


def format_grid_log(grid):
    return "\n" + "\n".join([" | ".join([f"{n:2}" for n in row]) for row in grid])


async def _api_call_with_retry(coro_fn, context=""):
    for attempt in range(2):
        try:
            return await coro_fn()
        except FloodWait as fw:
            if attempt == 0:
                logger.warning(f"[{context}] FloodWait {fw.value}s — retrying after sleep.")
                await asyncio.sleep(fw.value)
            else:
                logger.warning(f"[{context}] Still rate-limited after retry, giving up.")
        except Exception as e:
            logger.warning(f"[{context}] Error: {e}")
            break


async def broadcast_to_lobby(session_id, text, markup=None):
    session = gm.get_session(session_id)
    if str(session_id).replace("-", "").isdigit():
        if session.lobby_header_id:
            await _api_call_with_retry(
                lambda: app.edit_message_text(int(session_id), session.lobby_header_id, text=text, reply_markup=markup),
                f"broadcast_to_lobby/group/{session_id}"
            )
    elif session.inline_message_id:
        await _api_call_with_retry(
            lambda: app.edit_inline_text(session.inline_message_id, text, reply_markup=markup),
            f"broadcast_to_lobby/inline/{session.inline_message_id}"
        )


async def refresh_lobby_markup(session_id):
    session = gm.get_session(session_id)
    text = get_lobby_text(session_id)
    markup = get_lobby_markup(session_id)
    players_count = len(session.player_order)
    logger.info(f"[refresh_lobby_markup] Session {session_id} has {players_count} players.")
    if str(session_id).replace("-", "").isdigit():
        if session.lobby_header_id:
            await _api_call_with_retry(
                lambda: app.edit_message_text(int(session_id), session.lobby_header_id, text=text, reply_markup=markup),
                f"refresh_lobby_markup/group/{session_id}"
            )
    elif session.inline_message_id:
        await _api_call_with_retry(
            lambda: app.edit_inline_text(session.inline_message_id, text=text, reply_markup=markup),
            f"refresh_lobby_markup/inline/{session.inline_message_id}"
        )


async def broadcast_to_players(session_id, text, update_cards=True):
    session = gm.get_session(session_id)
    for uid in session.player_order:
        player = session.players.get(uid)
        if not player or not player.last_card_msg_id:
            continue
        if update_cards:
            new_text = get_card_text(session_id, uid)
            new_markup = get_card_markup(session_id, uid)
            await _api_call_with_retry(
                lambda u=uid, mid=player.last_card_msg_id, t=new_text, m=new_markup: 
                    app.edit_message_text(u, mid, text=t, reply_markup=m),
                f"broadcast_to_players/edit_card/{uid}"
            )
            if player.match_log_msg_id:
                log_text = get_match_log_text(session_id)
                await _api_call_with_retry(
                    lambda u=uid, mid=player.match_log_msg_id, t=log_text:
                        app.edit_message_text(u, mid, text=t),
                    f"broadcast_to_players/edit_log/{uid}"
                )
        elif text:
            await _api_call_with_retry(
                lambda u=uid: app.send_message(u, text, disable_notification=True),
                f"broadcast_to_players/msg/{uid}"
            )
            new_text = get_card_text(session_id, uid)
            new_markup = get_card_markup(session_id, uid)
            await _api_call_with_retry(
                lambda u=uid, mid=player.last_card_msg_id, t=new_text, m=new_markup: 
                    app.edit_message_text(u, mid, text=t, reply_markup=m),
                f"broadcast_to_players/edit_card/{uid}"
            )
            if player.match_log_msg_id:
                log_text = get_match_log_text(session_id)
                await _api_call_with_retry(
                    lambda u=uid, mid=player.match_log_msg_id, t=log_text:
                        app.edit_message_text(u, mid, text=t),
                    f"broadcast_to_players/edit_log/{uid}"
                )


def get_match_log_text(session_id):
    session = gm.get_session(session_id)
    if not session.picks:
        return "📝 **Match Log:** No numbers picked yet."
    log_text = "📝 **Match Log:**\n"
    for uid in session.player_order:
        nums = session.picks.get(uid, [])
        p_name = session.players[uid].user_name
        nums_str = ", ".join(map(str, nums)) if nums else "-"
        log_text += f"• {p_name}: {nums_str}\n"
    return log_text


def get_card_text(session_id, user_id):
    session = gm.get_session(session_id)
    player = session.players.get(user_id)
    if not session.game_started and not session.game_over:
        return "✅ **Random card generated!** Wait for the admin to start the game."
    if session.game_over:
        is_win, count, _ = player.is_win()
        winners_names = ", ".join([f"**{w}**" for w in session.winners])
        if is_win:
            return f"🎊 **BINGO! YOU WON!** 🎊"
        if session.winners:
            return f"🏁 **Game Over!**\n🏆 Winner: {winners_names}"
        return "🏁 **Game Over!** It's a draw."
    curr_id = session.get_current_player_id()
    curr_player_card = session.players.get(curr_id) if curr_id else None
    curr_name = curr_player_card.user_name if curr_player_card else "..."
    if curr_id == user_id:
        status_line = "👉 **Your turn!** Pick a number from your card."
    else:
        status_line = f"⏳ Turn: **{curr_name}** is picking."
    return f"🚀 **Game Started!**\nWin: Complete 5 lines (B-I-N-G-O)\n{status_line}"


def get_lobby_markup(session_id):
    session = gm.get_session(session_id)
    is_group = str(session_id).replace("-", "").isdigit()
    players_count = len(session.player_order)
    admin_suffix = f"_a{session.admin_id}" if session.admin_id else ""
    join_url = f"https://t.me/{BOT_USERNAME}?start=join_{session_id}{admin_suffix}"
    btn_text = f"🎟 Join & Play in PM ({players_count})" if is_group else "🎟 Join & Play in PM"
    keyboard = [[InlineKeyboardButton(btn_text, url=join_url)]]
    if is_group:
        keyboard.append([
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_lobby:{session_id}"),
            InlineKeyboardButton("🚀 Start Game", callback_data=f"start_game:{session_id}")
        ])
    else:
        keyboard.append([InlineKeyboardButton("🚀 Start Game", callback_data=f"start_game:{session_id}")])
    return InlineKeyboardMarkup(keyboard)


def get_card_choice_markup(session_id):
    keyboard = [
        [InlineKeyboardButton("🎲 Random Card", callback_data=f"choice:random:{session_id}"),
         InlineKeyboardButton("✍️ Custom Card", callback_data=f"choice:custom:{session_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_picker_markup(session_id):
    session = gm.get_session(session_id)
    keyboard = []
    all_nums = list(range(1, 26))
    for i in range(0, 25, 5):
        row = []
        for n in all_nums[i:i+5]:
            if n in session.called_numbers:
                row.append(InlineKeyboardButton("✖️", callback_data="none"))
            else:
                row.append(InlineKeyboardButton(str(n), callback_data=f"pick:{session_id}:{n}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back to Card", callback_data=f"back_to_card:{session_id}")])
    return InlineKeyboardMarkup(keyboard)


def get_card_markup(session_id, user_id):
    session = gm.get_session(session_id)
    player = session.players.get(user_id)
    if not player: return None
    keyboard = []
    for r in range(5):
        row_buttons = []
        for c in range(5):
            val = player.data[r][c]
            is_marked = (r, c) in player.marked
            btn_text = format_cell_text(val, is_marked)
            row_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"cell:{session_id}:{user_id}:{r}:{c}"))
        keyboard.append(row_buttons)
    _, line_count, _ = player.is_win()
    bingo_letters = list("BINGO")
    progress_str = " ".join([f"{bingo_letters[i]}" if i < line_count else " _ " for i in range(5)])
    keyboard.append([InlineKeyboardButton(f"{progress_str}", callback_data="none")])
    if not session.game_started and not session.game_over:
        status_btn = InlineKeyboardButton("🚀 Start Game", callback_data=f"start_game:{session_id}")
    elif session.game_over:
        status_btn = InlineKeyboardButton("🏁 Game Over", callback_data="none")
    else:
        curr_player_id = session.get_current_player_id()
        if curr_player_id == user_id:
            status_btn = InlineKeyboardButton("🎯 YOUR TURN! Pick a Number", callback_data=f"show_picker:{session_id}")
        else:
            curr_name = session.players[curr_player_id].user_name if curr_player_id in session.players else "..."
            status_btn = InlineKeyboardButton(f"⏳ Waiting for {curr_name}...", callback_data="none")
    keyboard.append([status_btn])
    if not session.game_over:
        keyboard.append([InlineKeyboardButton("🏆 Bingo!", callback_data=f"bingo:{session_id}:{user_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🔁 Rematch!", callback_data=f"rematch:{session_id}")])
    return InlineKeyboardMarkup(keyboard)


def get_lobby_text(session_id):
    session = gm.get_session(session_id)
    text = "📢 **Bingo Lobby Open!**\nClick the button below to join and play in PM."
    if session.player_order:
        names = []
        for uid in session.player_order:
            p_name = session.user_names.get(uid, f"User {uid}")
            names.append(p_name)
        text += f"\n\n✅ **Joined:** {', '.join(names)}"
    return text


async def handle_game_pick(session_id, num, picker_id):
    session = gm.get_session(session_id)
    if session.game_over:
        return False
    picker_card = session.players.get(picker_id)
    picker_name = picker_card.user_name if picker_card else "..."
    if session.draw_number(num, picker_id=picker_id):
        session.next_turn()
        curr_id = session.get_current_player_id()
        curr_player_card = session.players.get(curr_id) if curr_id else None
        curr_name = curr_player_card.user_name if curr_player_card else "..."
        announcement = f"🎱 **{picker_name}** picked number: **{num}**\nNext turn: **{curr_name}**"
        await broadcast_to_lobby(session_id, announcement, markup=get_lobby_markup(session_id))
        winners = []
        for uid in session.player_order:
            player = session.players.get(uid)
            if not player:
                logger.warning(f"[handle_game_pick] Player {uid} has no card in session {session_id}, skipping.")
                continue
            is_win, count, patterns = player.is_win()
            if is_win:
                winners.append(player)
        if winners:
            session.game_over = True
            session.game_started = False
            if len(winners) > 1:
                win_msg = f"🤝 **TIE MATCH! (DRAW)** 🤝\n{', '.join(['**' + w.user_name + '**' for w in winners])} both hit BINGO!"
            else:
                win_msg = f"🏆 **BINGO!** 🏆\n**{winners[0].user_name}** won the game!"
            session.winners = [w.user_name for w in winners]
            await broadcast_to_lobby(session_id, win_msg)
            await broadcast_to_players(session_id, None, update_cards=True)
            logger.info(f"[Session {session_id}] Game over. Winner(s): {[w.user_name for w in winners]}")
        elif len(session.called_numbers) == 25:
            session.game_over = True
            session.game_started = False
            draw_msg = "🏁 **DRAW!** 🏁\nAll 25 numbers have been called. No one reached 5 lines!"
            await broadcast_to_lobby(session_id, draw_msg)
            await broadcast_to_players(session_id, None, update_cards=True)
        else:
            await broadcast_to_players(session_id, None, update_cards=True)
        return True
    return False


async def notify_lobby_setup(session_id, user_name, current_user_id):
    session = gm.get_session(session_id)
    new_text = get_lobby_text(session_id)
    markup = get_lobby_markup(session_id)
    if str(session_id).replace("-", "").isdigit():
        try:
            await app.edit_message_text(int(session_id), session.lobby_header_id, text=new_text, reply_markup=markup)
            await app.send_message(int(session_id), f"✅ **{user_name}** is ready!")
        except Exception as e:
            logger.warning(f"[notify_lobby_setup] Failed to update group lobby {session_id}: {e}")
    elif session.inline_message_id:
        try:
            await app.edit_inline_text(session.inline_message_id, text=new_text, reply_markup=markup)
        except Exception as e:
            logger.warning(f"[notify_lobby_setup] Failed to edit inline lobby: {e}")
    for uid in session.player_order:
        if uid != current_user_id:
            try:
                await app.send_message(uid, f"🔔 **{user_name}** has finished setting up their Bingo card!")
            except Exception as e:
                logger.warning(f"[notify_lobby_setup] Failed to message user {uid}: {e}")


@app.on_inline_query()
async def inline_handler(client, inline_query: InlineQuery):
    session_id = generate_session_id()
    session = gm.get_session(session_id)
    session.admin_id = inline_query.from_user.id
    results = [
        InlineQueryResultArticle(
            id=session_id,
            title="🎮 Start a Bingo Match!",
            description="Invite friends to a private Bingo game.",
            input_message_content=InputTextMessageContent(get_lobby_text(session_id)),
            reply_markup=get_lobby_markup(session_id)
        )
    ]
    await inline_query.answer(results, cache_time=1)


@app.on_chosen_inline_result()
async def chosen_result_handler(client, chosen_result: ChosenInlineResult):
    session_id = chosen_result.result_id
    session = gm.get_session(session_id)
    session.inline_message_id = chosen_result.inline_message_id
    logger.info(f"Inline session {session_id} confirmed by admin. Refreshing lobby...")
    await refresh_lobby_markup(session_id)


@app.on_message(filters.command("start"))
async def start_handler(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    if len(message.command) > 1 and message.command[1].startswith("join_"):
        parts = message.command[1].replace("join_", "").split("_a")
        session_id = parts[0]
        session = gm.get_session(session_id)
        if len(parts) > 1 and session.admin_id is None:
            session.admin_id = int(parts[1])
        if session.game_started or session.game_over:
            await message.reply_text("Sorry, this game is already started or finished!"); return
        if session.add_player(user_id, user_name):
            if session.admin_id is None:
                session.admin_id = user_id
            await refresh_lobby_markup(session_id)
            await message.reply_text(f"✅ You've joined the Bingo match!\n\n🎲 **How do you want your card?**", reply_markup=get_card_choice_markup(session_id))
        else:
            await message.reply_text("You're already in the lobby!")
        return
    await message.reply_text(f"Welcome to Bingo Bot! Use `@{BOT_USERNAME}` me in any chat to invite friends.")


@app.on_message(filters.command(["play"]) & filters.group)
async def play_handler(client, message):
    session_id = str(message.chat.id)
    session = gm.get_session(session_id)
    if session.game_started and not session.game_over:
        await message.reply_text("A game is already in progress! Use /restart to end it."); return
    session.reset()
    session.admin_id = message.from_user.id
    msg = await message.reply_text(get_lobby_text(session_id), reply_markup=get_lobby_markup(session_id))
    session.lobby_header_id = msg.id


@app.on_callback_query(filters.regex("^choice:"))
async def choice_callback(client, callback_query: CallbackQuery):
    _, ctype, session_id = callback_query.data.split(":")
    user_id, user_name = callback_query.from_user.id, callback_query.from_user.first_name
    session = gm.get_session(session_id)
    if ctype == "random":
        player = BingoCard(user_id, user_name)
        session.players[user_id] = player
        logger.info(f"User {user_name} ({user_id}) generated a RANDOM card for session {session_id}:{format_grid_log(player.data)}")
        await callback_query.edit_message_text(f"✅ Random card generated! Wait for the admin to start the game.")
        sent_msg = await app.send_message(user_id, "Preview of your private card:", reply_markup=get_card_markup(session_id, user_id))
        player.last_card_msg_id = sent_msg.id
        await notify_lobby_setup(session_id, user_name, user_id)
    else:
        await callback_query.edit_message_text(f"✍️ Send your 25 numbers now (1-25) in any order.\nExample: `1 2 3 ... 25`")


@app.on_message(filters.text & filters.private & ~filters.regex("^/"))
async def custom_grid_handler(client, message):
    grid = parse_custom_grid(message.text)
    user_id, user_name = message.from_user.id, message.from_user.first_name
    if not grid:
        await message.reply_text("❌ **Invalid Format!**\nPlease send exactly **25 unique numbers** (1-25).")
        return
    for session_id, session in gm.sessions.items():
        if user_id in session.players and session.players[user_id] is None:
            player = BingoCard(user_id, user_name, custom_data=grid)
            session.players[user_id] = player
            logger.info(f"User {user_name} ({user_id}) set a CUSTOM card for session {session_id}:{format_grid_log(player.data)}")
            await message.reply_text(f"✅ Custom card set! Preview below.")
            sent_msg = await app.send_message(user_id, "Your private card:", reply_markup=get_card_markup(session_id, user_id))
            player.last_card_msg_id = sent_msg.id
            await notify_lobby_setup(session_id, user_name, user_id)
            return


@app.on_callback_query(filters.regex("^start_game:"))
async def start_game_callback(client, callback_query: CallbackQuery):
    _, session_id = callback_query.data.split(":")
    session = gm.get_session(session_id)
    if session.admin_id and callback_query.from_user.id != session.admin_id:
        await callback_query.answer("⚠️ Only the room admin can start the match!", show_alert=True); return
    if session.game_started or session.game_over: return
    if len(session.player_order) < 2:
        await callback_query.answer("⚠️ Need at least 2 players to start!", show_alert=True); return
    for uid, card in session.players.items():
        if card is None:
            await callback_query.answer("Everyone hasn't finished setup yet!", show_alert=True); return
    session.game_started = True
    random.shuffle(session.player_order)
    curr_id = session.get_current_player_id()
    curr_name = session.players[curr_id].user_name
    msg_text = get_card_text(session_id, session.player_order[0])
    if callback_query.inline_message_id:
        try:
            await app.edit_inline_text(callback_query.inline_message_id, msg_text)
        except Exception as e:
            logger.warning(f"[start_game_callback] Failed to edit inline message: {e}")
    else:
        await callback_query.edit_message_text(msg_text)
    for uid in session.player_order:
        player = session.players.get(uid)
        if not player:
            continue
        try:
            p_text = get_card_text(session_id, uid)
            p_markup = get_card_markup(session_id, uid)
            if player.last_card_msg_id:
                await app.edit_message_text(uid, player.last_card_msg_id, text=p_text, reply_markup=p_markup)
            else:
                msg = await app.send_message(uid, p_text, reply_markup=p_markup)
                player.last_card_msg_id = msg.id
            log_msg = await app.send_message(uid, get_match_log_text(session_id))
            player.match_log_msg_id = log_msg.id
        except Exception as e:
            logger.warning(f"[start_game_callback] Failed to update card for player {uid}: {e}")


@app.on_callback_query(filters.regex("^show_picker:"))
async def show_picker_callback(client, callback_query: CallbackQuery):
    _, session_id = callback_query.data.split(":")
    session = gm.get_session(session_id)
    if not session.game_started or session.game_over: await callback_query.answer("Game inactive!", show_alert=True); return
    if session.get_current_player_id() != callback_query.from_user.id: await callback_query.answer("Not your turn!"); return
    await callback_query.edit_message_reply_markup(reply_markup=get_picker_markup(session_id))


@app.on_callback_query(filters.regex("^back_to_card:"))
async def back_to_card_callback(client, callback_query: CallbackQuery):
    _, session_id = callback_query.data.split(":")
    await callback_query.edit_message_reply_markup(reply_markup=get_card_markup(session_id, callback_query.from_user.id))


@app.on_callback_query(filters.regex("^pick:"))
async def pick_callback(client, callback_query: CallbackQuery):
    _, session_id, num = callback_query.data.split(":")
    session = gm.get_session(session_id)
    if not session.game_started or session.game_over: return
    if session.get_current_player_id() != callback_query.from_user.id:
        await callback_query.answer("Not your turn!"); return
    dedup_key = f"turn:{session_id}"
    if dedup_key in _processing_callbacks:
        await callback_query.answer("Processing…"); return
    _processing_callbacks.add(dedup_key)
    try:
        if not await handle_game_pick(session_id, int(num), callback_query.from_user.id):
            await callback_query.answer("Taken!")
    finally:
        _processing_callbacks.discard(dedup_key)


@app.on_callback_query(filters.regex("^cell:"))
async def cell_callback(client, callback_query: CallbackQuery):
    _, session_id, user_id, r, c = callback_query.data.split(":")
    session = gm.get_session(session_id)
    if session.game_over: await callback_query.answer("Game is finished!"); return
    if not session.game_started: await callback_query.answer("Wait for start!", show_alert=True); return
    player = session.players.get(int(user_id))
    if not player: return
    val = player.data[int(r)][int(c)]
    is_turn = (int(user_id) == callback_query.from_user.id and session.get_current_player_id() == int(user_id))
    if val not in session.called_numbers:
        if is_turn:
            dedup_key = f"turn:{session_id}"
            if dedup_key in _processing_callbacks:
                await callback_query.answer("Processing…"); return
            _processing_callbacks.add(dedup_key)
            try:
                await handle_game_pick(session_id, val, callback_query.from_user.id)
            finally:
                _processing_callbacks.discard(dedup_key)
        else:
            await callback_query.answer("Wait for your turn to pick numbers!", show_alert=True); return
    else:
        await callback_query.answer(f"{val} is already marked.")
    await callback_query.answer()


@app.on_callback_query(filters.regex("^bingo:"))
async def bingo_callback(client, callback_query: CallbackQuery):
    _, session_id, user_id = callback_query.data.split(":")
    session = gm.get_session(session_id)
    if not session.game_started or session.game_over: return
    player = session.players.get(int(user_id))
    is_win, count, patterns = player.is_win()
    if is_win:
        await callback_query.answer("You've won! Results announced.", show_alert=True)
    else:
        await callback_query.answer(f"You have {count}/5 lines.", show_alert=True)


@app.on_message(filters.command("kick") & filters.group)
async def kick_handler(client, message):
    session_id = str(message.chat.id)
    session = gm.get_session(session_id)
    if message.from_user.id != session.admin_id:
        await message.reply_text("⚠️ Only the game host can kick players!"); return
    if session.game_over:
        await message.reply_text("❌ The game is already over."); return
    if not (message.reply_to_message and message.reply_to_message.from_user):
        await message.reply_text("ℹ️ Reply to a player's message and use `/kick` to remove them."); return
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name
    if target_id == session.admin_id:
        await message.reply_text("😄 You can't kick yourself!"); return
    if target_id not in session.players:
        await message.reply_text(f"❌ {target_name} is not in the current game."); return
    session.kick_player(target_id)
    logger.info(f"[kick_handler] {target_name} ({target_id}) kicked from session {session_id}")
    await _api_call_with_retry(
        lambda: app.send_message(target_id, f"❌ You were kicked from the Bingo game in **{message.chat.title}**."),
        "kick_handler/notify_kicked"
    )
    kick_msg = f"👢 **{target_name}** has been removed from the game."
    await message.reply_text(kick_msg)
    await broadcast_to_players(session_id, kick_msg, update_cards=True)
    await refresh_lobby_markup(session_id)
    if session.game_started and len(session.player_order) < 2:
        session.game_over = True
        session.game_started = False
        end_msg = "⚠️ Not enough players to continue. Game ended!"
        await message.reply_text(end_msg)
        await broadcast_to_players(session_id, end_msg, update_cards=True)


@app.on_callback_query(filters.regex("^rematch:"))
async def rematch_callback(client, callback_query: CallbackQuery):
    _, session_id = callback_query.data.split(":")
    session = gm.get_session(session_id)
    if callback_query.from_user.id != session.admin_id:
        await callback_query.answer("⚠️ Only the host can start a rematch!", show_alert=True); return
    if not session.game_over:
        await callback_query.answer("The game isn't over yet!", show_alert=True); return
    prev_players = list(session.player_order)
    session.reset()
    session.admin_id = callback_query.from_user.id
    new_text = get_lobby_text(session_id)
    markup = get_lobby_markup(session_id)
    msg = None
    if str(session_id).replace("-", "").isdigit():
        msg = await _api_call_with_retry(
            lambda: app.send_message(int(session_id), f"🔁 **Rematch!**\n\n{new_text}", reply_markup=markup),
            "rematch_callback/lobby"
        )
        if msg:
            session.lobby_header_id = msg.id
    await callback_query.answer("🔁 Rematch lobby created!")
    for uid in prev_players:
        join_url = f"https://t.me/{BOT_USERNAME}?start=join_{session_id}_a{session.admin_id}"
        await _api_call_with_retry(
            lambda u=uid, url=join_url: app.send_message(
                u,
                f"🔁 **Rematch time!** {callback_query.from_user.first_name} started a new game!\n"
                f"[Tap here to rejoin]({url})"
            ),
            f"rematch_callback/notify/{uid}"
        )


@app.on_message(filters.command("restart"))
async def restart_handler(client, message):
    session_id = str(message.chat.id)
    gm.get_session(session_id).reset()
    gm.cleanup_old_sessions()
    await message.reply_text("🔄 Game restarted! Ready for a new match.")


@app.on_message(filters.command("help"))
async def help_handler(client, message):
    help_text = (
        f"🎮 **Bingo Bot — Help**\n\n"
        f"**How to play:**\n"
        f"1️⃣ In any chat, type `@{BOT_USERNAME}` to invite friends via inline mode.\n"
        f"2️⃣ Alternatively, use `/play` in a **group** to open a lobby there.\n"
        f"3️⃣ Everyone clicks **Join & Play** and picks a card (random or custom).\n"
        f"4️⃣ The host clicks **Start Game** when everyone is ready.\n"
        f"5️⃣ On your turn, pick a number — first to complete **5 lines** wins! 🏆\n\n"
        f"**Commands:**\n"
        f"`/play` — Start a Bingo lobby in a group chat\n"
        f"`/restart` — Reset the current game in a group\n"
        f"`/kick` — Reply to a player's message to kick them (Host only)\n"
        f"`/about` — Credits and bot info\n"
        f"`/help` — Show this help message\n\n"
        f"**Card Tips:**\n"
        f"• **Random Card** — numbers placed automatically.\n"
        f"• **Custom Card** — send 25 unique numbers (1–25) in any order, e.g. `5 12 3 ...`"
    )
    await message.reply_text(help_text)


@app.on_message(filters.command("about"))
async def about_handler(client, message):
    about_text = (
        "🤖 **About Bingo Bot**\n\n"
        "👨‍💻 Author: [Shivam Raj](https://github.com/BetterCallShiv)\n"
        "💻 Source Code: [GitHub](https://github.com/BetterCallShiv/bingo-bot-telegram)\n\n"
        "Enjoy playing Bingo with your friends! 🎮"
    )
    await message.reply_text(about_text, disable_web_page_preview=True)


async def main():
    global BOT_USERNAME
    await app.start()
    me = await app.get_me()
    BOT_USERNAME = me.username
    logger.info(f"Bot started as @{BOT_USERNAME}")
    await app.set_bot_commands([
        BotCommand("play", "Start a new Bingo lobby"),
        BotCommand("restart", "Reset the current game"),
        BotCommand("kick", "Remove a player (reply to msg)"),
        BotCommand("about", "Credits and bot info"),
        BotCommand("help", "How to play bingo")
    ])
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(1800)
            gm.cleanup_old_sessions()
    async def graceful_shutdown():
        logger.info("Graceful shutdown initiated. Stopping bot...")
        await app.stop()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(graceful_shutdown()))
        except (NotImplementedError, OSError):
            signal.signal(sig, lambda s, f: asyncio.ensure_future(graceful_shutdown()))
    asyncio.ensure_future(periodic_cleanup())
    await idle()
    logger.info("Bot has stopped cleanly.")


if __name__ == "__main__":
    app.run(main())

