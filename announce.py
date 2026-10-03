#!/usr/bin/env python3
"""Post an announcement to Discord and Telegram.

Targets come from conf.py: CHANNEL_ANN (Discord channel id) and
TG_ANNOUNCE_CHAT / TG_ANNOUNCE_THREAD (Telegram). Run from the project dir
on the bot host (conf.py lives there).

Usage:
  python3 announce.py -m "server restart at 20:00 UTC"        # both platforms
  python3 announce.py -f post.md --tg-only
  echo "maintenance soon" | python3 announce.py --discord-only --pin
  python3 announce.py --dry-run          # validate tokens and targets, send nothing
"""
import argparse
import asyncio
import sys

import aiohttp

from conf import BOT_TOKEN, CHANNEL_ANN, TG_ANNOUNCE_CHAT, TG_ANNOUNCE_THREAD
from utils import notify


async def resolve_tg_thread(args_thread):
    if args_thread == "default":
        return TG_ANNOUNCE_THREAD
    if args_thread == "none":
        return None
    return int(args_thread)


async def announce(text, discord, tg, pin, discord_channel, tg_chat, tg_thread):
    if discord:
        channel = discord_channel or CHANNEL_ANN
        last = await notify.discord_channel(channel, text)
        print(f"discord: posted to channel {channel}")
        if pin:
            async with aiohttp.ClientSession(
                headers={"Authorization": f"Bot {BOT_TOKEN}"}
            ) as s:
                async with s.put(
                    f"{notify.DISCORD_API}/channels/{channel}/pins/{last}"
                ) as r:
                    if r.status >= 300:
                        print(f"discord pin failed {r.status}: {(await r.text())[:200]}")
                    else:
                        print("discord: message pinned")

    if tg:
        await notify.tg_send(tg_chat, text, thread=tg_thread)
        print(f"tg: posted to chat {tg_chat} (thread {tg_thread})")


async def dry_run(discord, tg, discord_channel, tg_chat, tg_thread):
    if discord:
        channel = discord_channel or CHANNEL_ANN
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{notify.DISCORD_API}/users/@me") as r:
                me = await r.json()
                print(f"discord bot: {me.get('username')} ({me.get('id')})")
            async with s.get(f"{notify.DISCORD_API}/channels/{channel}") as r:
                ch = await r.json()
                print(
                    f"discord target: #{ch.get('name')} "
                    f"(guild {ch.get('guild_id')}, type {ch.get('type')})"
                )

    if tg:
        me = await notify.tg_api("getMe")
        print(f"tg bot: @{me.get('username')} ({me.get('id')})")
        chat = await notify.tg_api("getChat", chat_id=tg_chat)
        print(
            f"tg target: {chat.get('title') or chat.get('username')} "
            f"(id {chat.get('id')}, forum={chat.get('is_forum', False)}), "
            f"thread={tg_thread}"
        )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("-m", "--message", help="announcement text")
    g.add_argument("-f", "--file", help="read the announcement text from a file")
    p.add_argument("--discord-only", action="store_true")
    p.add_argument("--tg-only", action="store_true")
    p.add_argument(
        "--pin", action="store_true", help="pin the message in the Discord channel"
    )
    p.add_argument("--discord-channel", type=int, help="override CHANNEL_ANN")
    p.add_argument("--tg-chat", type=int, help="override TG_ANNOUNCE_CHAT")
    p.add_argument(
        "--tg-thread",
        default="default",
        help="topic id, 'default' (conf value) or 'none'",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    text = args.message
    if args.file:
        with open(args.file) as f:
            text = f.read()
    if text is None and not args.dry_run and not sys.stdin.isatty():
        text = sys.stdin.read()
    if not args.dry_run and not (text or "").strip():
        p.error("no message text (use -m, -f or pipe to stdin)")

    discord = not args.tg_only
    tg = not args.discord_only
    tg_thread = asyncio.run(resolve_tg_thread(args.tg_thread))

    if args.dry_run:
        asyncio.run(
            dry_run(discord, tg, args.discord_channel, args.tg_chat, tg_thread)
        )
    else:
        asyncio.run(
            announce(
                text,
                discord,
                tg,
                args.pin,
                args.discord_channel,
                args.tg_chat,
                tg_thread,
            )
        )


if __name__ == "__main__":
    main()
