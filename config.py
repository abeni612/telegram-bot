import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = os.getenv('CHANNEL_ID')
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
WELCOME_VIDEO_URL = "https://youtu.be/nF0rqeymxmQ?si=pNNlXP-lMxW3d8xl"  # Replace with your actual YouTube video URL