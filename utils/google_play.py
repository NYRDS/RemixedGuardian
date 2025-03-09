import asyncio

from emoji import emojize
from google.oauth2 import service_account
from googleapiclient.discovery import build

from conf import GOOGLE_PLAY_PACKAGE_NAME, GOOGLE_KEY_FILE_LOCATION

import shelve

reviews_db = shelve.open("reviews")


def get_service():
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_KEY_FILE_LOCATION,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )

    # Build the API client
    service = build("androidpublisher", "v3", credentials=credentials)
    return service


async def async_publish_fresh_reviews(channel=None):
    print("Publishing fresh reviews...")

    # Retrieve the reviews list for the app
    try:
        service = get_service()
        reviews = (
            service.reviews()
            .list(packageName=GOOGLE_PLAY_PACKAGE_NAME, translationLanguage="en")
            .execute()
        )

        for review in reviews["reviews"]:
            if review["reviewId"] not in reviews_db:
                stars = review["comments"][0]["userComment"]["starRating"]
                text = f"{review['authorName']}: {emojize(':star:'*stars)}\n {review['comments'][0]['userComment']['text']}"
                if "originalText" in review["comments"][0]["userComment"]:
                    text += (
                        f"\n\n{review['comments'][0]['userComment']['originalText']}"
                    )

                if channel is not None:
                    reviews_db[review["reviewId"]] = review
                    res = await channel.send(content=text)
                    reviews_db[str(res.id)] = review["reviewId"]
                    return

    except Exception as e:
        print(e)


async def async_publish_reply(msg_id, replyMsg: str):
    msg_id = str(msg_id)
    if msg_id in reviews_db:
        review_id = reviews_db[msg_id]
        service = get_service()
        print(f"Replying to review {review_id} with {replyMsg}")

        ret = (
            service.reviews()
            .reply(
                body={"replyText": replyMsg},
                packageName=GOOGLE_PLAY_PACKAGE_NAME,
                reviewId=review_id,
            )
            .execute()
        )
        print(f"{ret}")

    else:
        print("Replying to review that doesn't exist")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(async_publish_fresh_reviews())
