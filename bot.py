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

# === Get today's date and holidays ===
today = datetime.now().strftime("%m-%d")
holiday_list = themes.get(today, [])

if holiday_list:
    for holiday in holiday_list:
        try:
            # Format hashtag
            if "birthday" in holiday.lower():
                # Example: "Birthday Blac Chyna" → #HappyBirthdayBlacChyna
                name = holiday.replace("Birthday", "").strip()
                hashtag = f"#HappyBirthday{''.join(word.capitalize() for word in name.split())}"
                tweet_intro = f"{hashtag} from @ClamBakeSanta"
            else:
                # Example: "Hostess CupCake Day" → #HostessCupCakeDay
                tag = "#" + "".join(c for c in holiday.title() if c.isalnum())
                hashtag = tag
                tweet_intro = f"Happy {hashtag} from @ClamBakeSanta"

            # Prompt ChatGPT
            prompt = (
                f"Write a haiku in 5-7-5 format about {holiday}. "
                "Make it sensory, poetic, and themed like a holiday. "
                "Only output the three haiku lines with no title or extras."
            )

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.9
            )

            haiku = response.choices[0].message['content'].strip()
            tweet = f"{haiku}\n\n{tweet_intro}"
            api.update_status(tweet)
            print(f"✅ Tweet posted for: {holiday}")

        except Exception as e:
            print(f"❌ Failed to post for {holiday}: {e}")
else:
    print("No holidays for today.")
