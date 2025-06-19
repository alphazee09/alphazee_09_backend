import uuid
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from src.extensions import db

class ProjectType(db.Model):
    __tablename__ = 'project_types'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    color = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    projects = db.relationship('Project', backref='project_type', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    project_type_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project_types.id'))
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    features = db.Column(db.Text)
    timeline = db.Column(db.String(50))
    budget_range = db.Column(db.String(50))
    estimated_cost = db.Column(db.Numeric(10, 2))
    final_cost = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default='submitted')
    priority = db.Column(db.String(10), default='medium')
    progress = db.Column(db.Integer, default=0)
    start_date = db.Column(db.Date)
    deadline = db.Column(db.Date)
    completion_date = db.Column(db.Date)
    assigned_to = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    milestones = db.relationship('ProjectMilestone', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    files = db.relationship('ProjectFile', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='project', lazy='dynamic')
    contracts = db.relationship('Contract', backref='project', lazy='dynamic')
    payments = db.relationship('Payment', backref='project', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='project', lazy='dynamic')
    
    def __repr__(self):
        return f'<Project {self.name}>'
    
    @property
    def status_display(self):
        status_map = {
            'submitted': 'Submitted',
            'reviewing': 'Under Review',
            'approved': 'Approved',
            'in-progress': 'In Progress',
            'review': 'In Review',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
            'on-hold': 'On Hold'
        }
        return status_map.get(self.status, self.status.title())
    
    @property
    def priority_display(self):
        priority_map = {
            'low': 'Low',
            'medium': 'Medium',
            'high': 'High',
            'urgent': 'Urgent'
        }
        return priority_map.get(self.priority, self.priority.title())
    
    def to_dict(self, include_relations=False):
        data = {
            'id': str(self.id),
            'client_id': str(self.client_id),
            'project_type_id': str(self.project_type_id) if self.project_type_id else None,
            'name': self.name,
            'description': self.description,
            'features': self.features,
            'timeline': self.timeline,
            'budget_range': self.budget_range,
            'estimated_cost': float(self.estimated_cost) if self.estimated_cost else None,
            'final_cost': float(self.final_cost) if self.final_cost else None,
            'status': self.status,
            'status_display': self.status_display,
            'priority': self.priority,
            'priority_display': self.priority_display,
            'progress': self.progress,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'assigned_to': str(self.assigned_to) if self.assigned_to else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_relations:
            # Include client info
            if self.client:
                data['client'] = {
                    'id': str(self.client.id),
                    'name': self.client.full_name,
                    'email': self.client.email,
                    'company': self.client.company
                }
            
            # Include project type
            if self.project_type:
                data['project_type'] = self.project_type.to_dict()
            
            # Include assigned user
            if self.assigned_user:
                data['assigned_user'] = {
                    'id': str(self.assigned_user.id),
                    'name': self.assigned_user.full_name,
                    'email': self.assigned_user.email
                }
            
            # Include milestones
            data['milestones'] = [milestone.to_dict() for milestone in self.milestones.order_by('order_index')]
            
            # Include file count
            data['file_count'] = self.files.count()
            
            # Include message count
            data['message_count'] = self.messages.count()
        
        return data

class ProjectMilestone(db.Model):
    __tablename__ = 'project_milestones'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    completion_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')
    payment_percentage = db.Column(db.Numeric(5, 2), default=0)
    order_index = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    payments = db.relationship('Payment', backref='milestone', lazy='dynamic')
    
    @property
    def status_display(self):
        status_map = {
            'pending': 'Pending',
            'in-progress': 'In Progress',
            'completed': 'Completed',
            'overdue': 'Overdue'
        }
        return status_map.get(self.status, self.status.title())
    
    @property
    def is_overdue(self):
        if self.due_date and self.status not in ['completed']:
            return date.today() > self.due_date
        return False
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'status': self.status,
            'status_display': self.status_display,
            'payment_percentage': float(self.payment_percentage) if self.payment_percentage else 0,
            'order_index': self.order_index,
            'is_overdue': self.is_overdue,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ProjectFile(db.Model):
    __tablename__ = 'project_files'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=False)
    uploaded_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger)
    file_type = db.Column(db.String(100))
    mime_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    uploader = db.relationship('User', backref='uploaded_files')
    
    @property
    def file_size_mb(self):
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'uploaded_by': str(self.uploaded_by) if self.uploaded_by else None,
            'uploader_name': self.uploader.full_name if self.uploader else None,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_size_mb': self.file_size_mb,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'description': self.description,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

