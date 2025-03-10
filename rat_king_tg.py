from __future__ import annotations

import asyncio
import json
import logging
import string
import traceback

from aiogram import Bot, Dispatcher, Router
from aiogram.dispatcher import router
from aiogram.types import Message
from cerebras.cloud.sdk import RateLimitError

from llm_api.mistral import mistral_chat
from conf import TG_API_TOKEN
from state.session import ensure_session, reset_session

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
            # True or
            message.chat.id == -1001885182552
            and message.chat.type == "supergroup"
            and message.message_thread_id == 4521
        ):  # Remixed Dungeon sandbox
            text = message.text

            uid = str(message.chat.id)

            maybe_cmd = text.strip(string.whitespace + string.punctuation).split()[0]
            maybe_cmd = maybe_cmd.lower()

            if maybe_cmd.startswith("reset"):
                reset_session(uid)
                await message.reply("сессия сброшена")
                return

            session = ensure_session(uid)
            session.user_text(text, username)

            if maybe_cmd.startswith("статус"):
                await message.reply(session.get_user_status())
                return

            if maybe_cmd.startswith("персона"):
                make_persona_prompt = session.make_persona_prompt()
                persona_candidate = mistral_chat(make_persona_prompt)

                if await check_for_no(persona_candidate):
                    await message.reply(persona_candidate)
                    return

                session.user_status(persona_candidate)

                await message.reply(f"Персона обновлена: {persona_candidate}")
                return

            user_status = session.user_status(uid)
            if user_status is None or len(user_status) == "":
                await message.reply(f"Сначала вам нужно создать персонажа с помощью команды 'персона', например:\n"
                                    f"Персона: Эльф аристократ, искусный лучник\n"
                                    f"Или\n"
                                    f"Персона: Яростный хоббит-монах, мастер рукопашного боя\n"
                                    f"Или\n"
                                    f"Персона: 'то что вам придет в голову'\n")
                return


            # check_reply = cerebras_chat(session.make_user_input_check_prompt())
            #
            # if not await check_for_yes(check_reply):
            #     await message.reply(check_reply)
            #     return

            fix_reply = mistral_chat(session.make_user_input_fix_prompt())
            session.user_text(fix_reply, username)


            session.npc_intent = mistral_chat(session.make_intent_prompt())

            reply = mistral_chat(session.make_story_prompt())
            session.llm_text(session.clean_llm_reply(reply))

            user_params = mistral_chat(session.make_user_params_update_prompt())
            session.user_status(user_params)

            #await message.reply(f"{username}:\n{user_params}")

            updated_params = mistral_chat(session.make_params_update_prompt())
            updated_params = session.clean_llm_reply(updated_params)
            session.params_updated(updated_params)

            #await message.reply(updated_params)

            updated_relations = mistral_chat(session.make_relations_update_prompt())
            updated_relations = session.clean_llm_reply(updated_relations)
            session.relations_updated(updated_relations)

            #await message.reply(updated_relations)

            await message.reply(f"{session.active_user}:\n{session.user_intent}")
            await message.reply(f"{session.llm_reply()}")

            session.save()

    except RateLimitError as rl:
        await message.reply(f"На сегодня нафлудились: {rl.message}")
        return
    except Exception:
        traceback.print_exc()

async def check_for_yes(check_reply):
    test_reply = check_reply.lower().strip(string.punctuation + string.punctuation)
    if test_reply.startswith("да") or test_reply.endswith("да"):
        return True

async def check_for_no(check_reply):
    test_reply = check_reply.lower().strip(string.punctuation + string.punctuation)
    if test_reply.startswith("нет") or test_reply.endswith("нет"):
        return True

async def main() -> None:
    dp.include_router(router)
    await dp.start_polling(bot, skip_updates=False)


# Start polling
if __name__ == "__main__":
    asyncio.run(main())
