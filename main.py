import asyncio
import datetime
import signal
import time

import contractions
from discord import MessageType
from emoji import emojize, replace_emoji
from ftlangdetect import detect

from conf import (
    BOT_TOKEN,
    CHANNEL_GENERAL,
    CHANNEL_ANN,
    CHANNEL_REVIEWS,
    GOOGLE_PLAY_ADMINS,
    CHANNEL_GIT_MONITOR,
)

import discord
from discord.ext import tasks

from google_play import async_publish_fresh_reviews, async_publish_reply
from repo_monitor import check_repos
from utils import floodScore
import pylru
import shelve


def lang(arg):
    if arg is None:
        return None
    arg = arg.replace("\n", " ")
    ret = detect(text=arg, low_memory=True)
    return ret["lang"]


strikes = shelve.open("strikes")
authors = {}
messages = {}


def signal_handler(signal, frame):
    strikes.close()
    exit(0)


signal.signal(signal.SIGINT, signal_handler)


def isGoodMessageForAny(text: str, author: str):
    if author not in authors:
        authors[author] = pylru.lrucache(128)

    if text not in authors[author]:
        authors[author][text] = 0

    authors[author][text] += 1

    if authors[author][text] >= 3:
        return False, "Please don't spam this!"

    text = replace_emoji(text)
    text = contractions.fix(text)

    if floodScore(text) >= 50:
        return False, "Please don't flood!"

    return True, ""


def isGoodMessageForGeneral(text: str, author: str):
    if author not in authors:
        authors[author] = pylru.lrucache(128)

    if text not in authors[author]:
        authors[author][text] = 0

    authors[author][text] += 1

    if authors[author][text] >= 3:
        return False, "Please don't spam this!"

    text = replace_emoji(text)
    text = contractions.fix(text)

    if floodScore(text) >= 30:
        return False, "Please don't flood!"

    if lang(text) != "en":
        return False, "Please use only English here!"

    return True, ""


class RemixedGuardian(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.purge_start = datetime.datetime(year=2023, month=9, day=1)

    async def setup_hook(self) -> None:
        # start the task to run in the background
        # self.my_background_task.start()
        self.reviews_task.start()
        self.git_monitor_task.start()
        pass

    async def on_message(self, message):
        # print(message)

        filenames = " ".join([a.filename for a in message.attachments])
        content_to_check = message.content + " " + filenames
        print(content_to_check)

        if message.channel.id == CHANNEL_REVIEWS and message.type in [
            MessageType.reply
        ]:
            if (
                message.reference is not None
                and message.author.id in GOOGLE_PLAY_ADMINS
            ):
                await async_publish_reply(message.reference.message_id, message.content)
                return

        if message.author.id in GOOGLE_PLAY_ADMINS:
            return # Admins can post anything


        if message.type in [MessageType.default, MessageType.reply]:
            author = str(message.author.id)
            reason = ""

            if message.channel.id == CHANNEL_GENERAL:
                if not message.author.bot:
                    good, reason = isGoodMessageForGeneral(content_to_check, author)
                    if good:
                        # print("Good, general")
                        return
            else:
                good, reason = isGoodMessageForAny(content_to_check, author)
                if good:
                    # print("Good, any")
                    return

            if author not in strikes:
                strikes[author] = 0

            # print("Bad", author, strikes[author])
            strikes[author] += 1

            if strikes[author] >= 5:
                await message.delete(delay=2)
            else:
                await message.channel.send(reason, reference=message)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    @tasks.loop(seconds=1200)
    async def reviews_task(self):
        await self.wait_until_ready()  # wait until the bot logs in
        channel = client.get_channel(CHANNEL_REVIEWS)
        await async_publish_fresh_reviews(channel)

    @tasks.loop(seconds=1537)
    async def git_monitor_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

        def on_new_commit(repo, msg):
            async def _on_new_commit():
                await client.get_channel(CHANNEL_GIT_MONITOR).send(
                    f"New commit detected in {repo}: {msg}"
                )
                await asyncio.sleep(10)

            asyncio.ensure_future(_on_new_commit())

        check_repos(on_new_commit)

    # task runs every 60 seconds
    @tasks.loop(seconds=120)  # task runs every 60 seconds
    async def exterminatus(self):
        await self.wait_until_ready()
        print(f"Exterminatus!")
        channel = client.get_channel(CHANNEL_GENERAL)

        messages = [
            i
            async for i in channel.history(
                after=self.purge_start, before=datetime.datetime.now(), limit=50
            )
        ]
        print("processing: ", len(messages))
        for message in messages:
            print(message.created_at, message.content, lang(message.content), sep="\n")
            if message.created_at.replace(tzinfo=None) > self.purge_start:
                good, reason = isGoodMessageForGeneral(
                    message.content, message.author.name
                )
                if good:
                    continue

                print(f"{reason}, deleting")
                await asyncio.sleep(2)
                await message.delete(delay=2)
                print("done")

            self.purge_start = message.created_at.replace(tzinfo=None)
        print("Sleep")


intent = discord.Intents.all()
client = RemixedGuardian(intents=intent)

client.run(BOT_TOKEN)
