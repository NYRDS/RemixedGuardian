import httpx
from cerebras.cloud.sdk import Cerebras
from conf import CEREBRAS_API_KEY
from httpx_socks import SyncProxyTransport

transport = SyncProxyTransport.from_url("socks5://user:password@192.168.55.45:61125")
http_client = httpx.Client(transport=transport)

client = Cerebras(
    api_key=CEREBRAS_API_KEY,
    http_client=http_client,
)

def cerebras_chat(prompt):
    completion_create_response = client.chat.completions.create(
        messages=prompt,
        model="llama3.1-70b",
        stream=False,
        max_tokens=1024,
        temperature=1,
        top_p=1,
    )
    print(completion_create_response)
    return completion_create_response.choices[0].message.content


if __name__ == "__main__":
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

    print(completion_create_response)
    print(completion_create_response.choices[0].message.content)
