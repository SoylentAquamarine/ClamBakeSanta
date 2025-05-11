import os
import tweepy
import openai
from datetime import datetime
from days import themes

# === Twitter Auth ===
auth = tweepy.OAuth1UserHandler(
    os.environ['API_KEY'],
    os.environ['API_SECRET_KEY'],
    os.environ['ACCESS_TOKEN'],
    os.environ['ACCESS_TOKEN_SECRET']
)
api = tweepy.API(auth)

# === OpenAI Auth ===
openai.api_key = os.environ['OPENAI_API_KEY']

# === Get today's theme ===
today = datetime.now().strftime("%m-%d")
theme = themes.get(today)

if theme:
    # Convert theme to hashtag
    hashtag = "#" + "".join(word for word in theme.title() if word.isalnum())

    # Prompt ChatGPT for a haiku
    prompt = (
        f"Write a haiku in 5-7-5 format about {theme}. "
        "Make it sensory, poetic, and appropriate for a fun holiday tweet."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or gpt-4 if enabled
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.8
        )
        haiku = response.choices[0].message['content'].strip()

        # Build the tweet
        tweet = f"{haiku}\n\nHappy {hashtag} from @ClamBakeSanta"
        api.update_status(tweet)
        print("Tweet posted:", tweet)

    except Exception as e:
        print("Error generating or posting haiku:", e)
else:
    print("No theme found for today.")
