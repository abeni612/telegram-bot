from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from database import db
import asyncio
from telegram import Bot
from config import BOT_TOKEN, CHANNEL_ID

bot_instance = Bot(token=BOT_TOKEN)

async def check_subscriptions():
    users = db.get_all_users()
    now = datetime.now()
    
    for user in users:
        # Check if subscription expired
        if user.is_approved and user.subscription_end and now >= user.subscription_end:
            # BAN THE USER (no automatic continuation)
            try:
                # Remove from channel
                await bot_instance.ban_chat_member(
                    chat_id=CHANNEL_ID,
                    user_id=user.user_id
                )
                
                # Update database - mark as banned and not approved
                db.update_user(user.user_id, {
                    'is_approved': False,
                    'is_banned': True
                })
                
                # Notify user
                await bot_instance.send_message(
                    chat_id=user.user_id,
                    text="❌ Your subscription has expired. You've been removed from the premium channel.\n\n"
                         "To regain access, you must make a new payment and go through the approval process again."
                )
                print(f"Banned expired user: {user.user_id}")
                
            except Exception as e:
                print(f"Error banning user {user.user_id}: {e}")
        
        # Warning 1 day before expiry
        elif user.is_approved and user.subscription_end:
            if user.subscription_end - timedelta(days=1) <= now < user.subscription_end:
                try:
                    await bot_instance.send_message(
                        chat_id=user.user_id,
                        text="⚠️ Your subscription expires in 24 hours!\n\n"
                             "After expiration, you will be automatically banned and must complete a new payment "
                             "and approval process to regain access."
                    )
                except Exception as e:
                    print(f"Error sending warning to user {user.user_id}: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: asyncio.run(check_subscriptions()),
        trigger=IntervalTrigger(hours=1),
        id='subscription_check',
        replace_existing=True
    )
    scheduler.start()