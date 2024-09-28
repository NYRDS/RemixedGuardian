import json

from state.ai_person import makeRatKing

ROLE = "role"
CONTENT = "content"

HISTORY = "history"
TOKEN_BUDGET = 7000

allSessions = {}

ai = makeRatKing()


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

    def dumps(self):
        return json.dumps(self.data, ensure_ascii=False)

    def save(self):
        with open(self.filename(), "w") as f:
            f.write(self.dumps())

    def load(self):
        with open(self.filename(), "r") as f:
            self.data = json.load(f)

    def turn_string(self, name, text) -> str:
        if ai.lang == "ru":
            return f"ход {name}: {text}"

    def user_text(self, user_text: str, user_name: str):
        self.data[HISTORY].append(
            {ROLE: "user", CONTENT: self.turn_string(user_name, user_text)}
        )

    def llm_text(self, llm_text: str):
        self.data[HISTORY].append(
            {ROLE: "assistant", CONTENT: self.turn_string(ai.name, llm_text)}
        )

    def get_history(self) -> list[dict[str, str]]:
        return self.data[HISTORY]

    def make_prompt(self) -> list[dict[str, str]]:
        messages = []
        tokens_used = len(ai.base_card)

        for message in reversed(self.get_history()):
            tokens_used += len(message[CONTENT])
            if tokens_used > TOKEN_BUDGET:
                break
            messages.append({ROLE: message[ROLE], CONTENT: message[CONTENT]})

        ret = [{ROLE: "system", CONTENT: ai.base_card}]
        ret.extend(reversed(messages))

        print(ret)

        return ret

    def filename(self):
        return f"data/sessions/{self.data['uid']}.json"
