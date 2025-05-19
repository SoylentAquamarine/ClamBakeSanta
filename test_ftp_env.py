import os

print("🔎 Checking FTP environment variables...\n")

ftp_host = os.getenv("FTP_HOST")
ftp_user = os.getenv("FTP_USER")
ftp_pass = os.getenv("FTP_PASS")

if not ftp_host:
    print("❌ FTP_HOST is not set.")
else:
    print(f"✅ FTP_HOST = {ftp_host}")

if not ftp_user:
    print("❌ FTP_USER is not set.")
else:
    print(f"✅ FTP_USER = {ftp_user}")

if not ftp_pass:
    print("❌ FTP_PASS is not set.")
else:
    print("✅ FTP_PASS is set (value not printed for security)")

print("\n✅ Environment variable check complete.")
