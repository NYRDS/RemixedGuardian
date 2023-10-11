from google.oauth2 import service_account
from googleapiclient.discovery import build

from conf import GOOGLE_PLAY_PACKAGE_NAME, GOOGLE_KEY_FILE_LOCATION

# Authenticate with the Google Play Developer API using a service account
credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_KEY_FILE_LOCATION,
    scopes=["https://www.googleapis.com/auth/androidpublisher"],
)

# Build the API client
service = build("androidpublisher", "v3", credentials=credentials)

# Retrieve the reviews list for the app
reviews = service.reviews().list(packageName=GOOGLE_PLAY_PACKAGE_NAME).execute()

# Print the reviews
for review in reviews["reviews"]:
    print(review)
