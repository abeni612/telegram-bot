import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WELCOME_MESSAGE, PHONE_NUMBER
from database import db
from payment_handler import handle_payment_screenshot, handle_full_name
from admin import admin_approval_callback, admin_stats, show_pending_approvals, show_banned_users
from user_management import start_scheduler
from aiohttp import web

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user is banned
    db_user = db.get_user(user.id)
    if db_user and db_user.is_banned:
        await update.message.reply_text(
            "❌ Your account is currently banned due to expired subscription.\n\n"
            "To regain access, please:\n"
            "1. Make a new payment\n"
            "2. Send screenshot proof\n"
            "3. Wait for manual approval\n\n"
            "Each subscription lasts 30 days and requires new approval after expiration."
        )
        return
    
    # Check if user exists
    if not db_user:
        db.add_user({
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'phone_number': '',
            'is_approved': False,
            'is_banned': False
        })
    
    # Create click-to-copy phone number
    phone_text = f"📞 Phone: `{PHONE_NUMBER}`"
    
    # Send welcome message
    welcome_text = WELCOME_MESSAGE.format(PHONE_NUMBER)
    
    # Send message (video can be added later)
    await update.message.reply_text(welcome_text, parse_mode='Markdown')
    await update.message.reply_text(phone_text, parse_mode='Markdown')
    
    # Instructions for payment
    instructions = """
💳 **How to Pay:**
1. Send payment to the phone number above
2. Take a clear screenshot of the payment confirmation
3. Send the screenshot to this bot
4. Provide your full name when asked

✅ You'll get access within 24 hours after verification
"""
    await update.message.reply_text(instructions, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if context.user_data.get('awaiting_name'):
        await handle_full_name(update, context)
    else:
        # Check if user has active subscription
        db_user = db.get_user(user.id)
        if db_user and db_user.is_subscription_active():
            await update.message.reply_text("I'm here to help! Send /start to see options.")
        else:
            await update.message.reply_text("Please complete the payment process to access premium features. Send /start to begin.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")

def main():
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Store admin and channel IDs in bot data
    application.bot_data['admin_id'] = ADMIN_ID
    application.bot_data['channel_id'] = CHANNEL_ID
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("approvals", show_pending_approvals))
    application.add_handler(CommandHandler("banned", show_banned_users))
    application.add_handler(CallbackQueryHandler(admin_approval_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_payment_screenshot))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # Start subscription scheduler
    start_scheduler()
    
    # For Render: Start web server for health checks
    if os.getenv('RENDER', None):
        app = web.Application()
        app.router.add_get('/health', health_check)
        
        # Run both bot and web server
        import threading
        
        def run_web():
            web.run_app(app, port=8000, host='0.0.0.0')
        
        web_thread = threading.Thread(target=run_web)
        web_thread.daemon = True
        web_thread.start()
        
        print("Bot and web server starting...")
        application.run_polling()
    else:
        # Local development
        print("Bot is running...")
        application.run_polling()

if __name__ == "__main__":
    main()