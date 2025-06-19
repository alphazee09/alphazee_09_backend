import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from src.extensions import db

class Contract(db.Model):
    __tablename__ = 'contracts'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=False)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    contract_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='OMR')
    status = db.Column(db.String(20), default='draft')
    created_date = db.Column(db.Date, default=date.today)
    sent_date = db.Column(db.Date)
    signed_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    completion_date = db.Column(db.Date)
    terms_and_conditions = db.Column(db.Text)
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    signatures = db.relationship('ContractSignature', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='contract', lazy='dynamic')
    
    @property
    def status_display(self):
        status_map = {
            'draft': 'Draft',
            'sent': 'Sent for Signing',
            'signed': 'Signed',
            'active': 'Active',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
            'expired': 'Expired'
        }
        return status_map.get(self.status, self.status.title())
    
    @property
    def is_expired(self):
        if self.expiry_date and self.status not in ['signed', 'active', 'completed', 'cancelled']:
            return date.today() > self.expiry_date
        return False
    
    def to_dict(self, include_content=False):
        data = {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'client_id': str(self.client_id),
            'contract_number': self.contract_number,
            'title': self.title,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'status_display': self.status_display,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'sent_date': self.sent_date.isoformat() if self.sent_date else None,
            'signed_date': self.signed_date.isoformat() if self.signed_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'is_expired': self.is_expired,
            'created_by': str(self.created_by) if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_content:
            data['content'] = self.content
            data['terms_and_conditions'] = self.terms_and_conditions
        
        return data

class ContractSignature(db.Model):
    __tablename__ = 'contract_signatures'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey('contracts.id'), nullable=False)
    signer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    signature_image_url = db.Column(db.String(500), nullable=False)
    signed_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    verification_status = db.Column(db.String(20), default='valid')
    
    # Relationships
    signer = db.relationship('User', backref='contract_signatures')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'contract_id': str(self.contract_id),
            'signer_id': str(self.signer_id),
            'signer_name': self.signer.full_name if self.signer else None,
            'signature_image_url': self.signature_image_url,
            'signed_at': self.signed_at.isoformat() if self.signed_at else None,
            'ip_address': self.ip_address,
            'verification_status': self.verification_status
        }

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=False)
    milestone_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project_milestones.id'))
    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey('contracts.id'))
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='OMR')
    payment_method = db.Column(db.String(50))
    payment_gateway = db.Column(db.String(50))
    transaction_id = db.Column(db.String(255))
    gateway_response = db.Column(db.JSON)
    status = db.Column(db.String(20), default='pending')
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    description = db.Column(db.Text)
    invoice_number = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def status_display(self):
        status_map = {
            'pending': 'Pending',
            'processing': 'Processing',
            'completed': 'Completed',
            'failed': 'Failed',
            'refunded': 'Refunded',
            'cancelled': 'Cancelled'
        }
        return status_map.get(self.status, self.status.title())
    
    @property
    def is_overdue(self):
        if self.due_date and self.status == 'pending':
            return date.today() > self.due_date
        return False
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'milestone_id': str(self.milestone_id) if self.milestone_id else None,
            'contract_id': str(self.contract_id) if self.contract_id else None,
            'client_id': str(self.client_id),
            'amount': float(self.amount),
            'currency': self.currency,
            'payment_method': self.payment_method,
            'payment_gateway': self.payment_gateway,
            'transaction_id': self.transaction_id,
            'status': self.status,
            'status_display': self.status_display,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_date': self.paid_date.isoformat() if self.paid_date else None,
            'description': self.description,
            'invoice_number': self.invoice_number,
            'is_overdue': self.is_overdue,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=False)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='OMR')
    status = db.Column(db.String(20), default='draft')
    issue_date = db.Column(db.Date, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date)
    description = db.Column(db.Text)
    line_items = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def status_display(self):
        status_map = {
            'draft': 'Draft',
            'sent': 'Sent',
            'paid': 'Paid',
            'overdue': 'Overdue',
            'cancelled': 'Cancelled'
        }
        return status_map.get(self.status, self.status.title())
    
    @property
    def is_overdue(self):
        if self.due_date and self.status in ['sent']:
            return date.today() > self.due_date
        return False
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'client_id': str(self.client_id),
            'invoice_number': self.invoice_number,
            'amount': float(self.amount),
            'tax_amount': float(self.tax_amount),
            'total_amount': float(self.total_amount),
            'currency': self.currency,
            'status': self.status,
            'status_display': self.status_display,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_date': self.paid_date.isoformat() if self.paid_date else None,
            'description': self.description,
            'line_items': self.line_items,
            'is_overdue': self.is_overdue,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

