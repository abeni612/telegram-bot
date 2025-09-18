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
        
        # Store payment history
        db.add_payment_history({
            'user_id': user.id,
            'payment_date': datetime.now()
        })
        
        # Update or create user
        db_user = db.get_user(user.id)
        if db_user:
            db.update_user(user.id, {
                'payment_proof_path': file_path
            })
        else:
            db.add_user({
                'user_id': user.id,
                'username': user.username,
                'full_name': '',
                'phone_number': '',
                'is_approved': False,
                'is_banned': False,
                'payment_proof_path': file_path
            })
        
        # Ask for full name
        await message.reply_text(
            "📝 Please type your full name exactly as it appears on the payment receipt:"
        )
        context.user_data['awaiting_name'] = True
        context.user_data['proof_path'] = file_path
        
    else:
        await message.reply_text("Please send a clear screenshot of your payment.")

async def handle_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text
    user = update.effective_user
    
    # Update user in database
    db_user = db.get_user(user.id)
    if db_user:
        db.update_user(user.id, {'full_name': full_name})
    else:
        db.add_user({
            'user_id': user.id,
            'username': user.username,
            'full_name': full_name,
            'phone_number': '',
            'is_approved': False,
            'is_banned': False,
            'payment_proof_path': context.user_data.get('proof_path', '')
        })
    
    # Notify admin
    from bot import application
    admin_text = f"🆕 New Payment Submission:\n\nUser: @{user.username}\nName: {full_name}\nUser ID: {user.id}"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await application.bot.send_message(
        chat_id=application.bot_data['admin_id'],
        text=admin_text,
        reply_markup=reply_markup
    )
    
    await update.message.reply_text(
        "✅ Payment details received! Your submission is under review. "
        "You'll be notified once approved (usually within 24 hours)."
    )
    
    context.user_data['awaiting_name'] = False