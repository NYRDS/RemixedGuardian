from __future__ import annotations

import asyncio
import json
import logging
import string
import traceback

from aiogram import Bot, Dispatcher, Router
from aiogram.dispatcher import router
from aiogram.types import Message

from cerebras_test import cerebras_chat
from conf import TG_API_TOKEN, DEBUG
from state.session import ensure_session, HISTORY, Session, reset_session

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
        if len(message.from_user.first_name) > 0:
            username = message.from_user.first_name

        if (
            True
            or message.chat.id == -1001885182552
            and message.chat.type == "supergroup"
            and message.message_thread_id == 4521
        ):  # Remixed Dungeon sandbox
            text = message.text

            uid = str(message.chat.id)

            if text.startswith("reset"):
                reset_session(uid)
                await message.reply("сессия сброшена")
                return

            session = ensure_session(uid)
            session.user_text(text, username)

            check_reply = cerebras_chat(session.make_user_input_check_prompt())

            test_reply = check_reply.strip().lower().strip().strip(string.punctuation)

            if not test_reply.startswith("да") and not test_reply.endswith("да"):
                session.pop_user_text()
                await message.reply(check_reply)
                return

            session.npc_intent = cerebras_chat(session.make_intent_prompt())

            reply = cerebras_chat(session.make_story_prompt())
            session.llm_text(session.clean_llm_reply(reply))

            user_params = cerebras_chat(session.make_user_params_update_prompt())
            session.user_status(user_params)

            await message.reply(f"{username}:\n{user_params}")

            updated_params = cerebras_chat(session.make_params_update_prompt())
            updated_params = session.clean_llm_reply(updated_params)
            session.params_updated(updated_params)

            await message.reply(updated_params)

            updated_relations = cerebras_chat(session.make_relations_update_prompt())
            updated_relations = session.clean_llm_reply(updated_relations)
            session.relations_updated(updated_relations)

            await message.reply(updated_relations)

            await message.reply(session.llm_reply())

            session.save()

    except Exception:
        traceback.print_exc()


async def main() -> None:
    dp.include_router(router)
    await dp.start_polling(bot, skip_updates=False)


# Start polling
if __name__ == "__main__":
    asyncio.run(main())
