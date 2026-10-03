"""Community Telegram bot: collects player questions/feedback via DMs.

Runs alongside remixed_guardian_discord.py. Group chats are ignored -
announcements are posted with announce.py. Admins listed in TG_ADMINS can
run the feedback commands (see utils/feedback.py) right in this chat.
"""
import asyncio
import datetime
import traceback

from conf import TG_ADMINS

from utils import feedback, notify

POLL_TIMEOUT = 50

INTRO = (
    "Hi! This bot accepts questions and feedback for the Remixed Dungeon team.\n"
    "Just write your message here and the team will answer in this chat.\n"
    "\n"
    "Привет! Напишите здесь ваш вопрос или отзыв о Remixed Dungeon — "
    "команда ответит в этом чате."
)

THANKS = (
    "Thanks! Your message was stored as #{} and passed to the team.\n"
    "Спасибо! Сообщение #{} передано команде — ответ придёт сюда."
)


class TGCommunity:
    def __init__(self):
        self.offset = None

    async def discard_backlog(self):
        # Start from the newest update only: months-old group history must not
        # replay as feedback on first launch.
        updates = await notify.tg_api(
            "getUpdates", offset=-1, timeout=0, allowed_updates=["message"]
        )
        if updates:
            self.offset = updates[-1]["update_id"] + 1

    async def run(self):
        await self.discard_backlog()
        backoff = 5
        while True:
            try:
                updates = await notify.tg_api(
                    "getUpdates",
                    offset=self.offset,
                    timeout=POLL_TIMEOUT,
                    allowed_updates=["message"],
                )
                backoff = 5
            except Exception:
                traceback.print_exc()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue

            for upd in updates:
                self.offset = upd["update_id"] + 1
                try:
                    await self.handle(upd.get("message"))
                except Exception:
                    traceback.print_exc()

    async def handle(self, msg):
        if msg is None:
            return
        chat = msg.get("chat", {})
        if chat.get("type") != "private":
            return

        frm = msg.get("from", {})
        uid = frm.get("id")
        text = msg.get("text") or msg.get("caption") or ""
        if not text or uid is None:
            return
        name = (
            frm.get("username")
            or (frm.get("first_name") or "").strip()
            or str(uid)
        )

        print(
            f"{datetime.datetime.now(datetime.timezone.utc)} "
            f"[{uid}] {name}: {text[:80]}",
            flush=True,
        )

        if uid in TG_ADMINS:
            await notify.tg_send(uid, await feedback.execute_admin_command(text))
            return

        if text.startswith("/start"):
            await notify.tg_send(uid, INTRO)
            return

        entry_id = await feedback.intake(
            source="tg", author=name, chat_ref=str(uid), text=text
        )
        await notify.tg_send(uid, THANKS.format(entry_id, entry_id))


async def main():
    while True:
        try:
            await TGCommunity().run()
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
