from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date, timedelta
from src.extensions import db
from src.models.user import User, IdentityVerification
from src.models.project import Project, ProjectType, ProjectMilestone
from src.models.contract import Contract, Payment, Invoice
from src.models.communication import Message, Notification, ActivityLog
from src.utils.helpers import admin_required, paginate_query, log_activity
from src.services.email_service import send_email
from src.services.notification_service import create_notification, delete_old_notifications

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def get_admin_dashboard():
    """Get admin dashboard statistics"""
    try:
        # Get date ranges
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # User statistics
        total_users = User.query.filter_by(role='client').count()
        new_users_week = User.query.filter(
            User.role == 'client',
            User.created_at >= week_ago
        ).count()
        verified_users = User.query.join(IdentityVerification).filter(
            User.role == 'client',
            IdentityVerification.verification_status == 'verified'
        ).count()
        
        # Project statistics
        total_projects = Project.query.count()
        active_projects = Project.query.filter(
            Project.status.in_(['approved', 'in-progress'])
        ).count()
        completed_projects = Project.query.filter_by(status='completed').count()
        new_projects_week = Project.query.filter(
            Project.created_at >= week_ago
        ).count()
        
        # Revenue statistics
        total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.status == 'completed'
        ).scalar() or 0
        
        monthly_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.status == 'completed',
            Payment.paid_date >= month_ago
        ).scalar() or 0
        
        pending_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.status == 'pending'
        ).scalar() or 0
        
        # Contract statistics
        active_contracts = Contract.query.filter_by(status='active').count()
        pending_signatures = Contract.query.filter_by(status='sent').count()
        
        # Recent activity
        recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
        recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(5).all()
        recent_messages = Message.query.order_by(Message.created_at.desc()).limit(5).all()
        
        # Overdue items
        overdue_payments = Payment.query.filter(
            Payment.status == 'pending',
            Payment.due_date < today
        ).count()
        
        expired_contracts = Contract.query.filter(
            Contract.status.in_(['sent']),
            Contract.expiry_date < today
        ).count()
        
        dashboard_data = {
            'users': {
                'total': total_users,
                'new_this_week': new_users_week,
                'verified': verified_users,
                'verification_rate': round((verified_users / total_users * 100) if total_users > 0 else 0, 1)
            },
            'projects': {
                'total': total_projects,
                'active': active_projects,
                'completed': completed_projects,
                'new_this_week': new_projects_week,
                'completion_rate': round((completed_projects / total_projects * 100) if total_projects > 0 else 0, 1)
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': float(monthly_revenue),
                'pending': float(pending_revenue),
                'currency': 'OMR'
            },
            'contracts': {
                'active': active_contracts,
                'pending_signatures': pending_signatures
            },
            'alerts': {
                'overdue_payments': overdue_payments,
                'expired_contracts': expired_contracts
            },
            'recent_activity': {
                'projects': [project.to_dict() for project in recent_projects],
                'payments': [payment.to_dict() for payment in recent_payments],
                'messages': [message.to_dict(include_relations=True) for message in recent_messages]
            }
        }
        
        return jsonify({'dashboard': dashboard_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get admin dashboard error: {str(e)}")
        return jsonify({'error': 'Failed to get dashboard data'}), 500

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    """Get all users with filtering and pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        role = request.args.get('role', '')
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        verification_status = request.args.get('verification_status', '')
        
        query = User.query
        
        # Apply filters
        if role:
            query = query.filter(User.role == role)
        
        if status == 'active':
            query = query.filter(User.is_active == True)
        elif status == 'inactive':
            query = query.filter(User.is_active == False)
        
        if search:
            query = query.filter(
                db.or_(
                    User.first_name.ilike(f'%{search}%'),
                    User.last_name.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%'),
                    User.company.ilike(f'%{search}%')
                )
            )
        
        if verification_status:
            query = query.join(IdentityVerification, isouter=True).filter(
                IdentityVerification.verification_status == verification_status
            )
        
        # Order by creation date
        query = query.order_by(User.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert users to dict with additional info
        users_data = []
        for user in result['items']:
            user_data = user.to_dict()
            
            # Add project count
            user_data['project_count'] = Project.query.filter_by(client_id=user.id).count()
            
            # Add verification status
            if user.identity_verification:
                user_data['verification_status'] = user.identity_verification.verification_status
            else:
                user_data['verification_status'] = 'not_submitted'
            
            users_data.append(user_data)
        
        return jsonify({
            'users': users_data,
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
        current_app.logger.error(f"Get all users error: {str(e)}")
        return jsonify({'error': 'Failed to get users'}), 500

@admin_bp.route('/users/<user_id>', methods=['GET'])
@admin_required
def get_user_details(user_id):
    """Get detailed user information"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user.to_dict()
        
        # Add related data
        user_data['projects'] = [project.to_dict() for project in user.projects.order_by(Project.created_at.desc()).limit(10)]
        user_data['project_count'] = user.projects.count()
        
        # Add payment history
        payments = Payment.query.filter_by(client_id=user.id).order_by(Payment.created_at.desc()).limit(10).all()
        user_data['recent_payments'] = [payment.to_dict() for payment in payments]
        
        # Add message count
        user_data['message_count'] = Message.query.filter(
            db.or_(Message.sender_id == user.id, Message.recipient_id == user.id)
        ).count()
        
        # Add identity verification details
        if user.identity_verification:
            user_data['identity_verification'] = user.identity_verification.to_dict()
        
        return jsonify({'user': user_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get user details error: {str(e)}")
        return jsonify({'error': 'Failed to get user details'}), 500

@admin_bp.route('/users/<user_id>/status', methods=['PUT'])
@admin_required
def update_user_status(user_id):
    """Update user status (activate/deactivate)"""
    try:
        current_user_id = get_jwt_identity()
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        is_active = data.get('is_active')
        
        if is_active is None:
            return jsonify({'error': 'is_active field is required'}), 400
        
        old_status = user.is_active
        user.is_active = is_active
        user.updated_at = datetime.utcnow()
        
        # Log activity
        log_activity(
            user_id=current_user_id,
            action='update_user_status',
            entity_type='user',
            entity_id=user.id,
            old_values={'is_active': old_status},
            new_values={'is_active': is_active},
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.commit()
        
        # Send notification to user
        status_text = 'activated' if is_active else 'deactivated'
        create_notification(
            user_id=user.id,
            title=f"Account {status_text}",
            message=f"Your account has been {status_text} by an administrator.",
            type='account_status'
        )
        
        return jsonify({
            'message': f'User {status_text} successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update user status error: {str(e)}")
        return jsonify({'error': 'Failed to update user status'}), 500

@admin_bp.route('/users/<user_id>/verification', methods=['PUT'])
@admin_required
def update_verification_status(user_id):
    """Update user identity verification status"""
    try:
        current_user_id = get_jwt_identity()
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        verification = user.identity_verification
        if not verification:
            return jsonify({'error': 'No identity verification found for this user'}), 404
        
        data = request.get_json()
        new_status = data.get('verification_status')
        rejection_reason = data.get('rejection_reason')
        
        if not new_status:
            return jsonify({'error': 'verification_status is required'}), 400
        
        if new_status not in ['pending', 'verified', 'rejected']:
            return jsonify({'error': 'Invalid verification status'}), 400
        
        old_status = verification.verification_status
        verification.verification_status = new_status
        verification.verified_at = datetime.utcnow() if new_status == 'verified' else None
        verification.verified_by = current_user_id if new_status == 'verified' else None
        
        if new_status == 'rejected' and rejection_reason:
            verification.rejection_reason = rejection_reason
        
        # Log activity
        log_activity(
            user_id=current_user_id,
            action='update_verification_status',
            entity_type='identity_verification',
            entity_id=verification.id,
            old_values={'verification_status': old_status},
            new_values={'verification_status': new_status, 'rejection_reason': rejection_reason},
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.commit()
        
        # Send notification to user
        if new_status == 'verified':
            create_notification(
                user_id=user.id,
                title="Identity Verified",
                message="Your identity has been successfully verified. You can now sign contracts.",
                type='verification_approved'
            )
        elif new_status == 'rejected':
            create_notification(
                user_id=user.id,
                title="Identity Verification Rejected",
                message=f"Your identity verification was rejected. Reason: {rejection_reason or 'No reason provided'}",
                type='verification_rejected'
            )
        
        return jsonify({
            'message': f'Verification status updated to {new_status}',
            'verification': verification.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update verification status error: {str(e)}")
        return jsonify({'error': 'Failed to update verification status'}), 500

@admin_bp.route('/project-types', methods=['GET'])
@admin_required
def get_project_types():
    """Get all project types"""
    try:
        project_types = ProjectType.query.order_by(ProjectType.name).all()
        return jsonify({
            'project_types': [pt.to_dict() for pt in project_types]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get project types error: {str(e)}")
        return jsonify({'error': 'Failed to get project types'}), 500

@admin_bp.route('/project-types', methods=['POST'])
@admin_required
def create_project_type():
    """Create new project type"""
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        
        project_type = ProjectType(
            name=data['name'],
            description=data.get('description'),
            icon=data.get('icon'),
            color=data.get('color')
        )
        
        db.session.add(project_type)
        db.session.commit()
        
        return jsonify({
            'message': 'Project type created successfully',
            'project_type': project_type.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create project type error: {str(e)}")
        return jsonify({'error': 'Failed to create project type'}), 500

@admin_bp.route('/project-types/<type_id>', methods=['PUT'])
@admin_required
def update_project_type(type_id):
    """Update project type"""
    try:
        project_type = ProjectType.query.get(type_id)
        if not project_type:
            return jsonify({'error': 'Project type not found'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            project_type.name = data['name']
        if 'description' in data:
            project_type.description = data['description']
        if 'icon' in data:
            project_type.icon = data['icon']
        if 'color' in data:
            project_type.color = data['color']
        if 'is_active' in data:
            project_type.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Project type updated successfully',
            'project_type': project_type.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update project type error: {str(e)}")
        return jsonify({'error': 'Failed to update project type'}), 500

@admin_bp.route('/activity-logs', methods=['GET'])
@admin_required
def get_activity_logs():
    """Get system activity logs"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        action = request.args.get('action', '')
        entity_type = request.args.get('entity_type', '')
        user_id = request.args.get('user_id', '')
        
        query = ActivityLog.query
        
        # Apply filters
        if action:
            query = query.filter(ActivityLog.action == action)
        
        if entity_type:
            query = query.filter(ActivityLog.entity_type == entity_type)
        
        if user_id:
            query = query.filter(ActivityLog.user_id == user_id)
        
        # Order by creation date
        query = query.order_by(ActivityLog.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert logs to dict
        logs_data = [log.to_dict() for log in result['items']]
        
        return jsonify({
            'activity_logs': logs_data,
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
        current_app.logger.error(f"Get activity logs error: {str(e)}")
        return jsonify({'error': 'Failed to get activity logs'}), 500

@admin_bp.route('/system/cleanup', methods=['POST'])
@admin_required
def system_cleanup():
    """Perform system cleanup tasks"""
    try:
        data = request.get_json()
        cleanup_type = data.get('type', 'notifications')
        days = data.get('days', 30)
        
        if cleanup_type == 'notifications':
            deleted_count = delete_old_notifications(days)
            message = f"Deleted {deleted_count} old notifications"
        else:
            return jsonify({'error': 'Invalid cleanup type'}), 400
        
        return jsonify({
            'message': message,
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"System cleanup error: {str(e)}")
        return jsonify({'error': 'Failed to perform system cleanup'}), 500

@admin_bp.route('/system/broadcast', methods=['POST'])
@admin_required
def broadcast_message():
    """Send broadcast message to all users"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        title = data.get('title')
        message = data.get('message')
        user_role = data.get('user_role', 'all')  # 'all', 'client', 'admin'
        
        if not title or not message:
            return jsonify({'error': 'Title and message are required'}), 400
        
        # Get target users
        query = User.query.filter_by(is_active=True)
        
        if user_role != 'all':
            query = query.filter_by(role=user_role)
        
        users = query.all()
        
        # Create notifications for all users
        notification_count = 0
        for user in users:
            notification = create_notification(
                user_id=user.id,
                title=title,
                message=message,
                type='broadcast'
            )
            if notification:
                notification_count += 1
        
        # Log activity
        log_activity(
            user_id=current_user_id,
            action='broadcast_message',
            entity_type='system',
            entity_id=current_user_id,
            new_values={
                'title': title,
                'message': message,
                'user_role': user_role,
                'recipient_count': notification_count
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return jsonify({
            'message': f'Broadcast sent to {notification_count} users',
            'recipient_count': notification_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Broadcast message error: {str(e)}")
        return jsonify({'error': 'Failed to send broadcast message'}), 500

