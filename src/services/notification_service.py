from flask import current_app
from src.extensions import db
from src.models.communication import Notification

def create_notification(user_id, title, message, type, related_entity_type=None, related_entity_id=None, action_url=None):
    """Create a new notification for a user"""
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            action_url=action_url
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return notification
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create notification error: {str(e)}")
        return None

def create_project_notification(project, title, message, type, action_url=None):
    """Create notification for project client"""
    return create_notification(
        user_id=project.client_id,
        title=title,
        message=message,
        type=type,
        related_entity_type='project',
        related_entity_id=project.id,
        action_url=action_url
    )

def create_payment_notification(payment, title, message, type, action_url=None):
    """Create notification for payment client"""
    return create_notification(
        user_id=payment.client_id,
        title=title,
        message=message,
        type=type,
        related_entity_type='payment',
        related_entity_id=payment.id,
        action_url=action_url
    )

def create_contract_notification(contract, title, message, type, action_url=None):
    """Create notification for contract client"""
    return create_notification(
        user_id=contract.client_id,
        title=title,
        message=message,
        type=type,
        related_entity_type='contract',
        related_entity_id=contract.id,
        action_url=action_url
    )

def create_admin_notification(title, message, type, related_entity_type=None, related_entity_id=None, action_url=None):
    """Create notification for all admin users"""
    from src.models.user import User
    
    try:
        admin_users = User.query.filter_by(role='admin', is_active=True).all()
        
        notifications = []
        for admin in admin_users:
            notification = create_notification(
                user_id=admin.id,
                title=title,
                message=message,
                type=type,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                action_url=action_url
            )
            if notification:
                notifications.append(notification)
        
        return notifications
        
    except Exception as e:
        current_app.logger.error(f"Create admin notification error: {str(e)}")
        return []

def mark_notifications_read(user_id, notification_type=None, related_entity_id=None):
    """Mark notifications as read for a user"""
    try:
        query = Notification.query.filter_by(user_id=user_id, is_read=False)
        
        if notification_type:
            query = query.filter_by(type=notification_type)
        
        if related_entity_id:
            query = query.filter_by(related_entity_id=related_entity_id)
        
        notifications = query.all()
        
        for notification in notifications:
            notification.is_read = True
            notification.read_at = db.func.now()
        
        db.session.commit()
        
        return len(notifications)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Mark notifications read error: {str(e)}")
        return 0

def delete_old_notifications(days=30):
    """Delete notifications older than specified days"""
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_notifications = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).all()
        
        count = len(old_notifications)
        
        for notification in old_notifications:
            db.session.delete(notification)
        
        db.session.commit()
        
        return count
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete old notifications error: {str(e)}")
        return 0

def get_notification_counts(user_id):
    """Get notification counts for a user"""
    try:
        total = Notification.query.filter_by(user_id=user_id).count()
        unread = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        
        return {
            'total': total,
            'unread': unread,
            'read': total - unread
        }
        
    except Exception as e:
        current_app.logger.error(f"Get notification counts error: {str(e)}")
        return {
            'total': 0,
            'unread': 0,
            'read': 0
        }

