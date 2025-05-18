import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# === Load tweet from file ===
with open("outbox.txt", "r", encoding="utf-8") as f:
    tweet_text = f.read().strip()

# === Load credentials from environment ===
TWITTER_USERNAME = os.environ["TWITTER_USERNAME"]
TWITTER_PASSWORD = os.environ["TWITTER_PASSWORD"]

# === Configure ChromeDriver ===
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # Uncomment if you want it invisible

driver = webdriver.Chrome(options=options)

# === Log in to Twitter ===
driver.get("https://twitter.com/login")
time.sleep(5)

# === Enter username ===
username_input = driver.find_element(By.NAME, "text")
username_input.send_keys(TWITTER_USERNAME)
username_input.send_keys(Keys.RETURN)
time.sleep(3)

# === Enter password ===
password_input = driver.find_element(By.NAME, "password")
password_input.send_keys(TWITTER_PASSWORD)
password_input.send_keys(Keys.RETURN)
time.sleep(5)

# === Find tweet box and submit tweet ===
tweet_box = driver.find_element(By.CSS_SELECTOR, "div[aria-label='Tweet text']")
tweet_box.click()
tweet_box.send_keys(tweet_text)
time.sleep(1)

tweet_button = driver.find_element(By.XPATH, "//div[@data-testid='tweetButtonInline']")
tweet_button.click()
time.sleep(3)

print("✅ Tweet posted successfully.")
driver.quit()
