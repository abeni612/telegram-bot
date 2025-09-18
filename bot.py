import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WELCOME_MESSAGE, PHONE_NUMBER
from database import db
from payment_handler import handle_payment_screenshot, handle_full_name
from admin import admin_approval_callback, admin_stats, show_pending_approvals, show_banned_users
from user_management import start_scheduler

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user is banned
    db_user = db.get_user(user.id)
    if db_user and db_user.is_banned:
        await update.message.reply_text("❌ Your account is banned. Make a new payment and submit proof.")
        return
    
    if not db_user:
        db.add_user({
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'is_approved': False,
            'is_banned': False
        })
    
    phone_text = f"📞 Phone: `{PHONE_NUMBER}`"
    await update.message.reply_text(WELCOME_MESSAGE.format(PHONE_NUMBER), parse_mode='Markdown')
    await update.message.reply_text(phone_text, parse_mode='Markdown')
    
    instructions = "💳 Send payment screenshot to begin approval process."
    await update.message.reply_text(instructions)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_name'):
        await handle_full_name(update, context)
    else:
        await update.message.reply_text("Send /start to begin payment process.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Error: {context.error}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
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
    
    start_scheduler()
    print("Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()