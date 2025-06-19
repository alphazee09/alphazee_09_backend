import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from src.extensions import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default='client', nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(255))
    reset_token = db.Column(db.String(255))
    reset_token_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    identity_verification = db.relationship('IdentityVerification', backref='user', uselist=False, cascade='all, delete-orphan', foreign_keys='IdentityVerification.user_id')
    projects = db.relationship('Project', foreign_keys='Project.client_id', backref='client', lazy='dynamic')
    assigned_projects = db.relationship('Project', foreign_keys='Project.assigned_to', backref='assigned_user', lazy='dynamic')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    contracts = db.relationship('Contract', foreign_keys='Contract.client_id', backref='client', lazy='dynamic')
    created_contracts = db.relationship('Contract', foreign_keys='Contract.created_by', backref='creator', lazy='dynamic')
    payments = db.relationship('Payment', backref='client', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='client', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='user', lazy='dynamic')
    sessions = db.relationship('UserSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self, include_sensitive=False):
        data = {
            'id': str(self.id),
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'company': self.company,
            'phone': self.phone,
            'role': self.role,
            'is_verified': self.is_verified,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data.update({
                'verification_token': self.verification_token,
                'reset_token': self.reset_token,
                'reset_token_expires': self.reset_token_expires.isoformat() if self.reset_token_expires else None
            })
        
        return data

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    avatar_url = db.Column(db.String(500))
    bio = db.Column(db.Text)
    website = db.Column(db.String(255))
    timezone = db.Column(db.String(50), default='UTC')
    notification_preferences = db.Column(db.JSON, default={'email': True, 'sms': False, 'push': True})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'website': self.website,
            'timezone': self.timezone,
            'notification_preferences': self.notification_preferences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class IdentityVerification(db.Model):
    __tablename__ = 'identity_verifications'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    front_id_image_url = db.Column(db.String(500), nullable=False)
    back_id_image_url = db.Column(db.String(500), nullable=False)
    signature_image_url = db.Column(db.String(500), nullable=False)
    verification_status = db.Column(db.String(20), default='pending')
    verified_at = db.Column(db.DateTime)
    verified_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to verifier (remove this line as it's causing the conflict)
    # verifier = db.relationship('User', foreign_keys=[verified_by])
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'front_id_image_url': self.front_id_image_url,
            'back_id_image_url': self.back_id_image_url,
            'signature_image_url': self.signature_image_url,
            'verification_status': self.verification_status,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'verified_by': str(self.verified_by) if self.verified_by else None,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'session_token': self.session_token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

