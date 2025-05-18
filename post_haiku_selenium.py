import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# Replace with your credentials (or use env vars)
TWITTER_USERNAME = os.environ["TWITTER_USERNAME"]
TWITTER_PASSWORD = os.environ["TWITTER_PASSWORD"]

# Text you want to post
with open("outbox.txt", "r", encoding="utf-8") as f:
    tweet_text = f.read().strip()

# Chrome setup (headless optional)
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # Uncomment for headless mode

driver = webdriver.Chrome(options=options)
driver.get("https://twitter.com/login")
time.sleep(5)

# === Login ===
username_field = driver.find_element(By.NAME, "text")
username_field.send_keys(TWITTER_USERNAME)
username_field.send_keys(Keys.RETURN)
time.sleep(2)

password_field = driver.find_element(By.NAME, "password")
password_field.send_keys(TWITTER_PASSWORD)
password_field.send_keys(Keys.RETURN)
time.sleep(5)

# === Post the tweet ===
tweet_box = driver.find_element(By.CSS_SELECTOR, "div[aria-label='Tweet text']")
tweet_box.click()
tweet_box.send_keys(tweet_text)
time.sleep(1)

tweet_button = driver.find_element(By.XPATH, "//div[@data-testid='tweetButtonInline']")
tweet_button.click()
time.sleep(3)

print("✅ Tweet posted!")
driver.quit()
