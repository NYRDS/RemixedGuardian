
from mistralai import Mistral, UserMessage
from conf import MISTRAL_API_KEY

client = Mistral(api_key=MISTRAL_API_KEY)

def mistral_chat(prompt):

    if prompt[-1]["role"] == "assistant":
        prompt[-1]["prefix"] = True

    chat_response = client.chat.complete(
        messages=prompt,
        model="mistral-large-latest",
        max_tokens=1024,
        temperature=1,
        top_p=1,
        safe_prompt=False
    )
    return chat_response.choices[0].message.content

if __name__ == "__main__":
    messages = [
        {"role": "system", "content": "Ты крысиный король, всегда отвечаешь на русском языке. Ты очень заносчив и не слишком умён."},
        {"role": "user", "content": "Как тебя зовут?"},
    ]

    response = client.chat.complete(
        messages=messages,
        model="mistral-large-latest",
        max_tokens=1024,
        temperature=1,
        top_p=1,
    )
    print(response.choices[0].message.content)