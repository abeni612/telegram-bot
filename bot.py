import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WELCOME_MESSAGE, PHONE_NUMBER, WELCOME_VIDEO_URL
from database import db
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Check essential variables
if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID:
    print("❌ ERROR: Missing essential environment variables!")
    print(f"BOT_TOKEN: {'Set' if BOT_TOKEN else 'Missing'}")
    print(f"ADMIN_ID: {'Set' if ADMIN_ID else 'Missing'}")
    print(f"CHANNEL_ID: {'Set' if CHANNEL_ID else 'Missing'}")
    exit(1)

print("✅ Environment variables loaded successfully")

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        print(f"User {user.id} started the bot")
        
        # Check if user is banned
        db_user = db.get_user(user.id)
        if db_user and db_user.is_banned:
            await update.message.reply_text("❌ Your account is banned. Make a new payment to regain access.")
            return
        
        # Create user if not exists
        if not db_user:
            db.add_user({
                'user_id': user.id,
                'username': user.username or '',
                'full_name': user.full_name or '',
                'is_approved': False,
                'is_banned': False
            })
        
        # Send welcome video
        try:
            await update.message.reply_video(
                video=WELCOME_VIDEO_URL,
                caption="🎥 Welcome to our premium service!"
            )
        except Exception as e:
            print(f"Video error: {e}")
            await update.message.reply_text("🎉 Welcome to our premium service!")
        
        # Send welcome message
        await update.message.reply_text(WELCOME_MESSAGE.format(PHONE_NUMBER))
        await update.message.reply_text(f"📞 Phone: `{PHONE_NUMBER}`", parse_mode='Markdown')
        await update.message.reply_text("💳 Send a screenshot of your payment to begin verification.")
        
    except Exception as e:
        print(f"Start error: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again.")

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            
    except Exception as e:
        print(f"Payment error: {e}")
        await update.message.reply_text("Error processing payment. Please try again.")

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        full_name = update.message.text
        proof_path = context.user_data.get('proof_path', '')
        
        # Update user in database
        db_user = db.get_user(user.id)
        if db_user:
            db.update_user(user.id, {
                'full_name': full_name,
                'payment_proof_path': proof_path
            })
        else:
            db.add_user({
                'user_id': user.id,
                'username': user.username or '',
                'full_name': full_name,
                'payment_proof_path': proof_path,
                'is_approved': False,
                'is_banned': False
            })
        
        # Send screenshot to admin
        try:
            with open(proof_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=photo,
                    caption=f"🆕 Payment from: @{user.username or 'No username'}\nName: {full_name}\nID: {user.id}"
                )
        except:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🆕 Payment from: @{user.username or 'No username'}\nName: {full_name}\nID: {user.id}"
            )
        
        # Send approval buttons to admin
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Approve or reject this payment:",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text("✅ Payment received! Waiting for admin approval.")
        context.user_data['awaiting_name'] = False
        
    except Exception as e:
        print(f"Name error: {e}")
        await update.message.reply_text("Error processing your information. Please try again.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        # Verify admin
        if query.from_user.id != ADMIN_ID:
            await query.message.reply_text("❌ Only admin can do this.")
            return
        
        action, user_id = query.data.split('_')
        user_id = int(user_id)
        target_user = db.get_user(user_id)
        
        if not target_user:
            await query.edit_message_text("❌ User not found.")
            return
        
        if action == 'approve':
            # Set 30-day subscription
            subscription_end = datetime.now() + timedelta(days=30)
            db.update_user(user_id, {
                'is_approved': True,
                'is_banned': False,
                'subscription_end': subscription_end
            })
            
            # Add to channel
            try:
                await context.bot.add_chat_member(
                    chat_id=CHANNEL_ID,
                    user_id=user_id
                )
                channel_info = "✅ Added to private channel"
            except Exception as e:
                print(f"Channel error: {e}")
                channel_info = "⚠️ Could not add to channel automatically"
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 Payment approved! You have 30 days access.\n{channel_info}\nExpires: {subscription_end.strftime('%Y-%m-%d')}"
                )
            except:
                pass
            
            await query.edit_message_text(f"✅ Approved user @{target_user.username}")
            
        elif action == 'reject':
            db.update_user(user_id, {'is_approved': False, 'is_banned': True})
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Payment rejected. Please check details and try again."
                )
            except:
                pass
            
            await query.edit_message_text(f"❌ Rejected user @{target_user.username}")
            
    except Exception as e:
        print(f"Callback error: {e}")
        await query.edit_message_text("Error processing request.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('awaiting_name'):
            await handle_name(update, context)
        else:
            await update.message.reply_text("Send /start to begin or send payment screenshot.")
    except Exception as e:
        print(f"Message error: {e}")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            return
        
        users = db.get_all_users()
        active = len([u for u in users if u.is_subscription_active()])
        pending = len([u for u in users if not u.is_approved and not u.is_banned])
        
        stats = f"📊 Stats:\nUsers: {len(users)}\nActive: {active}\nPending: {pending}"
        await update.message.reply_text(stats)
    except Exception as e:
        print(f"Stats error: {e}")

def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", admin_stats))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.PHOTO, handle_payment))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("✅ Bot starting...")
        print(f"🤖 Bot Token: {'✓' if BOT_TOKEN else '✗'}")
        print(f"👑 Admin ID: {ADMIN_ID}")
        print(f"📢 Channel ID: {CHANNEL_ID}")
        
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        print("Please check your BOT_TOKEN and environment variables")

if __name__ == "__main__":
    main()