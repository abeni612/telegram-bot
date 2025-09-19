import os
from dotenv import load_dotenv

load_dotenv()

# Safe environment variable handling
BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_ID = os.getenv('ADMIN_ID', '').strip()
CHANNEL_ID = os.getenv('CHANNEL_ID', '').strip()

# Convert ADMIN_ID to integer safely
try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0
except (ValueError, TypeError):
    ADMIN_ID = 0

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

WELCOME_MESSAGE = """
🎉 Welcome to Our Premium Service!

📞 For payments, contact: {}
💰 Payment Instructions: 
- Send payment via [Your Payment Method]
- Upload screenshot as proof
- Provide your full name exactly as on receipt

⚡️ 30 days access after verification
"""

PHONE_NUMBER = "+1234567890"  # Your phone number here
WELCOME_VIDEO_URL = "https://www.youtube.com/watch?v=nF0rqeymxmQ&pp=ugUEEgJlbg%3D%3D"  # Your YouTube video URL