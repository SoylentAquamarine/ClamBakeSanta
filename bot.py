import os
import tweepy
from datetime import datetime

# Authenticate to Twitter
auth = tweepy.OAuth1UserHandler(
    os.environ['API_KEY'],
    os.environ['API_SECRET_KEY'],
    os.environ['ACCESS_TOKEN'],
    os.environ['ACCESS_TOKEN_SECRET']
)
api = tweepy.API(auth)

# Generate today's theme (placeholder)
today = datetime.now().strftime("%B %d")
theme = f"Today is {today}."

# Placeholder haiku
haiku = f"{theme}\nLine two of haiku\nFinal line here."

# Post the tweet
api.update_status(haiku)
