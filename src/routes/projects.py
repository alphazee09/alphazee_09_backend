from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date
from src.extensions import db
from src.models.user import User
from src.models.project import Project, ProjectType, ProjectMilestone, ProjectFile
from src.utils.helpers import admin_required, client_or_admin_required, paginate_query, generate_random_password, hash_password
from src.services.email_service import send_project_submitted_email, send_project_approved_email, send_milestone_completed_email
from src.services.file_service import upload_file, delete_file

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/types', methods=['GET'])
def get_project_types():
    """Get all active project types"""
    try:
        project_types = ProjectType.query.filter_by(is_active=True).all()
        return jsonify({
            'project_types': [pt.to_dict() for pt in project_types]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get project types error: {str(e)}")
        return jsonify({'error': 'Failed to get project types'}), 500

@projects_bp.route('/submit', methods=['POST'])
def submit_project():
    """Submit a new project (public endpoint with auto-registration)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'description', 'email', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user exists
        user = User.query.filter_by(email=data['email'].lower()).first()
        auto_created_user = False
        
        if not user:
            # Auto-create user account
            password = generate_random_password()
            user = User(
                email=data['email'].lower(),
                password_hash=hash_password(password),
                first_name=data['first_name'],
                last_name=data['last_name'],
                company=data.get('company'),
                phone=data.get('phone')
            )
            db.session.add(user)
            db.session.flush()  # Get user ID
            auto_created_user = True
        
        # Get project type
        project_type = None
        if data.get('project_type_id'):
            project_type = ProjectType.query.get(data['project_type_id'])
        
        # Create project
        project = Project(
            client_id=user.id,
            project_type_id=project_type.id if project_type else None,
            name=data['name'],
            description=data['description'],
            features=data.get('features'),
            timeline=data.get('timeline'),
            budget_range=data.get('budget_range')
        )
        
        db.session.add(project)
        db.session.commit()
        
        # Send confirmation email
        try:
            send_project_submitted_email(user, project)
        except Exception as e:
            current_app.logger.error(f"Failed to send project submission email: {str(e)}")
        
        response_data = {
            'message': 'Project submitted successfully',
            'project': project.to_dict(include_relations=True)
        }
        
        if auto_created_user:
            response_data['account_created'] = True
            response_data['message'] += '. An account has been created and login details sent to your email.'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Project submission error: {str(e)}")
        return jsonify({'error': 'Failed to submit project'}), 500

@projects_bp.route('/', methods=['GET'])
@client_or_admin_required
def get_projects():
    """Get projects (filtered by user role)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        
        # Build query based on user role
        if user.role == 'admin':
            query = Project.query
        else:
            query = Project.query.filter_by(client_id=user.id)
        
        # Apply filters
        if status:
            query = query.filter(Project.status == status)
        
        if search:
            query = query.filter(
                db.or_(
                    Project.name.ilike(f'%{search}%'),
                    Project.description.ilike(f'%{search}%')
                )
            )
        
        # Order by creation date
        query = query.order_by(Project.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert projects to dict with relations
        projects_data = [project.to_dict(include_relations=True) for project in result['items']]
        
        return jsonify({
            'projects': projects_data,
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
        current_app.logger.error(f"Get projects error: {str(e)}")
        return jsonify({'error': 'Failed to get projects'}), 500

@projects_bp.route('/<project_id>', methods=['GET'])
@client_or_admin_required
def get_project(project_id):
    """Get project by ID"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and project.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'project': project.to_dict(include_relations=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get project error: {str(e)}")
        return jsonify({'error': 'Failed to get project'}), 500

@projects_bp.route('/<project_id>/status', methods=['PUT'])
@admin_required
def update_project_status(project_id):
    """Update project status (admin only)"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        old_status = project.status
        
        # Update project fields
        if 'status' in data:
            project.status = data['status']
        
        if 'priority' in data:
            project.priority = data['priority']
        
        if 'progress' in data:
            project.progress = max(0, min(100, data['progress']))
        
        if 'estimated_cost' in data:
            project.estimated_cost = data['estimated_cost']
        
        if 'final_cost' in data:
            project.final_cost = data['final_cost']
        
        if 'start_date' in data and data['start_date']:
            project.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        
        if 'deadline' in data and data['deadline']:
            project.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date()
        
        if 'assigned_to' in data:
            project.assigned_to = data['assigned_to'] if data['assigned_to'] else None
        
        # Set completion date if status changed to completed
        if project.status == 'completed' and old_status != 'completed':
            project.completion_date = date.today()
            project.progress = 100
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send email notification if status changed to approved
        if project.status == 'approved' and old_status != 'approved':
            try:
                send_project_approved_email(project.client, project)
            except Exception as e:
                current_app.logger.error(f"Failed to send approval email: {str(e)}")
        
        return jsonify({
            'message': 'Project status updated successfully',
            'project': project.to_dict(include_relations=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update project status error: {str(e)}")
        return jsonify({'error': 'Failed to update project status'}), 500

@projects_bp.route('/<project_id>/milestones', methods=['GET'])
@client_or_admin_required
def get_project_milestones(project_id):
    """Get project milestones"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and project.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        milestones = ProjectMilestone.query.filter_by(project_id=project_id).order_by('order_index').all()
        
        return jsonify({
            'milestones': [milestone.to_dict() for milestone in milestones]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get project milestones error: {str(e)}")
        return jsonify({'error': 'Failed to get project milestones'}), 500

@projects_bp.route('/<project_id>/milestones', methods=['POST'])
@admin_required
def create_milestone(project_id):
    """Create project milestone (admin only)"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        
        # Get next order index
        max_order = db.session.query(db.func.max(ProjectMilestone.order_index)).filter_by(project_id=project_id).scalar() or 0
        
        milestone = ProjectMilestone(
            project_id=project_id,
            title=data['title'],
            description=data.get('description'),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            payment_percentage=data.get('payment_percentage', 0),
            order_index=max_order + 1
        )
        
        db.session.add(milestone)
        db.session.commit()
        
        return jsonify({
            'message': 'Milestone created successfully',
            'milestone': milestone.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create milestone error: {str(e)}")
        return jsonify({'error': 'Failed to create milestone'}), 500

@projects_bp.route('/<project_id>/milestones/<milestone_id>/complete', methods=['PUT'])
@admin_required
def complete_milestone(project_id, milestone_id):
    """Mark milestone as completed (admin only)"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        milestone = ProjectMilestone.query.filter_by(id=milestone_id, project_id=project_id).first()
        if not milestone:
            return jsonify({'error': 'Milestone not found'}), 404
        
        milestone.status = 'completed'
        milestone.completion_date = date.today()
        milestone.updated_at = datetime.utcnow()
        
        # Update project progress
        completed_milestones = ProjectMilestone.query.filter_by(project_id=project_id, status='completed').count()
        total_milestones = ProjectMilestone.query.filter_by(project_id=project_id).count()
        
        if total_milestones > 0:
            project.progress = int((completed_milestones / total_milestones) * 100)
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send milestone completion email
        try:
            send_milestone_completed_email(project.client, project, milestone)
        except Exception as e:
            current_app.logger.error(f"Failed to send milestone completion email: {str(e)}")
        
        return jsonify({
            'message': 'Milestone marked as completed',
            'milestone': milestone.to_dict(),
            'project_progress': project.progress
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Complete milestone error: {str(e)}")
        return jsonify({'error': 'Failed to complete milestone'}), 500

@projects_bp.route('/<project_id>/files', methods=['GET'])
@client_or_admin_required
def get_project_files(project_id):
    """Get project files"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and project.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        files = ProjectFile.query.filter_by(project_id=project_id).order_by(ProjectFile.created_at.desc()).all()
        
        return jsonify({
            'files': [file.to_dict() for file in files]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get project files error: {str(e)}")
        return jsonify({'error': 'Failed to get project files'}), 500

@projects_bp.route('/<project_id>/files', methods=['POST'])
@client_or_admin_required
def upload_project_file(project_id):
    """Upload project file"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and project.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Upload file
        file_path = upload_file(file, f'projects/{project_id}')
        
        # Create file record
        project_file = ProjectFile(
            project_id=project_id,
            uploaded_by=user.id,
            file_name=file.filename,
            file_path=file_path,
            file_size=len(file.read()),
            file_type=file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else '',
            mime_type=file.content_type,
            description=request.form.get('description'),
            is_public=request.form.get('is_public', 'false').lower() == 'true'
        )
        
        # Reset file pointer after reading size
        file.seek(0)
        
        db.session.add(project_file)
        db.session.commit()
        
        return jsonify({
            'message': 'File uploaded successfully',
            'file': project_file.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Upload project file error: {str(e)}")
        return jsonify({'error': 'Failed to upload file'}), 500

@projects_bp.route('/<project_id>/files/<file_id>', methods=['DELETE'])
@client_or_admin_required
def delete_project_file(project_id, file_id):
    """Delete project file"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        project_file = ProjectFile.query.filter_by(id=file_id, project_id=project_id).first()
        if not project_file:
            return jsonify({'error': 'File not found'}), 404
        
        # Check permissions (admin or file uploader)
        if user.role != 'admin' and project_file.uploaded_by != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Delete file from storage
        try:
            delete_file(project_file.file_path)
        except Exception as e:
            current_app.logger.warning(f"Failed to delete file from storage: {str(e)}")
        
        # Delete file record
        db.session.delete(project_file)
        db.session.commit()
        
        return jsonify({'message': 'File deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete project file error: {str(e)}")
        return jsonify({'error': 'Failed to delete file'}), 500

@projects_bp.route('/stats', methods=['GET'])
@admin_required
def get_project_stats():
    """Get project statistics (admin only)"""
    try:
        stats = {
            'total_projects': Project.query.count(),
            'submitted': Project.query.filter_by(status='submitted').count(),
            'in_progress': Project.query.filter_by(status='in-progress').count(),
            'completed': Project.query.filter_by(status='completed').count(),
            'cancelled': Project.query.filter_by(status='cancelled').count(),
            'total_revenue': db.session.query(db.func.sum(Project.final_cost)).filter(Project.status == 'completed').scalar() or 0,
            'estimated_revenue': db.session.query(db.func.sum(Project.estimated_cost)).filter(Project.status.in_(['approved', 'in-progress'])).scalar() or 0
        }
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get project stats error: {str(e)}")
        return jsonify({'error': 'Failed to get project statistics'}), 500

