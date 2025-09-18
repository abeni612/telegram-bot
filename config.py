import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = os.getenv('CHANNEL_ID')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

# Welcome message configuration
WELCOME_MESSAGE = """
🎉 Welcome to Our Premium Service!

📞 For payments, contact: {}
💰 Payment Instructions: 
- Send payment via Telebirr
- Upload screenshot as proof
- Provide your full name exactly as on receipt

⚡️ 30 days access after verification
"""

PHONE_NUMBER = "0945376561 - Yohannes"  # Your phone number here