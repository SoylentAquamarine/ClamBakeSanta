import os
import tweepy
import openai
from datetime import datetime

# === Twitter Auth ===
auth = tweepy.OAuth1UserHandler(
    os.environ['API_KEY'],
    os.environ['API_SECRET_KEY'],
    os.environ['ACCESS_TOKEN'],
    os.environ['ACCESS_TOKEN_SECRET']
)
api = tweepy.API(auth)

# === OpenAI Auth ===
client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# === Get today's date and month ===
today = datetime.now().strftime("%m-%d")
month = datetime.now().strftime("%B").lower()  # e.g., "may"

# === Load holidays from files ===
holiday_list = []

def load_holidays_from_file(filename):
    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.startswith(today):
                    holiday = line.split(":", 1)[1].strip()
                    holiday_list.append(holiday)
    except FileNotFoundError:
        print(f"File not found: {filename}")

load_holidays_from_file(f"{month}_celebritybirthday.txt")
load_holidays_from_file(f"{month}_randomholiday.txt")

# === Process each holiday ===
if holiday_list:
    for holiday in holiday_list:
        try:
            # Format hashtag
            if "birthday" in holiday.lower():
                name = holiday.replace("Birthday", "").strip()
                hashtag = f"#HappyBirthday{''.join(word.capitalize() for word in name.split())}"
                tweet_intro = f"{hashtag} from @ClamBakeSanta"
            else:
                tag = "#" + "".join(c for c in holiday.title() if c.isalnum())
                hashtag = tag
                tweet_intro = f"Happy {hashtag} from @ClamBakeSanta"

            # Prompt ChatGPT (OpenAI)
            prompt = (
                f"Write a haiku in 5-7-5 format about {holiday}. "
                "Make it sensory, poetic, and themed like a holiday. "
                "Only output the three haiku lines with no title or extras."
            )

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.9
            )

            haiku = response.choices[0].message.content.strip()
            tweet = f"{haiku}\n\n{tweet_intro}"
            api.update_status(tweet)
            print(f"✅ Tweet posted for: {holiday}")

        except Exception as e:
            print(f"❌ Failed to post for {holiday}: {e}")
else:
    print("No holidays for today.")
