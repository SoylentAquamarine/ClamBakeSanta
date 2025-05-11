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

# === Get today's date and holiday list ===
today = datetime.now().strftime("%m-%d")
holiday_list = themes.get(today, [])

if holiday_list:
    for holiday in holiday_list:
        try:
            # Create hashtag (remove spaces and punctuation, PascalCase)
            hashtag = "#" + "".join(c for c in holiday.title() if c.isalnum())

            # Prompt ChatGPT
            prompt = (
                f"Write a haiku in 5-7-5 format about {holiday}. "
                "Make it sensory and poetic, as if celebrating a fun or meaningful holiday. "
                "Do not include a title or explanation — just the 3 haiku lines."
            )

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # or gpt-4 if enabled
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.9
            )

            haiku = response.choices[0].message['content'].strip()

            tweet = f"{haiku}\n\nHappy {hashtag} from @ClamBakeSanta"
            api.update_status(tweet)
            print(f"✅ Tweet posted for: {holiday}")

        except Exception as e:
            print(f"❌ Failed to post for {holiday}: {e}")
else:
    print("No holidays for today.")
