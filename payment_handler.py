import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from datetime import datetime

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

async def handle_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    
    # Check if user is banned
    db_user = db.get_user(user.id)
    if db_user and db_user.is_banned:
        await message.reply_text(
            "❌ Your account is currently banned due to expired subscription.\n\n"
            "Please make a new payment and submit the proof. Your submission will be reviewed manually."
        )
        return
    
    if message.photo:
        # Get the highest resolution photo
        photo = message.photo[-1]
        file = await photo.get_file()
        
        # Save the file
        filename = f"{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(UPLOADS_DIR, filename)
        await file.download_to_drive(file_path)
        
        # Store payment info in user context
        context.user_data['payment_proof_path'] = file_path
        context.user_data['payment_date'] = datetime.now()
        
        # Ask for full name
        await message.reply_text(
            "📝 Please type your full name exactly as it appears on the payment receipt:"
        )
        context.user_data['awaiting_name'] = True
        
    else:
        await message.reply_text("📸 Please send a clear screenshot of your payment receipt.")

async def handle_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    user = update.effective_user
    
    if not full_name:
        await update.message.reply_text("Please provide your full name.")
        return
    
    # Get payment proof path from context
    proof_path = context.user_data.get('payment_proof_path', '')
    
    # Update or create user in database
    db_user = db.get_user(user.id)
    if db_user:
        db.update_user(user.id, {
            'full_name': full_name,
            'payment_proof_path': proof_path,
            'is_approved': False,
            'is_banned': False
        })
    else:
        db.add_user({
            'user_id': user.id,
            'username': user.username,
            'full_name': full_name,
            'phone_number': '',
            'is_approved': False,
            'is_banned': False,
            'payment_proof_path': proof_path
        })
    
    # Notify admin with approval buttons
    try:
        admin_text = (
            f"🆕 New Payment Submission:\n\n"
            f"👤 User: @{user.username}\n"
            f"📛 Name: {full_name}\n"
            f"🆔 ID: {user.id}\n"
            f"📅 Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to admin
        await context.bot.send_message(
            chat_id=context.bot_data['admin_id'],
            text=admin_text,
            reply_markup=reply_markup
        )
        
        # Confirm to user
        await update.message.reply_text(
            "✅ Thank you! Your payment details have been received.\n\n"
            "📋 Your submission is now under review. You will receive a notification "
            "once it's approved (usually within 24 hours).\n\n"
            "Please be patient while we verify your payment."
        )
        
    except Exception as e:
        print(f"Error in admin notification: {e}")
        await update.message.reply_text(
            "✅ Payment details received! However, there was an issue notifying the admin.\n"
            "Please wait for manual review. You will be notified once approved."
        )
    
    # Clear context
    context.user_data['awaiting_name'] = False
    if 'payment_proof_path' in context.user_data:
        del context.user_data['payment_proof_path']