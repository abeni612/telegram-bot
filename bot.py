import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WELCOME_MESSAGE, PHONE_NUMBER
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
    users = db.get_all_users()
    now = datetime.now()
    
    for user in users:
        if user.is_approved and user.subscription_end:
            # Check if subscription expires in 1 day
            if user.subscription_end - timedelta(days=1) <= now < user.subscription_end:
                try:
                    from telegram import Bot
                    bot = Bot(token=BOT_TOKEN)
                    await bot.send_message(
                        chat_id=user.user_id,
                        text="⚠️ Your subscription expires in 24 hours! Please renew to maintain access."
                    )
                except:
                    pass
            
            # Check if subscription expired
            elif now >= user.subscription_end:
                try:
                    from telegram import Bot
                    bot = Bot(token=BOT_TOKEN)
                    # Remove from channel
                    await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user.user_id)
                    # Update database
                    db.update_user(user.user_id, {'is_approved': False, 'is_banned': True})
                    # Notify user
                    await bot.send_message(
                        chat_id=user.user_id,
                        text="❌ Your subscription has expired. You've been removed from the premium channel."
                    )
                except:
                    pass

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
    
    # Notify admin
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_text = f"🆕 Payment Submission:\nUser: @{user.username}\nName: {full_name}\nID: {user.id}"
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_text,
        reply_markup=reply_markup
    )
    
    await update.message.reply_text("✅ Payment received! Your submission is under review. You'll be notified once approved.")
    context.user_data['awaiting_name'] = False

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    target_user = db.get_user(user_id)
    
    if action == 'approve' and target_user:
        # Approve user - 30 days access
        subscription_end = datetime.now() + timedelta(days=30)
        db.update_user(user_id, {
            'is_approved': True,
            'is_banned': False,
            'subscription_end': subscription_end
        })
        
        # Add to channel
        try:
            await context.bot.add_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        except:
            pass
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 Your payment has been approved! You now have 30 days access to our premium channel."
            )
        except:
            pass
        
        await query.edit_message_text(f"✅ User approved! Subscription until: {subscription_end.strftime('%Y-%m-%d')}")
        
    elif action == 'reject' and target_user:
        # Reject user
        db.update_user(user_id, {'is_approved': False, 'is_banned': True})
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Your payment was rejected. Please check your credentials and try again."
            )
        except:
            pass
        
        await query.edit_message_text("❌ User rejected.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_name'):
        await handle_name(update, context)
    else:
        await update.message.reply_text("Send /start to begin or send a payment screenshot.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    users = db.get_all_users()
    active = [u for u in users if u.is_subscription_active()]
    pending = len([u for u in users if not u.is_approved and not u.is_banned])
    
    stats = f"📊 Stats:\nTotal: {len(users)}\nActive: {len(active)}\nPending: {pending}"
    await update.message.reply_text(stats)

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
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()