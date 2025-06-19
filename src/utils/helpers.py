import bcrypt
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps
from flask import jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from src.models.user import User

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Check if password matches the hashed password"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_random_password(length=12):
    """Generate a random password"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_token(length=32):
    """Generate a random token"""
    return secrets.token_urlsafe(length)

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def client_or_admin_required(f):
    """Decorator to require client or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or user.role not in ['client', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def validate_email(email):
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Basic phone validation"""
    import re
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    # Check if it's between 8 and 15 digits
    return 8 <= len(digits_only) <= 15

def format_currency(amount, currency='OMR'):
    """Format currency amount"""
    return f"{amount:,.2f} {currency}"

def calculate_tax(amount, tax_rate=0.05):
    """Calculate tax amount"""
    return amount * tax_rate

def generate_invoice_number():
    """Generate unique invoice number"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = secrets.token_hex(3).upper()
    return f"INV-{timestamp}-{random_suffix}"

def generate_contract_number():
    """Generate unique contract number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    random_suffix = secrets.token_hex(4).upper()
    return f"CON-{timestamp}-{random_suffix}"

def paginate_query(query, page, per_page=20):
    """Paginate a SQLAlchemy query"""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < total
    }

def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_size_mb(file_size_bytes):
    """Convert file size from bytes to MB"""
    return file_size_bytes / (1024 * 1024)

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    import re
    # Remove any path components
    filename = filename.split('/')[-1].split('\\')[-1]
    # Remove or replace unsafe characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:255-len(ext)-1] + '.' + ext if ext else name[:255]
    
    return filename


def log_activity(user_id, action, entity_type, entity_id, old_values=None, new_values=None, ip_address=None, user_agent=None):
    """Log user activity"""
    from src.models.communication import ActivityLog
    from src.extensions import db
    
    try:
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.session.add(activity)
        db.session.commit()
        
        return activity
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Log activity error: {str(e)}")
        return None

def validate_password_strength(password):
    """Validate password strength"""
    import re
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    return True, "Password is strong"

