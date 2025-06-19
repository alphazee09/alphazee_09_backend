from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from src.extensions import db
from src.models.user import User
from src.models.project import Project
from src.models.communication import Message, Notification
from src.utils.helpers import admin_required, client_or_admin_required, paginate_query
from src.services.notification_service import create_notification

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/', methods=['GET'])
@client_or_admin_required
def get_messages():
    """Get messages (filtered by user role and project access)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        project_id = request.args.get('project_id', '')
        message_type = request.args.get('type', '')
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        # Build query based on user role
        if user.role == 'admin':
            # Admin can see all messages
            query = Message.query
        else:
            # Client can only see messages where they are sender or recipient
            query = Message.query.filter(
                db.or_(
                    Message.sender_id == user.id,
                    Message.recipient_id == user.id
                )
            )
        
        # Apply filters
        if project_id:
            # Verify user has access to this project
            project = Project.query.get(project_id)
            if project and (user.role == 'admin' or project.client_id == user.id):
                query = query.filter(Message.project_id == project_id)
            else:
                return jsonify({'error': 'Access denied to this project'}), 403
        
        if message_type:
            query = query.filter(Message.message_type == message_type)
        
        if unread_only:
            query = query.filter(Message.is_read == False, Message.recipient_id == user.id)
        
        # Only show top-level messages (not replies)
        query = query.filter(Message.parent_message_id.is_(None))
        
        # Order by creation date
        query = query.order_by(Message.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert messages to dict with relations
        messages_data = [message.to_dict(include_relations=True) for message in result['items']]
        
        return jsonify({
            'messages': messages_data,
            'pagination': {
                'total': result['total'],
                'page': result['page'],
                'per_page': result['per_page'],
                'pages': result['pages'],
                'has_prev': result['has_prev'],
                'has_next': result['has_next']
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get messages error: {str(e)}")
        return jsonify({'error': 'Failed to get messages'}), 500

@messages_bp.route('/<message_id>', methods=['GET'])
@client_or_admin_required
def get_message(message_id):
    """Get message by ID with replies"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and message.sender_id != user.id and message.recipient_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Mark as read if user is recipient
        if message.recipient_id == user.id and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.session.commit()
        
        message_data = message.to_dict(include_relations=True)
        
        # Include replies
        replies = Message.query.filter_by(parent_message_id=message_id).order_by(Message.created_at.asc()).all()
        message_data['replies'] = [reply.to_dict(include_relations=True) for reply in replies]
        
        return jsonify({'message': message_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get message error: {str(e)}")
        return jsonify({'error': 'Failed to get message'}), 500

@messages_bp.route('/', methods=['POST'])
@client_or_admin_required
def send_message():
    """Send a new message"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['project_id', 'content']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate project exists and user has access
        project = Project.query.get(data['project_id'])
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if user.role != 'admin' and project.client_id != user.id:
            return jsonify({'error': 'Access denied to this project'}), 403
        
        # Determine recipient
        if user.role == 'admin':
            # Admin sending to client
            recipient_id = project.client_id
        else:
            # Client sending to admin (find assigned admin or any admin)
            if project.assigned_to:
                recipient_id = project.assigned_to
            else:
                # Find any admin user
                admin_user = User.query.filter_by(role='admin', is_active=True).first()
                if not admin_user:
                    return jsonify({'error': 'No admin available to receive message'}), 400
                recipient_id = admin_user.id
        
        # Create message
        message = Message(
            project_id=project.id,
            sender_id=user.id,
            recipient_id=recipient_id,
            subject=data.get('subject'),
            content=data['content'],
            message_type=data.get('message_type', 'general'),
            attachments=data.get('attachments')
        )
        
        db.session.add(message)
        db.session.flush()  # Get message ID
        
        # Create notification for recipient
        create_notification(
            user_id=recipient_id,
            title=f"New message from {user.full_name}",
            message=f"You have received a new message regarding project '{project.name}'",
            type='message',
            related_entity_type='message',
            related_entity_id=message.id,
            action_url=f"/dashboard/messages/{message.id}"
        )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Message sent successfully',
            'data': message.to_dict(include_relations=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Send message error: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500

@messages_bp.route('/<message_id>/reply', methods=['POST'])
@client_or_admin_required
def reply_to_message(message_id):
    """Reply to a message"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        parent_message = Message.query.get(message_id)
        if not parent_message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and parent_message.sender_id != user.id and parent_message.recipient_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        # Determine recipient (reply to sender if current user is recipient, or to recipient if current user is sender)
        if parent_message.recipient_id == user.id:
            recipient_id = parent_message.sender_id
        else:
            recipient_id = parent_message.recipient_id
        
        # Create reply
        reply = Message(
            project_id=parent_message.project_id,
            sender_id=user.id,
            recipient_id=recipient_id,
            subject=f"Re: {parent_message.subject}" if parent_message.subject else None,
            content=data['content'],
            message_type=parent_message.message_type,
            parent_message_id=parent_message.id,
            attachments=data.get('attachments')
        )
        
        db.session.add(reply)
        db.session.flush()  # Get reply ID
        
        # Create notification for recipient
        create_notification(
            user_id=recipient_id,
            title=f"Reply from {user.full_name}",
            message=f"You have received a reply to your message regarding project '{parent_message.project.name}'",
            type='message_reply',
            related_entity_type='message',
            related_entity_id=reply.id,
            action_url=f"/dashboard/messages/{parent_message.id}"
        )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Reply sent successfully',
            'data': reply.to_dict(include_relations=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reply to message error: {str(e)}")
        return jsonify({'error': 'Failed to send reply'}), 500

@messages_bp.route('/<message_id>/read', methods=['PUT'])
@jwt_required()
def mark_message_read(message_id):
    """Mark message as read"""
    try:
        current_user_id = get_jwt_identity()
        
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Check if user is the recipient
        if message.recipient_id != current_user_id:
            return jsonify({'error': 'You can only mark your own messages as read'}), 403
        
        if not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.session.commit()
        
        return jsonify({'message': 'Message marked as read'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Mark message read error: {str(e)}")
        return jsonify({'error': 'Failed to mark message as read'}), 500

@messages_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """Get unread message count for current user"""
    try:
        current_user_id = get_jwt_identity()
        
        unread_count = Message.query.filter_by(
            recipient_id=current_user_id,
            is_read=False
        ).count()
        
        return jsonify({'unread_count': unread_count}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get unread count error: {str(e)}")
        return jsonify({'error': 'Failed to get unread count'}), 500

@messages_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get notifications for current user"""
    try:
        current_user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        query = Notification.query.filter_by(user_id=current_user_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        query = query.order_by(Notification.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert notifications to dict
        notifications_data = [notification.to_dict() for notification in result['items']]
        
        return jsonify({
            'notifications': notifications_data,
            'pagination': {
                'total': result['total'],
                'page': result['page'],
                'per_page': result['per_page'],
                'pages': result['pages'],
                'has_prev': result['has_prev'],
                'has_next': result['has_next']
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get notifications error: {str(e)}")
        return jsonify({'error': 'Failed to get notifications'}), 500

@messages_bp.route('/notifications/<notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        current_user_id = get_jwt_identity()
        
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        # Check if user owns this notification
        if notification.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.session.commit()
        
        return jsonify({'message': 'Notification marked as read'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Mark notification read error: {str(e)}")
        return jsonify({'error': 'Failed to mark notification as read'}), 500

@messages_bp.route('/notifications/unread-count', methods=['GET'])
@jwt_required()
def get_unread_notifications_count():
    """Get unread notifications count for current user"""
    try:
        current_user_id = get_jwt_identity()
        
        unread_count = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        ).count()
        
        return jsonify({'unread_count': unread_count}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get unread notifications count error: {str(e)}")
        return jsonify({'error': 'Failed to get unread notifications count'}), 500

@messages_bp.route('/notifications/mark-all-read', methods=['PUT'])
@jwt_required()
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    try:
        current_user_id = get_jwt_identity()
        
        Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        
        db.session.commit()
        
        return jsonify({'message': 'All notifications marked as read'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Mark all notifications read error: {str(e)}")
        return jsonify({'error': 'Failed to mark all notifications as read'}), 500

