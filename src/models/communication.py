import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from src.extensions import db

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=False)
    sender_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(255))
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='general')
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    parent_message_id = db.Column(UUID(as_uuid=True), db.ForeignKey('messages.id'))
    attachments = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    parent_message = db.relationship('Message', remote_side=[id], backref='replies')
    
    @property
    def message_type_display(self):
        type_map = {
            'general': 'General',
            'update': 'Project Update',
            'feedback': 'Feedback',
            'invoice': 'Invoice',
            'milestone': 'Milestone',
            'urgent': 'Urgent'
        }
        return type_map.get(self.message_type, self.message_type.title())
    
    def to_dict(self, include_relations=False):
        data = {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'sender_id': str(self.sender_id),
            'recipient_id': str(self.recipient_id),
            'subject': self.subject,
            'content': self.content,
            'message_type': self.message_type,
            'message_type_display': self.message_type_display,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'parent_message_id': str(self.parent_message_id) if self.parent_message_id else None,
            'attachments': self.attachments,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_relations:
            # Include sender info
            if self.sender:
                data['sender'] = {
                    'id': str(self.sender.id),
                    'name': self.sender.full_name,
                    'email': self.sender.email,
                    'role': self.sender.role
                }
            
            # Include recipient info
            if self.recipient:
                data['recipient'] = {
                    'id': str(self.recipient.id),
                    'name': self.recipient.full_name,
                    'email': self.recipient.email,
                    'role': self.recipient.role
                }
            
            # Include project info
            if self.project:
                data['project'] = {
                    'id': str(self.project.id),
                    'name': self.project.name,
                    'status': self.project.status
                }
            
            # Include reply count
            data['reply_count'] = len(self.replies) if self.replies else 0
        
        return data

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    related_entity_type = db.Column(db.String(50))
    related_entity_id = db.Column(UUID(as_uuid=True))
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    action_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': str(self.related_entity_id) if self.related_entity_id else None,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'action_url': self.action_url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(UUID(as_uuid=True), nullable=False)
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id) if self.user_id else None,
            'user_name': self.user.full_name if self.user else 'System',
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': str(self.entity_id),
            'old_values': self.old_values,
            'new_values': self.new_values,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

