import asyncio
import datetime

from emoji import emojize

from conf import BOT_TOKEN, CHANNEL_GENERAL
from langdetect import detect

import discord
from discord.ext import tasks


def lang(arg):
    if arg is None:
        return None

    for_detect = (
        arg.replace("%d", "").replace("%s", "").replace("%1$s", "").replace("%2$s", "")
    )
    from langdetect.lang_detect_exception import LangDetectException

    ret = None
    try:
        ret = detect(for_detect)
    except LangDetectException as e:
        print(arg, "->", e)
    return ret


strikes = {}


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.purge_start = datetime.datetime(year=2023, month=6, day=18)

    async def setup_hook(self) -> None:
        # start the task to run in the background
        # self.my_background_task.start()
        pass

    async def on_message(self, message):
        print(message)
        if message.channel.id != CHANNEL_GENERAL:
            if not message.author.bot:
                await message.add_reaction(emojize(":eye:"))

            if lang(message.content) != "en":
                if not message.author.bot:
                    if message.author.id not in strikes:
                        strikes[message.author.id] = 0

                    strikes[message.author.id] += 1

                    if strikes[message.author.id] >= 5:
                        await message.delete(delay=2)
                    else:
                        await message.channel.send(
                            "Please use only English in this channel", reference=message
                        )

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    @tasks.loop(seconds=120)  # task runs every 60 seconds
    async def my_background_task(self):
        print(f"Exterminatus!")
        channel = client.get_channel(
            CHANNEL_GENERAL
        )  # A channel ID must be entered here

        messages = [
            i
            async for i in channel.history(
                after=self.purge_start, before=datetime.datetime.now(), limit=50
            )
        ]
        print(len(messages))
        for message in messages:
            print(message.created_at, message.content, lang(message.content), sep="\n")
            if message.created_at.replace(tzinfo=None) > self.purge_start:
                if lang(message.content) != "en":
                    print("non-english, deleting")
                    await message.delete(delay=2)
                    print("done")

            self.purge_start = message.created_at.replace(tzinfo=None)
        print("Sleep")

    @my_background_task.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in


intent = discord.Intents.all()
client = MyClient(intents=intent)

client.run(BOT_TOKEN)
