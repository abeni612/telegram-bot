from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import db
from datetime import datetime, timedelta

async def admin_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    target_user = db.get_user(user_id)
    
    if action == 'approve' and target_user:
        # Set NEW 30-day subscription (no continuation)
        subscription_end = datetime.now() + timedelta(days=30)
        
        db.update_user(user_id, {
            'is_approved': True,
            'is_banned': False,
            'subscription_end': subscription_end
        })
        
        # Update payment history
        user_payments = db.get_user_payments(user_id)
        if user_payments:
            latest_payment = user_payments[-1]
            # Mark as approved in payment history (you'd need to add this method to database)
        
        # Add user to channel
        try:
            await context.bot.add_chat_member(
                chat_id=context.bot_data['channel_id'],
                user_id=user_id
            )
        except Exception as e:
            print(f"Error adding user to channel: {e}")
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 Your payment has been approved! You now have 30 days access to our premium channel.\n\n"
                     "⚠️ Note: After 30 days, you must complete a new payment and approval process to continue access."
            )
        except Exception as e:
            print(f"Error notifying user: {e}")
        
        await query.edit_message_text(
            f"✅ User @{target_user.username} approved successfully!\n"
            f"New subscription until: {subscription_end.strftime('%Y-%m-%d %H:%M')}"
        )
        
    elif action == 'reject' and target_user:
        # Reject user and keep them banned
        db.update_user(user_id, {
            'is_approved': False,
            'is_banned': True
        })
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Your payment was rejected. Please check your credentials and try again, or contact support."
            )
        except Exception as e:
            print(f"Error notifying user: {e}")
        
        await query.edit_message_text(f"❌ User @{target_user.username} rejected and banned.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != context.bot_data['admin_id']:
        return
    
    users = db.get_all_users()
    active_users = [u for u in users if u.is_subscription_active()]
    pending_approvals = db.get_pending_approvals()
    banned_users = db.get_banned_users()
    
    stats_text = f"""
📊 Bot Statistics:
Total Users: {len(users)}
Active Subscriptions: {len(active_users)}
Pending Approvals: {len(pending_approvals)}
Banned Users: {len(banned_users)}

👑 Admin Commands:
/approvals - Show pending approvals
/stats - Show statistics
/banned - Show banned users
"""
    
    await update.message.reply_text(stats_text)

async def show_pending_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != context.bot_data['admin_id']:
        return
    
    pending_users = db.get_pending_approvals()
    
    if not pending_users:
        await update.message.reply_text("No pending approvals.")
        return
    
    for user in pending_users:
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"🆕 Pending Approval:\nUser: @{user.username}\nName: {user.full_name}\nID: {user.user_id}"
        
        await update.message.reply_text(text, reply_markup=reply_markup)

async def show_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != context.bot_data['admin_id']:
        return
    
    banned_users = db.get_banned_users()
    
    if not banned_users:
        await update.message.reply_text("No banned users.")
        return
    
    text = "🚫 Banned Users:\n\n"
    for user in banned_users:
        text += f"👤 @{user.username} (ID: {user.user_id})\n"
        if user.subscription_end:
            text += f"   Expired: {user.subscription_end.strftime('%Y-%m-%d')}\n"
        text += "\n"
    
    await update.message.reply_text(text)