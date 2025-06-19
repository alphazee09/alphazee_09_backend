from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timedelta
import uuid
from src.extensions import db
from src.models.user import User, UserProfile, UserSession
from src.utils.helpers import hash_password, check_password, generate_random_password, generate_token, validate_email, validate_phone
from src.services.email_service import send_welcome_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email'].lower()).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 409
        
        # Validate phone if provided
        if data.get('phone') and not validate_phone(data['phone']):
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        # Generate password if not provided (for auto-registration)
        password = data.get('password')
        auto_generated_password = False
        if not password:
            password = generate_random_password()
            auto_generated_password = True
        elif len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Create new user
        user = User(
            email=data['email'].lower(),
            password_hash=hash_password(password),
            first_name=data['first_name'],
            last_name=data['last_name'],
            company=data.get('company'),
            phone=data.get('phone'),
            verification_token=generate_token()
        )
        
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Create user profile
        profile = UserProfile(
            user_id=user.id,
            timezone=data.get('timezone', 'UTC')
        )
        
        db.session.add(profile)
        db.session.commit()
        
        # Send welcome email
        try:
            send_welcome_email(user, password if auto_generated_password else None)
        except Exception as e:
            current_app.logger.error(f"Failed to send welcome email: {str(e)}")
        
        # Create access token
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'auto_generated_password': auto_generated_password
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(email=data['email'].lower()).first()
        if not user or not check_password(data['password'], user.password_hash):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Check if user is active
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        # Create session
        session_token = generate_token()
        session = UserSession(
            user_id=user.id,
            session_token=session_token,
            expires_at=datetime.utcnow() + timedelta(days=30),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.add(session)
        db.session.commit()
        
        # Create JWT tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session_token
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    try:
        current_user_id = get_jwt_identity()
        session_token = request.json.get('session_token') if request.json else None
        
        # Deactivate session if provided
        if session_token:
            session = UserSession.query.filter_by(
                user_id=current_user_id,
                session_token=session_token
            ).first()
            if session:
                session.is_active = False
                db.session.commit()
        
        return jsonify({'message': 'Logout successful'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 404
        
        new_access_token = create_access_token(identity=str(user.id))
        
        return jsonify({
            'access_token': new_access_token
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 500

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        
        user = User.query.filter_by(email=data['email'].lower()).first()
        if not user:
            # Don't reveal if email exists or not
            return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200
        
        # Generate reset token
        reset_token = generate_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        
        db.session.commit()
        
        # Send reset email
        try:
            send_password_reset_email(user, reset_token)
        except Exception as e:
            current_app.logger.error(f"Failed to send reset email: {str(e)}")
        
        return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password reset request error: {str(e)}")
        return jsonify({'error': 'Password reset request failed'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        
        required_fields = ['token', 'new_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        if len(data['new_password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Find user with valid reset token
        user = User.query.filter_by(reset_token=data['token']).first()
        if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
            return jsonify({'error': 'Invalid or expired reset token'}), 400
        
        # Update password
        user.password_hash = hash_password(data['new_password'])
        user.reset_token = None
        user.reset_token_expires = None
        
        # Deactivate all sessions
        UserSession.query.filter_by(user_id=user.id).update({'is_active': False})
        
        db.session.commit()
        
        return jsonify({'message': 'Password reset successful'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password reset error: {str(e)}")
        return jsonify({'error': 'Password reset failed'}), 500

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Verify email with token"""
    try:
        data = request.get_json()
        
        if not data.get('token'):
            return jsonify({'error': 'Verification token is required'}), 400
        
        user = User.query.filter_by(verification_token=data['token']).first()
        if not user:
            return jsonify({'error': 'Invalid verification token'}), 400
        
        user.is_verified = True
        user.verification_token = None
        
        db.session.commit()
        
        return jsonify({'message': 'Email verified successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Email verification error: {str(e)}")
        return jsonify({'error': 'Email verification failed'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        required_fields = ['current_password', 'new_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        if len(data['new_password']) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Verify current password
        if not check_password(data['current_password'], user.password_hash):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Update password
        user.password_hash = hash_password(data['new_password'])
        
        # Deactivate all other sessions
        UserSession.query.filter(
            UserSession.user_id == user.id,
            UserSession.session_token != request.json.get('session_token')
        ).update({'is_active': False})
        
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password change error: {str(e)}")
        return jsonify({'error': 'Password change failed'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user information"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user.to_dict()
        
        # Include profile data if exists
        if user.profile:
            user_data['profile'] = user.profile.to_dict()
        
        # Include identity verification status
        if user.identity_verification:
            user_data['identity_verification'] = {
                'status': user.identity_verification.verification_status,
                'verified_at': user.identity_verification.verified_at.isoformat() if user.identity_verification.verified_at else None
            }
        
        return jsonify({'user': user_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get current user error: {str(e)}")
        return jsonify({'error': 'Failed to get user information'}), 500

