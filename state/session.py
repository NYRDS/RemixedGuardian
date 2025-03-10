import json
import os
import re
import string
import time
import traceback
from random import random, randint

from state.ai_person import makeRatKing, makeGameMaster

PARAMS = "params"

RELATIONS = "relations"
USER_STATUS = "user_status"
ROLE = "role"
CONTENT = "content"
STORY = "story"
HISTORY = "history"
TOKEN_BUDGET = 5000

allSessions = {}


def ensure_session(uid: str):
    if uid not in allSessions:
        allSessions[uid] = Session(uid)
        try:
            allSessions[uid].load()
        except Exception as e:
            print("fresh session", e)

    return allSessions[uid]


def reset_session(uid: str):
    ensure_session(uid)
    ts = int(time.time())
    try:
        os.rename(
            allSessions[uid].filename(),
            allSessions[uid].filename() + f".{ts}.bak")
    except Exception as e:
        print("reset session", e)

    allSessions[uid] = Session(uid)


class Session:
    def __init__(self, uid: str):
        self.data = {}
        self.data["uid"] = uid
        self.data[HISTORY] = []
        self.data[RELATIONS] = {}
        self.data[PARAMS] = ""
        self.active_user = None
        self.user_intent = None
        self.npc_intent = None
        self.fix_data()

        self.ai = makeRatKing()
        self.game_master = makeGameMaster()

    def fix_data(self):
        if HISTORY not in self.data:
            self.data[HISTORY] = []
        if RELATIONS not in self.data:
            self.data[RELATIONS] = {}
        if PARAMS not in self.data:
            self.data[PARAMS] = ""
        if USER_STATUS not in self.data:
            self.data[USER_STATUS] = {}

    def dumps(self):
        return json.dumps(self.data, ensure_ascii=False)

    def save(self):
        with open(self.filename(), "w") as f:
            f.write(self.dumps())

    def load(self):
        with open(self.filename(), "r") as f:
            self.data = json.load(f)
            self.fix_data()

    def turn_template(self, name) -> str:
        if self.ai.lang == "ru":
            return f"Ход {name}:"

    def turn_string(self, name, text) -> str:
        if self.ai.lang == "ru":
            return f"{self.turn_template(name)} {text}"

    def user_text(self, user_text: str, user_name: str):
        self.active_user = user_name
        self.user_intent = user_text

    def pop_user_text(self):
        self.active_user = None

    def llm_text(self, llm_text: str):
        llm_text = self.clean_llm_reply(llm_text)

        self.data[HISTORY].append(llm_text)

    def clean_llm_reply(self, llm_text):
        return llm_text.strip(string.whitespace)

    def get_history(self) -> list[dict[str, str]]:
        ret = ""

        tokens_used = 0

        for message in reversed(self.data[HISTORY]):
            tokens_used += len(message)
            if tokens_used > TOKEN_BUDGET:
                break
            ret = message + "\n" + ret

        return ret

    def make_user_input_check_prompt(self) -> list[dict[str, str]]:
        format_dict = {"player": self.active_user,
                       "setting": self.ai.setting,
                       "history": self.get_history(),
                       "player_status": self.get_user_status(),
                       }

        messages = [
            {
                ROLE: "system",
                CONTENT: self.game_master.player_check.format(**format_dict),
            },
            {ROLE: "user", CONTENT: self.user_intent},
        ]

        return messages


    def make_user_input_fix_prompt(self) -> list[dict[str, str]]:
        format_dict = {"player": self.active_user,
                       "setting": self.ai.setting,
                       "history": self.get_history(),
                       "player_status": self.get_user_status(),
                       }

        messages = [
            {
                ROLE: "system",
                CONTENT: self.game_master.player_fix.format(**format_dict),
            },
            {ROLE: "user", CONTENT: self.user_intent},
        ]

        return messages

    def make_persona_prompt(self) -> list[dict[str, str]]:
        format_dict = {"player": self.active_user,
                       "setting": self.ai.setting,
                       "history": self.get_history(),
                       }

        messages = [
            {
                ROLE: "system",
                CONTENT: self.game_master.player_persona.format(**format_dict),
            },
            {ROLE: "user", CONTENT: f"Предложение {self.active_user}:\n {self.user_intent}"},
            {ROLE: "assistant", CONTENT: f"Лист персонажа {self.active_user}:\n"}
        ]

        return messages


    def make_params_update_prompt(self) -> list[dict[str, str]]:
        ret = [
            {ROLE: "system", CONTENT: self.game_master.base_card
             + "\nПредыстория:\n"
             + self.get_history()
             },
             {
                ROLE: "user",
                CONTENT: self.game_master.params_update.format(
                    **{"npc": self.ai.name, "params": self.ai.params}
                ),
            },
        ]

        print("!!!params prompt:\n", ret)

        return ret

    def make_user_params_update_prompt(self) -> list[dict[str, str]]:
        ret = [{ROLE: "system", CONTENT: self.game_master.base_card
                + "\nПредыстория:\n"
                + self.get_history()
                },
            {
                ROLE: "user",
                CONTENT: self.game_master.params_pc_update.format(
                    **{"npc": self.active_user, "params": self.get_user_status()}
                ),
            }
        ]

        print("!!!params prompt:\n", ret)

        return ret

    def make_relations_update_prompt(self) -> list[dict[str, str]]:
        ret = [{ROLE: "system", CONTENT: self.game_master.base_card +
                f"\nПредыстория:\n" + self.get_history()},
            {
                ROLE: "user",
                CONTENT: self.game_master.relations_update.format(
                    **{
                        "npc": self.ai.name,
                        "player": self.active_user,
                        RELATIONS: self.get_relations(),
                    }
                ),
            }
        ]

        print("!!!relations prompt:\n", ret)

        return ret

    def params_updated(self, params: str):
        self.ai.params = params
        self.data[PARAMS] = params

    def relations_updated(self, relations: str):
        self.data[RELATIONS][self.active_user] = relations

    def make_story_prompt(self) -> list[dict[str, str]]:
        ret = [
            {
                ROLE: "system",
                CONTENT: self.game_master.base_card
                + f"\nСтатус {self.ai.name}:\n"
                + self.ai.params
                + f"\nДействия {self.ai.name}\n"
                + self.npc_intent
                + f"\nd20 roll за {self.ai.name}: {randint(1,20)}\n"
                + f"\nСтатус {self.active_user}:\n"
                + self.get_user_status()
                + f"\nДействия {self.active_user}\n"
                + f"\nd20 roll за {self.active_user}: {randint(1, 20)}\n"
                + self.user_intent
                + f"\nПредыстория:\n"
                + self.get_history(),
            }
        ]
        ret.append(
            {
                ROLE: "user",
                CONTENT: f"Продолжи историю учитывая статус и намерения {self.active_user} и {self.ai.name}. "
                         f"Описывай только что произойдет в результате действий {self.active_user} и {self.ai.name}, "
                         f"не описывай их дальнейшие шаги. Будь лаконичен, не более 3 абзацев.\n"
                         f"Если {self.ai.name} мертв, не продолжай историю, а предложи начать новую игру с помощью команды reset.",
            }
        )

        print("!!!reply prompt:\n", ret)

        return ret

    def make_intent_prompt(self) -> list[dict[str, str]]:
        if self.active_user not in self.data[RELATIONS]:
            self.data[RELATIONS][self.active_user] = "Нет отношения"

        ret = [
            {
                ROLE: "system",
                CONTENT: self.ai.base_card
                + f"\nСтатус {self.ai.name}:\n"
                + self.ai.params
                + f"\nОтношение {self.ai.name} к {self.active_user}:\n"
                + self.get_relations()
                + f"\nПредыстория:\n"
                + self.get_history(),
            },
            {
                ROLE: "user",
                CONTENT: "Опиши что твой персонаж скажет и будет делать в этой ситуацию. Только реплики и действия, не описывай что произошло дальше.",
            },
        ]

        print("!!!reply prompt:\n", ret)

        return ret

    def get_relations(self):
        if self.active_user not in self.data[RELATIONS]:
            self.data[RELATIONS][self.active_user] = "Нет отношения"

        return self.data[RELATIONS][self.active_user]

    def user_status(self, data: str):
        self.data[USER_STATUS][self.active_user] = data

    def get_user_status(self):
        if self.active_user not in self.data[USER_STATUS]:
            self.data[USER_STATUS][self.active_user] = ""

        return self.data[USER_STATUS][self.active_user]

    def llm_reply(self) -> str:
        return self.clean_llm_reply(self.data[HISTORY][-1])

    def filename(self):
        return f"data/sessions/{self.data['uid']}.json"
