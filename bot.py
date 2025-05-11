import os
import tweepy
from datetime import datetime
from days import themes, haikus

# Authenticate to Twitter
auth = tweepy.OAuth1UserHandler(
    os.environ['API_KEY'],
    os.environ['API_SECRET_KEY'],
    os.environ['ACCESS_TOKEN'],
    os.environ['ACCESS_TOKEN_SECRET']
)
api = tweepy.API(auth)

# Get today’s date and theme
today = datetime.now().strftime("%m-%d")
theme_key = themes.get(today, None)

if theme_key and theme_key in haikus:
    haiku_body = haikus[theme_key][0]
    hashtag = f"#{theme_key}"
    tweet = f"{haiku_body}\n\nHappy {hashtag} from @ClamBakeSanta"
    api.update_status(tweet)
else:
    print("No theme or haiku found for today.")
