import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WELCOME_MESSAGE, PHONE_NUMBER, WELCOME_VIDEO_URL
from database import db
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Subscription checker
async def check_subscriptions():
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        users = db.get_all_users()
        now = datetime.now()
        
        for user in users:
            if user.is_approved and user.subscription_end:
                # Check if subscription expires in 1 day
                if user.subscription_end - timedelta(days=1) <= now < user.subscription_end:
                    try:
                        await bot.send_message(
                            chat_id=user.user_id,
                            text="⚠️ Your subscription expires in 24 hours! Please renew to maintain access."
                        )
                        print(f"Sent warning to user {user.user_id}")
                    except Exception as e:
                        print(f"Warning failed for user {user.user_id}: {e}")
                
                # Check if subscription expired
                elif now >= user.subscription_end:
                    try:
                        # Remove from channel
                        await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user.user_id)
                        # Update database
                        db.update_user(user.user_id, {'is_approved': False, 'is_banned': True})
                        # Notify user
                        await bot.send_message(
                            chat_id=user.user_id,
                            text="❌ Your subscription has expired. You've been removed from the premium channel."
                        )
                        print(f"Banned expired user {user.user_id}")
                    except Exception as e:
                        print(f"Banning failed for user {user.user_id}: {e}")
    except Exception as e:
        print(f"Subscription check error: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: asyncio.run(check_subscriptions()), 'interval', hours=1)
    scheduler.start()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user is banned
    db_user = db.get_user(user.id)
    if db_user and db_user.is_banned:
        await update.message.reply_text("❌ Your account is banned. Make a new payment to regain access.")
        return
    
    if not db_user:
        db.add_user({
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name or '',
            'is_approved': False,
            'is_banned': False
        })
    
    # Send welcome video
    try:
        await update.message.reply_video(
            video=WELCOME_VIDEO_URL,
            caption="🎥 Welcome to our premium service! Watch this video to learn more."
        )
    except:
        await update.message.reply_text("🎉 Welcome to our premium service!")
    
    # Send welcome message with phone number
    await update.message.reply_text(WELCOME_MESSAGE.format(PHONE_NUMBER))
    await update.message.reply_text(f"📞 Phone: `{PHONE_NUMBER}`", parse_mode='Markdown')
    
    # Instructions
    instructions = "💳 Send a screenshot of your payment to begin the verification process."
    await update.message.reply_text(instructions)

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if update.message.photo:
        # Save payment screenshot
        photo = update.message.photo[-1]
        file = await photo.get_file()
        filename = f"{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(UPLOADS_DIR, filename)
        await file.download_to_drive(file_path)
        
        # Store file path and ask for name
        context.user_data['proof_path'] = file_path
        await update.message.reply_text("📝 Please type your full name exactly as on the receipt:")
        context.user_data['awaiting_name'] = True
    else:
        await update.message.reply_text("Please send a clear screenshot of your payment.")

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = update.message.text
    
    # Update user with name and proof path
    db_user = db.get_user(user.id)
    proof_path = context.user_data.get('proof_path', '')
    
    if db_user:
        db.update_user(user.id, {'full_name': full_name, 'payment_proof_path': proof_path})
    else:
        db.add_user({
            'user_id': user.id,
            'username': user.username,
            'full_name': full_name,
            'payment_proof_path': proof_path,
            'is_approved': False,
            'is_banned': False
        })
    
    # Send screenshot to admin with approval buttons
    try:
        # Send the actual screenshot to admin
        with open(proof_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo,
                caption=f"🆕 Payment Submission:\nUser: @{user.username}\nName: {full_name}\nID: {user.user_id}"
            )
    except:
        # Fallback if file doesn't exist
        admin_text = f"🆕 Payment Submission:\nUser: @{user.username}\nName: {full_name}\nID: {user.user_id}\n📸 Screenshot saved but couldn't send file."
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    
    # Send approval buttons
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text="Approve or reject this payment:",
        reply_markup=reply_markup
    )
    
    await update.message.reply_text("✅ Payment received! Your submission is under review. You'll be notified once approved.")
    context.user_data['awaiting_name'] = False

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Check if admin
    if query.from_user.id != ADMIN_ID:
        await query.message.reply_text("❌ Only admin can approve/reject users.")
        return
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    target_user = db.get_user(user_id)
    
    if not target_user:
        await query.edit_message_text("❌ User not found.")
        return
    
    if action == 'approve':
        # Calculate subscription end (30 days from now)
        subscription_end = datetime.now() + timedelta(days=30)
        db.update_user(user_id, {
            'is_approved': True,
            'is_banned': False,
            'subscription_end': subscription_end
        })
        
        # Add to channel with invite link
        try:
            # First try to add directly
            await context.bot.add_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            
            # Send channel invite link to user
            chat = await context.bot.get_chat(CHANNEL_ID)
            invite_link = await chat.export_invite_link()
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Your payment has been approved! You now have 30 days access.\n\n"
                     f"Join our private channel here: {invite_link}\n\n"
                     f"Subscription ends: {subscription_end.strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception as e:
            print(f"Channel add error: {e}")
            # Fallback: just notify user
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 Your payment has been approved! You now have 30 days access.\n\n"
                     "The admin will add you to the private channel shortly."
            )
        
        await query.edit_message_text(
            f"✅ User approved!\n"
            f"Subscription until: {subscription_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"User: @{target_user.username}"
        )
        
    elif action == 'reject':
        db.update_user(user_id, {'is_approved': False, 'is_banned': True})
        
        # Remove from channel if they were added
        try:
            await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        except:
            pass
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Your payment was rejected. Please check your credentials and try again."
            )
        except:
            pass
        
        await query.edit_message_text(f"❌ User @{target_user.username} rejected and banned.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_name'):
        await handle_name(update, context)
    else:
        # Check if user has active subscription
        user = update.effective_user
        db_user = db.get_user(user.id)
        
        if db_user and db_user.is_subscription_active():
            # User is approved and active
            remaining = db_user.subscription_end - datetime.now()
            days_left = remaining.days
            await update.message.reply_text(
                f"✅ Your subscription is active!\n"
                f"Days remaining: {days_left}\n"
                f"Expires: {db_user.subscription_end.strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            await update.message.reply_text("Send /start to begin or send a payment screenshot.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    users = db.get_all_users()
    active_users = [u for u in users if u.is_subscription_active()]
    pending_approvals = [u for u in users if not u.is_approved and not u.is_banned]
    banned_users = [u for u in users if u.is_banned]
    
    stats_text = f"""
📊 ADMIN STATISTICS:

👥 Total Users: {len(users)}
✅ Active Subscriptions: {len(active_users)}
⏳ Pending Approvals: {len(pending_approvals)}
🚫 Banned Users: {len(banned_users)}

Active Users:
"""
    for user in active_users:
        remaining = user.subscription_end - datetime.now()
        stats_text += f"• @{user.username} - {remaining.days} days left\n"
    
    await update.message.reply_text(stats_text)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start scheduler
    start_scheduler()
    
    print("🤖 Bot is running perfectly...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📢 Channel ID: {CHANNEL_ID}")
    print("⏰ Subscription checker active (runs every hour)")
    
    application.run_polling()

if __name__ == "__main__":
    main()