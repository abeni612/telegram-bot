from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import db
from datetime import datetime, timedelta

async def admin_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Check if user is admin
    if query.from_user.id != context.bot_data['admin_id']:
        await query.message.reply_text("❌ Only the admin can approve or reject users.")
        return
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    target_user = db.get_user(user_id)
    
    if not target_user:
        await query.edit_message_text("❌ User not found in database.")
        return
    
    if action == 'approve':
        # Set NEW 30-day subscription
        subscription_end = datetime.now() + timedelta(days=30)
        
        db.update_user(user_id, {
            'is_approved': True,
            'is_banned': False,
            'subscription_end': subscription_end
        })
        
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
            f"Subscription until: {subscription_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"User ID: {user_id}"
        )
        
    elif action == 'reject':
        # Reject user and mark as banned
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
        
        await query.edit_message_text(
            f"❌ User @{target_user.username} rejected and banned.\n"
            f"User ID: {user_id}"
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != context.bot_data['admin_id']:
        await update.message.reply_text("❌ Only the admin can view statistics.")
        return
    
    users = db.get_all_users()
    active_users = [u for u in users if u.is_subscription_active()]
    pending_approvals = db.get_pending_approvals()
    banned_users = db.get_banned_users()
    
    stats_text = f"""
📊 Bot Statistics:
├─ Total Users: {len(users)}
├─ Active Subscriptions: {len(active_users)}
├─ Pending Approvals: {len(pending_approvals)}
└─ Banned Users: {len(banned_users)}

👑 Admin Commands:
├─ /approvals - Show pending approvals
├─ /stats - Show statistics
└─ /banned - Show banned users
"""
    
    await update.message.reply_text(stats_text)

async def show_pending_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != context.bot_data['admin_id']:
        await update.message.reply_text("❌ Only the admin can view pending approvals.")
        return
    
    pending_users = db.get_pending_approvals()
    
    if not pending_users:
        await update.message.reply_text("✅ No pending approvals.")
        return
    
    await update.message.reply_text(f"📋 Found {len(pending_users)} pending approval(s):")
    
    for user in pending_users:
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"🆕 Pending Approval:\n"
            f"├─ User: @{user.username}\n"
            f"├─ Name: {user.full_name}\n"
            f"├─ ID: {user.user_id}\n"
            f"└─ Submitted: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        
        await update.message.reply_text(text, reply_markup=reply_markup)

async def show_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != context.bot_data['admin_id']:
        await update.message.reply_text("❌ Only the admin can view banned users.")
        return
    
    banned_users = db.get_banned_users()
    
    if not banned_users:
        await update.message.reply_text("✅ No banned users.")
        return
    
    text = "🚫 Banned Users:\n\n"
    for user in banned_users:
        expired_text = f"Expired: {user.subscription_end.strftime('%Y-%m-%d')}" if user.subscription_end else "No subscription data"
        text += f"👤 @{user.username} (ID: {user.user_id})\n   {expired_text}\n\n"
    
    await update.message.reply_text(text)