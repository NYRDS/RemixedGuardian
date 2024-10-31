import json
import re
import string

from state.ai_person import makeRatKing, makeGameMaster

PARAMS = "params"

RELATIONS = "relations"

ROLE = "role"
CONTENT = "content"

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


class Session:
    def __init__(self, uid: str):
        self.data = {}
        self.data["uid"] = uid
        self.data[HISTORY] = []
        self.data[RELATIONS] = {}
        self.data[PARAMS] = ""
        self.active_user = None

    def dumps(self):
        return json.dumps(self.data, ensure_ascii=False)

    def save(self):
        with open(self.filename(), "w") as f:
            f.write(self.dumps())

    def load(self):
        with open(self.filename(), "r") as f:
            self.data = json.load(f)

    def turn_template(self, name) -> str:
        if ai.lang == "ru":
            return f"Ход {name}:"

    def turn_string(self, name, text) -> str:
        if ai.lang == "ru":
            return f"{self.turn_template(name)} {text}"

    def user_text(self, user_text: str, user_name: str):
        self.active_user = user_name
        self.data[HISTORY].append(
            {ROLE: "user", CONTENT: self.turn_string(user_name, user_text)}
        )

    def pop_user_text(self):
        self.data[HISTORY].pop()
        self.active_user = None

    def llm_text(self, llm_text: str):
        llm_text = self.clean_llm_reply(llm_text)

        self.data[HISTORY].append(
            {ROLE: "assistant", CONTENT: self.turn_string(ai.name, llm_text)}
        )

    def clean_llm_reply(self, llm_text):
        return re.sub(r"Ход.*?:", "", llm_text).strip(string.whitespace)
        # return llm_text.replace(self.turn_template(ai.name), "").strip(
        #     string.whitespace
        # )

    def get_history(self) -> list[dict[str, str]]:
        return self.data[HISTORY]

    def make_user_input_check_prompt(self) -> list[dict[str, str]]:
        format_dict = {"player": self.active_user, "setting": ai.setting}
        print(game_master.player_check, format_dict)

        messages = [
            {
                ROLE: "system",
                CONTENT: game_master.player_check.format(**format_dict),
            }
        ]
        messages.append({ROLE: "user", CONTENT: self.data[HISTORY][-1][CONTENT]})
        return messages

    def make_params_update_prompt(self) -> list[dict[str, str]]:
        messages = []
        tokens_used = len(game_master.base_card)

        for message in reversed(self.get_history()):
            tokens_used += len(message[CONTENT])
            if tokens_used > TOKEN_BUDGET:
                break
            messages.append({ROLE: message[ROLE], CONTENT: message[CONTENT]})

        ret = [{ROLE: "system", CONTENT: game_master.base_card}]
        ret.extend(reversed(messages))

        ret.append(
            {
                ROLE: "user",
                CONTENT: game_master.params_update.format(
                    **{"npc": ai.name, "params": ai.params}
                ),
            }
        )

        print("!!!params prompt:\n", ret)

        return ret

    def make_relations_update_prompt(self) -> list[dict[str, str]]:
        messages = []
        tokens_used = len(game_master.base_card)

        for message in reversed(self.get_history()):
            tokens_used += len(message[CONTENT])
            if tokens_used > TOKEN_BUDGET:
                break
            messages.append({ROLE: message[ROLE], CONTENT: message[CONTENT]})

        ret = [{ROLE: "system", CONTENT: game_master.base_card}]
        ret.extend(reversed(messages))

        if self.active_user not in self.data[RELATIONS]:
            self.data[RELATIONS][self.active_user] = "Нет отношения"

        ret.append(
            {
                ROLE: "user",
                CONTENT: game_master.relations_update.format(
                    **{"npc": ai.name, "player": self.active_user, RELATIONS:self.data[RELATIONS][self.active_user]}
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

    def make_reply_prompt(self) -> list[dict[str, str]]:
        messages = []
        tokens_used = len(ai.base_card)

        for message in reversed(self.get_history()):
            tokens_used += len(message[CONTENT])
            if tokens_used > TOKEN_BUDGET:
                break
            messages.append({ROLE: message[ROLE], CONTENT: message[CONTENT]})

        ret = [{ROLE: "system", CONTENT: ai.base_card + f"\nСтатус {ai.name}:\n" + ai.params + f"\nОтношение {ai.name} к {self.active_user}\n" + self.data[RELATIONS][self.active_user]}]
        ret.extend(reversed(messages))

        print("!!!reply prompt:\n", ret)

        return ret

    def llm_reply(self) -> str:
        return self.clean_llm_reply(self.data[HISTORY][-1][CONTENT])

    def filename(self):
        return f"data/sessions/{self.data['uid']}.json"
