from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import os
import time

# Load credentials from GitHub Secrets
username = os.environ['TWITTER_USERNAME']
password = os.environ['TWITTER_PASSWORD']

# Read the haiku to post
with open("haiku.txt", "r") as f:
    haiku = f.read()

# Set up headless browser
options = webdriver.FirefoxOptions()
options.add_argument("--headless")  # remove this line to debug
driver = webdriver.Firefox(options=options)

try:
    driver.get("https://twitter.com/login")
    time.sleep(3)

    # Login
    user_field = driver.find_element(By.NAME, "text")
    user_field.send_keys(username)
    user_field.send_keys(Keys.RETURN)
    time.sleep(2)

    pwd_field = driver.find_element(By.NAME, "password")
    pwd_field.send_keys(password)
    pwd_field.send_keys(Keys.RETURN)
    time.sleep(5)

    # Compose tweet
    tweet_box = driver.find_element(By.CSS_SELECTOR, "div[aria-label='Tweet text']")
    tweet_box.send_keys(haiku)

    tweet_button = driver.find_element(By.XPATH, "//div[@data-testid='tweetButtonInline']")
    tweet_button.click()
    print("✅ Tweet posted.")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    driver.quit()
