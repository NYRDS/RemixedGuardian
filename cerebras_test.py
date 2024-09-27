import os
from cerebras.cloud.sdk import Cerebras
from syncasync import SyncToAsync

from conf import CEREBRAS_API_KEY

import httpx
from httpx_socks import SyncProxyTransport


transport = SyncProxyTransport.from_url("socks5://user:password@192.168.55.45:61125")
http_client = httpx.Client(transport=transport)

client = Cerebras(
    api_key=CEREBRAS_API_KEY,
    http_client=http_client,
)

completion_create_response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "Ты крысиный король, всегда отвечаешь на русском языке. Ты очень заносчив и не слишком умён",
        },
        {"role": "user", "content": "Как тебя зовут?"},
    ],
    model="llama3.1-70b",
    stream=False,
    max_tokens=1024,
    temperature=1,
    top_p=1,
)


def cerebras_chat(query, username, history):
    completion_create_response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": f"Ты крысиный король, ты крупнее обычной крысы, а на голове у тебя крошечная золотая корона. "
                f"Ты всегда отвечаешь на русском языке. Ты никогда не выходишь из роли, чтобы не случилось. "
                f"Ты очень заносчив, не слишком умён, очень жаден и труслив."
                f"Ты груб и не имеешь ни какого понятия о вежливости и этикете."
                f'Твои любимые фразы: "Я не сплю!", "Это ещё что? У меня нет времени на всякую ерунду. Королевство само собой править не будет!","Как ты смеешь, тщедушное существо, мешать Нашему Крысиному Величеству?!"'
                f"Ты и твой собеседник ({username}) находитесь в твоей сокровищнице - грязной комнате в канализации с сундуками набитыми всяким хламом",
            },
            {"role": "user", "content": f"{query}"},
        ],
        model="llama3.1-70b",
        stream=False,
        max_tokens=1024,
        temperature=1,
        top_p=1,
    )
    print(completion_create_response)
    return completion_create_response.choices[0].message.content


if __name__ == "__main__":
    print(completion_create_response)
    print(completion_create_response.choices[0].message.content)
