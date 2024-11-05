import json
import re
import string
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

ai = makeRatKing()

game_master = makeGameMaster()


def ensure_session(uid: str):
    if uid not in allSessions:
        allSessions[uid] = Session(uid)
        try:
            allSessions[uid].load()
        except Exception as e:
            print("fresh session", e)

    return allSessions[uid]


def reset_session(uid: str):
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
        if ai.lang == "ru":
            return f"Ход {name}:"

    def turn_string(self, name, text) -> str:
        if ai.lang == "ru":
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
        format_dict = {"player": self.active_user, "setting": ai.setting}

        messages = [
            {
                ROLE: "system",
                CONTENT: game_master.player_check.format(**format_dict),
            },
            {ROLE: "user", CONTENT: self.user_intent},
        ]

        return messages

    def make_params_update_prompt(self) -> list[dict[str, str]]:
        ret = [
            {ROLE: "system", CONTENT: game_master.base_card},
            {ROLE: "assistant", CONTENT: self.get_history()},
            {
                ROLE: "user",
                CONTENT: game_master.params_update.format(
                    **{"npc": ai.name, "params": ai.params}
                ),
            },
        ]

        print("!!!params prompt:\n", ret)

        return ret

    def make_user_params_update_prompt(self) -> list[dict[str, str]]:
        ret = [{ROLE: "system", CONTENT: game_master.base_card}]

        ret.append({ROLE: "assistant", CONTENT: self.get_history()})

        ret.append(
            {
                ROLE: "user",
                CONTENT: game_master.params_update.format(
                    **{"npc": self.active_user, "params": self.get_user_status()}
                ),
            }
        )

        print("!!!params prompt:\n", ret)

        return ret

    def make_relations_update_prompt(self) -> list[dict[str, str]]:
        ret = [{ROLE: "system", CONTENT: game_master.base_card}]
        ret.append({ROLE: "assistant", CONTENT: self.get_history()})

        ret.append(
            {
                ROLE: "user",
                CONTENT: game_master.relations_update.format(
                    **{
                        "npc": ai.name,
                        "player": self.active_user,
                        RELATIONS: self.get_relations(),
                    }
                ),
            }
        )

        print("!!!relations prompt:\n", ret)

        return ret

    def params_updated(self, params: str):
        ai.params = params
        self.data[PARAMS] = params

    def relations_updated(self, relations: str):
        self.data[RELATIONS][self.active_user] = relations

    def make_story_prompt(self) -> list[dict[str, str]]:
        ret = [
            {
                ROLE: "system",
                CONTENT: game_master.base_card
                + f"\nСтатус {ai.name}:\n"
                + ai.params
                + f"\nДействия {ai.name}\n"
                + self.npc_intent
                + f"\nd20 roll за {ai.name}: {randint(1,20)}\n"
                + f"\nСтатус {self.active_user}:\n"
                + self.get_user_status()
                + f"\nДействия {self.active_user}\n"
                + f"\nd20 roll за {self.active_user}: {randint(1, 20)}\n"
                + self.user_intent,
            }
        ]
        ret.append({ROLE: "assistant", CONTENT: self.get_history()})
        ret.append(
            {
                ROLE: "user",
                CONTENT: f"Продолжи историю учитывая статус и намерения {self.active_user} и {ai.name}. Будь лаконичен, не более 3 абзацев.\n",
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
                CONTENT: ai.base_card
                + f"\nСтатус {ai.name}:\n"
                + ai.params
                + f"\nОтношение {ai.name} к {self.active_user}\n"
                + self.get_relations(),
            },
            {ROLE: "assistant", CONTENT: self.get_history()},
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
