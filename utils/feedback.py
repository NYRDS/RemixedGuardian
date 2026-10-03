"""Player feedback & Q&A store (sqlite) shared by all processes.

Intake: DMs on Discord/Telegram and Google Play reviews all land in one
feedback.db. For direct player questions an LLM answer draft is generated
and admins are notified on Discord.

Manual confirmation rule: LLM drafts are NEVER sent to players. A player
only receives text that an admin explicitly sends with `answer <id> <text>`.
"""
import asyncio
import datetime
import sqlite3

from conf import CHANNEL_FEEDBACK, GOOGLE_PLAY_ADMINS

from llm_api.mistral import mistral_chat
from utils import notify

DB = "feedback.db"

HELP = (
    "Commands:\n"
    "`fb` - latest entries\n"
    "`fb <id>` - entry details\n"
    "`answer <id> <text>` - send the answer to the player\n"
    "`dismiss <id>` - close without answering"
)

DRAFT_SYSTEM = (
    "You are the support assistant for Remixed Dungeon, a free open-source "
    "pixel-art roguelike by NYRDS (github.com/NYRDS/remixed-dungeon, "
    "Google Play: Remixed Dungeon). Draft a short friendly answer (2-5 "
    "sentences) to the player's message. Reply in the language the player "
    "used. Do not invent facts about versions, dates or features - if unsure, "
    "say the team will confirm. Plain text only, no greetings and no signatures."
)

_conn = None


def conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB, timeout=30)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                author TEXT,
                chat_ref TEXT,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                draft TEXT,
                answer TEXT,
                answered_at TEXT
            )"""
        )
        _conn.commit()
    return _conn


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def add_entry(source: str, author: str, chat_ref: str, text: str) -> int:
    cur = conn().execute(
        "INSERT INTO feedback (created_at, source, author, chat_ref, text) "
        "VALUES (?,?,?,?,?)",
        (now_iso(), source, author, chat_ref, text),
    )
    conn().commit()
    return cur.lastrowid


def get(entry_id: int):
    return conn().execute(
        "SELECT * FROM feedback WHERE id=?", (entry_id,)
    ).fetchone()


def set_draft(entry_id: int, draft: str):
    conn().execute("UPDATE feedback SET draft=? WHERE id=?", (draft, entry_id))
    conn().commit()


def mark_answered(entry_id: int, answer: str):
    conn().execute(
        "UPDATE feedback SET status='answered', answer=?, answered_at=? WHERE id=?",
        (answer, now_iso(), entry_id),
    )
    conn().commit()


def mark_answered_by_ref(chat_ref: str, answer: str):
    """GPlay reviews are answered through the #reviews reply flow; mirror it here."""
    conn().execute(
        "UPDATE feedback SET status='answered', answer=?, answered_at=? "
        "WHERE chat_ref=? AND source='gplay'",
        (answer, now_iso(), chat_ref),
    )
    conn().commit()


def dismiss(entry_id: int):
    conn().execute(
        "UPDATE feedback SET status='dismissed' WHERE id=?", (entry_id,)
    )
    conn().commit()


def format_entry(row) -> str:
    return (
        f"#{row['id']} [{row['source']}] {row['created_at']} "
        f"{row['author'] or '-'} ({row['status']})\n  {(row['text'] or '')[:150]}"
    )


def list_recent() -> str:
    rows = conn().execute(
        "SELECT * FROM feedback ORDER BY status='new' DESC, id DESC LIMIT 10"
    ).fetchall()
    if not rows:
        return "No feedback entries."
    return "\n".join(format_entry(r) for r in rows)


DRAFT_MODEL = "mistral-small-latest"
# DORMANT 2026-10-03: mistral-large left the key's tier (403) and the free
# tier throttles small hard; LLM auto-drafts suspended per operator until a
# working provider is wired. Answers are composed manually (by the operator
# or the coding agent) and sent with `answer <id> <text>`.


def make_draft(text: str) -> str:
    prompt = [
        {"role": "system", "content": DRAFT_SYSTEM},
        {"role": "user", "content": text},
    ]
    # free tier throttles hard; back off patiently, this runs in the background
    for attempt in range(3):
        try:
            return mistral_chat(prompt, model=DRAFT_MODEL)
        except Exception as e:
            throttled = "429" in str(e) or "rate" in str(e).lower()
            if not throttled or attempt == 2:
                raise
            import time

            time.sleep(30 * (attempt + 1))


async def intake(source: str, author: str, chat_ref: str, text: str) -> int:
    """Store a player message, then draft + notify admins in the background.

    Returns the entry id immediately so the player gets an instant reply.
    """
    entry_id = add_entry(source, author, chat_ref, text)
    asyncio.create_task(_finish_intake(entry_id, text))
    return entry_id


async def _finish_intake(entry_id: int, text: str):
    # LLM auto-drafts are dormant (see make_draft note); notify admins with
    # the raw question so an answer can be composed manually.
    await notify_admins(format_for_admin(get(entry_id)))


def format_for_admin(row) -> str:
    return (
        f"New question #{row['id']} [{row['source']}] from {row['author']}:\n"
        f"{(row['text'] or '')[:800]}\n"
        f"---\n"
        f"`answer {row['id']} <text>` to send | `dismiss {row['id']}` | `fb {row['id']}`"
    )


async def notify_admins(text: str):
    try:
        if CHANNEL_FEEDBACK:
            await notify.discord_channel(CHANNEL_FEEDBACK, text)
        else:
            for admin in GOOGLE_PLAY_ADMINS:
                await notify.discord_dm(admin, text)
    except Exception as e:
        print(f"admin notify failed: {e}")


async def execute_admin_command(text: str) -> str:
    """Parse and run an admin command, return the reply for the admin."""
    parts = (text or "").strip().split(maxsplit=2)
    if not parts:
        return HELP

    cmd = parts[0].lower()

    if cmd in ("fb", "feedback") and len(parts) == 1:
        return list_recent()

    if cmd == "fb" and len(parts) > 1:
        row = get(int(parts[1]))
        return format_entry(row) if row else f"#{parts[1]}: not found"

    if cmd in ("answer", "reply") and len(parts) == 3:
        entry_id = int(parts[1])
        answer_text = parts[2].strip()
        row = get(entry_id)
        if not row:
            return f"#{entry_id}: not found"
        if row["status"] == "answered":
            return f"#{entry_id}: already answered"
        if row["source"] == "tg":
            await notify.tg_send(int(row["chat_ref"]), answer_text)
        elif row["source"] == "discord":
            await notify.discord_dm(int(row["chat_ref"]), answer_text)
        else:
            return (
                f"#{entry_id}: gplay reviews are answered by replying to the "
                f"relayed message in #reviews"
            )
        mark_answered(entry_id, answer_text)
        return f"#{entry_id}: answer sent to {row['author']} ({row['source']})"

    if cmd == "dismiss" and len(parts) > 1:
        dismiss(int(parts[1]))
        return f"#{parts[1]}: dismissed"

    return HELP
