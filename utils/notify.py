"""Cross-platform send helpers: plain REST, no gateway or polling imports.

Used by the discord bot, the tg community bot and CLI tools, so any process
can reach both platforms (e.g. a TG-received question notifies the admin
through a Discord DM).
"""
import aiohttp

from conf import BOT_TOKEN, TG_API_TOKEN

DISCORD_API = "https://discord.com/api/v10"
TG_API = f"https://api.telegram.org/bot{TG_API_TOKEN}"


def _chunks(text: str, size: int):
    text = text or ""
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut < size // 2:
            cut = size
        yield text[:cut]
        text = text[cut:].lstrip("\n")
    if text:
        yield text


def _discord_headers():
    return {"Authorization": f"Bot {BOT_TOKEN}"}


async def discord_channel(channel_id: int, text: str) -> int:
    """Post to a channel, return the id of the last posted message."""
    last = None
    async with aiohttp.ClientSession(headers=_discord_headers()) as s:
        for chunk in _chunks(text, 1900):
            async with s.post(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                json={"content": chunk},
            ) as r:
                if r.status >= 300:
                    raise RuntimeError(
                        f"discord send {r.status}: {(await r.text())[:300]}"
                    )
                last = (await r.json())["id"]
    return last


async def discord_dm(user_id: int, text: str) -> None:
    async with aiohttp.ClientSession(headers=_discord_headers()) as s:
        async with s.post(
            f"{DISCORD_API}/users/@me/channels", json={"recipient_id": user_id}
        ) as r:
            if r.status >= 300:
                raise RuntimeError(
                    f"discord dm open {r.status}: {(await r.text())[:300]}"
                )
            dm = await r.json()
        for chunk in _chunks(text, 1900):
            async with s.post(
                f"{DISCORD_API}/channels/{dm['id']}/messages",
                json={"content": chunk},
            ) as r:
                if r.status >= 300:
                    raise RuntimeError(
                        f"discord dm send {r.status}: {(await r.text())[:300]}"
                    )


async def tg_api(method: str, **payload):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{TG_API}/{method}", json=payload) as r:
            data = await r.json()
    if not data.get("ok"):
        raise RuntimeError(f"tg {method}: {data.get('description')}")
    return data["result"]


async def tg_send(chat_id, text: str, thread=None) -> None:
    for chunk in _chunks(text, 3900):
        params = {"chat_id": chat_id, "text": chunk}
        if thread:
            params["message_thread_id"] = thread
        await tg_api("sendMessage", **params)
