from __future__ import annotations

import asyncio
import json
import logging
import traceback

from aiogram import Bot, Dispatcher, types, enums, Router
from aiogram.dispatcher import router
from aiogram.types import Message
from aiogram.filters import BaseFilter, CommandStart

from cerebras_test import cerebras_chat
from conf import TG_API_TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=TG_API_TOKEN)

dp = Dispatcher()
router = Router()


@router.message()
async def echo_handler(message: Message) -> None:
    print(json.dumps(message.dict()))

    try:
        username = message.from_user.username

        if message.reply_to_message.forum_topic_created.name != "sandbox":
            return

        text = message.text

        reply = cerebras_chat(text, username, [])

        await message.reply(reply)
    except Exception:
        traceback.print_tb()


async def main() -> None:
    dp.include_router(router)
    await dp.start_polling(bot, skip_updates=False)


# Start polling
if __name__ == "__main__":
    asyncio.run(main())
