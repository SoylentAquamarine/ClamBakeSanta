import os
import openai
from datetime import datetime

# === OpenAI Auth ===
client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# === Get today's date and month ===
today = datetime.now().strftime("%m-%d")
month = datetime.now().strftime("%B").lower()

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

# === Process first holiday ===
if holiday_list:
    holiday = holiday_list[0]
    try:
        # Format greeting
        if "birthday" in holiday.lower():
            name = holiday.replace("Birthday", "").strip()
            hashtag = f"#HappyBirthday{''.join(word.capitalize() for word in name.split())}"
            tweet_intro = f"{hashtag} from @ClamBakeSanta"
        else:
            tag = "#" + "".join(c for c in holiday.title() if c.isalnum())
            tweet_intro = f"Happy {tag} from @ClamBakeSanta"

        # Haiku prompt
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

        # Write to outbox.txt
        with open("outbox.txt", "w", encoding="utf-8") as f:
            f.write(tweet + "\n")

        print("✅ Haiku written to outbox.txt")

        # === Commit and push outbox.txt ===
        os.system("git config --global user.name 'ClamBakeSantaBot'")
        os.system("git config --global user.email 'bot@example.com'")
        os.system("git add outbox.txt")
        os.system('git commit -m "Daily haiku update"')
        os.system("git push origin main")

    except Exception as e:
        print(f"❌ Failed to generate tweet: {e}")
else:
    print("No holidays for today.")
