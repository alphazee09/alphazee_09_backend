from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from src.extensions import db
from src.models.user import User, UserProfile, IdentityVerification
from src.utils.helpers import admin_required, validate_email, validate_phone, paginate_query
from src.services.file_service import upload_file, delete_file

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user.to_dict()
        
        # Include profile data
        if user.profile:
            user_data['profile'] = user.profile.to_dict()
        else:
            # Create default profile if doesn't exist
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()
            user_data['profile'] = profile.to_dict()
        
        return jsonify({'profile': user_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update user basic info
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'company' in data:
            user.company = data['company']
        if 'phone' in data:
            if data['phone'] and not validate_phone(data['phone']):
                return jsonify({'error': 'Invalid phone number format'}), 400
            user.phone = data['phone']
        
        # Update or create profile
        profile = user.profile
        if not profile:
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)
        
        if 'bio' in data:
            profile.bio = data['bio']
        if 'website' in data:
            profile.website = data['website']
        if 'timezone' in data:
            profile.timezone = data['timezone']
        if 'notification_preferences' in data:
            profile.notification_preferences = data['notification_preferences']
        
        user.updated_at = datetime.utcnow()
        profile.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Return updated profile
        user_data = user.to_dict()
        user_data['profile'] = profile.to_dict()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': user_data
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update profile error: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@users_bp.route('/avatar', methods=['POST'])
@jwt_required()
def upload_avatar():
    """Upload user avatar"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if 'avatar' not in request.files:
            return jsonify({'error': 'No avatar file provided'}), 400
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Upload file
        file_url = upload_file(file, 'avatars')
        
        # Update profile
        profile = user.profile
        if not profile:
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)
        
        # Delete old avatar if exists
        if profile.avatar_url:
            try:
                delete_file(profile.avatar_url)
            except Exception as e:
                current_app.logger.warning(f"Failed to delete old avatar: {str(e)}")
        
        profile.avatar_url = file_url
        profile.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Avatar uploaded successfully',
            'avatar_url': file_url
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Avatar upload error: {str(e)}")
        return jsonify({'error': 'Failed to upload avatar'}), 500

@users_bp.route('/identity-verification', methods=['POST'])
@jwt_required()
def submit_identity_verification():
    """Submit identity verification documents"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if already verified
        if user.identity_verification and user.identity_verification.verification_status == 'verified':
            return jsonify({'error': 'Identity already verified'}), 400
        
        # Check required files
        required_files = ['front_id', 'back_id', 'signature']
        for file_key in required_files:
            if file_key not in request.files:
                return jsonify({'error': f'{file_key} file is required'}), 400
        
        # Upload files
        front_id_url = upload_file(request.files['front_id'], 'identity/front_id')
        back_id_url = upload_file(request.files['back_id'], 'identity/back_id')
        signature_url = upload_file(request.files['signature'], 'identity/signatures')
        
        # Create or update identity verification
        identity_verification = user.identity_verification
        if identity_verification:
            # Delete old files
            try:
                delete_file(identity_verification.front_id_image_url)
                delete_file(identity_verification.back_id_image_url)
                delete_file(identity_verification.signature_image_url)
            except Exception as e:
                current_app.logger.warning(f"Failed to delete old identity files: {str(e)}")
            
            identity_verification.front_id_image_url = front_id_url
            identity_verification.back_id_image_url = back_id_url
            identity_verification.signature_image_url = signature_url
            identity_verification.verification_status = 'pending'
            identity_verification.verified_at = None
            identity_verification.verified_by = None
            identity_verification.rejection_reason = None
            identity_verification.updated_at = datetime.utcnow()
        else:
            identity_verification = IdentityVerification(
                user_id=user.id,
                front_id_image_url=front_id_url,
                back_id_image_url=back_id_url,
                signature_image_url=signature_url
            )
            db.session.add(identity_verification)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Identity verification submitted successfully',
            'verification': identity_verification.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Identity verification error: {str(e)}")
        return jsonify({'error': 'Failed to submit identity verification'}), 500

@users_bp.route('/identity-verification', methods=['GET'])
@jwt_required()
def get_identity_verification():
    """Get identity verification status"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.identity_verification:
            return jsonify({'verification': None}), 200
        
        return jsonify({
            'verification': user.identity_verification.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get identity verification error: {str(e)}")
        return jsonify({'error': 'Failed to get identity verification'}), 500

@users_bp.route('/', methods=['GET'])
@admin_required
def list_users():
    """List all users (admin only)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        role = request.args.get('role', '')
        status = request.args.get('status', '')
        
        query = User.query
        
        # Apply filters
        if search:
            query = query.filter(
                db.or_(
                    User.email.ilike(f'%{search}%'),
                    User.first_name.ilike(f'%{search}%'),
                    User.last_name.ilike(f'%{search}%'),
                    User.company.ilike(f'%{search}%')
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if status == 'active':
            query = query.filter(User.is_active == True)
        elif status == 'inactive':
            query = query.filter(User.is_active == False)
        elif status == 'verified':
            query = query.filter(User.is_verified == True)
        elif status == 'unverified':
            query = query.filter(User.is_verified == False)
        
        # Order by creation date
        query = query.order_by(User.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert users to dict
        users_data = [user.to_dict() for user in result['items']]
        
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
        current_app.logger.error(f"List users error: {str(e)}")
        return jsonify({'error': 'Failed to list users'}), 500

@users_bp.route('/<user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Get user by ID (admin only)"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user.to_dict()
        
        # Include profile data
        if user.profile:
            user_data['profile'] = user.profile.to_dict()
        
        # Include identity verification
        if user.identity_verification:
            user_data['identity_verification'] = user.identity_verification.to_dict()
        
        return jsonify({'user': user_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get user error: {str(e)}")
        return jsonify({'error': 'Failed to get user'}), 500

@users_bp.route('/<user_id>/status', methods=['PUT'])
@admin_required
def update_user_status(user_id):
    """Update user status (admin only)"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'is_verified' in data:
            user.is_verified = data['is_verified']
        
        if 'role' in data and data['role'] in ['client', 'admin']:
            user.role = data['role']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'User status updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update user status error: {str(e)}")
        return jsonify({'error': 'Failed to update user status'}), 500

