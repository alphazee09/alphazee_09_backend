import os
import uuid
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename
from src.utils.helpers import allowed_file, sanitize_filename, get_file_size_mb

# Optional AWS S3 support
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

def get_file_extension(filename):
    """Get file extension"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def generate_unique_filename(original_filename):
    """Generate unique filename while preserving extension"""
    extension = get_file_extension(original_filename)
    unique_name = str(uuid.uuid4())
    return f"{unique_name}.{extension}" if extension else unique_name

def upload_file(file, folder='uploads'):
    """Upload file to configured storage (local or S3)"""
    if not file or file.filename == '':
        raise ValueError("No file provided")
    
    if not allowed_file(file.filename):
        raise ValueError("File type not allowed")
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
    if file_size > max_size:
        raise ValueError(f"File too large. Maximum size is {get_file_size_mb(max_size):.1f}MB")
    
    # Generate unique filename
    original_filename = sanitize_filename(file.filename)
    unique_filename = generate_unique_filename(original_filename)
    
    # Use S3 if configured, otherwise local storage
    if _is_s3_configured():
        return _upload_to_s3(file, folder, unique_filename)
    else:
        return _upload_to_local(file, folder, unique_filename)

def delete_file(file_url):
    """Delete file from storage"""
    if not file_url:
        return True
    
    if _is_s3_configured() and file_url.startswith('https://'):
        return _delete_from_s3(file_url)
    else:
        return _delete_from_local(file_url)

def _is_s3_configured():
    """Check if S3 is configured"""
    return (S3_AVAILABLE and 
            current_app.config.get('AWS_ACCESS_KEY_ID') and 
            current_app.config.get('AWS_SECRET_ACCESS_KEY') and 
            current_app.config.get('AWS_S3_BUCKET'))

def _upload_to_s3(file, folder, filename):
    """Upload file to AWS S3"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config.get('AWS_S3_REGION', 'us-east-1')
        )
        
        bucket = current_app.config['AWS_S3_BUCKET']
        key = f"{folder}/{filename}"
        
        # Upload file
        s3_client.upload_fileobj(
            file,
            bucket,
            key,
            ExtraArgs={
                'ContentType': file.content_type or 'application/octet-stream'
            }
        )
        
        # Return public URL
        return f"https://{bucket}.s3.amazonaws.com/{key}"
        
    except ClientError as e:
        current_app.logger.error(f"S3 upload error: {str(e)}")
        raise Exception("Failed to upload file to S3")

def _upload_to_local(file, folder, filename):
    """Upload file to local storage"""
    try:
        # Create upload directory
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        full_folder_path = os.path.join(upload_folder, folder)
        os.makedirs(full_folder_path, exist_ok=True)
        
        # Save file
        file_path = os.path.join(full_folder_path, filename)
        file.save(file_path)
        
        # Return relative URL
        return f"/uploads/{folder}/{filename}"
        
    except Exception as e:
        current_app.logger.error(f"Local upload error: {str(e)}")
        raise Exception("Failed to upload file locally")

def _delete_from_s3(file_url):
    """Delete file from AWS S3"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config.get('AWS_S3_REGION', 'us-east-1')
        )
        
        bucket = current_app.config['AWS_S3_BUCKET']
        
        # Extract key from URL
        if f"https://{bucket}.s3.amazonaws.com/" in file_url:
            key = file_url.replace(f"https://{bucket}.s3.amazonaws.com/", "")
            s3_client.delete_object(Bucket=bucket, Key=key)
            return True
        
        return False
        
    except ClientError as e:
        current_app.logger.error(f"S3 delete error: {str(e)}")
        return False

def _delete_from_local(file_url):
    """Delete file from local storage"""
    try:
        # Convert URL to file path
        if file_url.startswith('/uploads/'):
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            file_path = os.path.join(upload_folder, file_url[9:])  # Remove '/uploads/' prefix
            
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        
        return False
        
    except Exception as e:
        current_app.logger.error(f"Local delete error: {str(e)}")
        return False

def get_file_info(file_path):
    """Get file information"""
    try:
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            return {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'exists': True
            }
        else:
            return {'exists': False}
    except Exception:
        return {'exists': False}

def create_upload_directories():
    """Create necessary upload directories"""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    directories = [
        'avatars',
        'identity/front_id',
        'identity/back_id', 
        'identity/signatures',
        'projects',
        'contracts',
        'temp'
    ]
    
    for directory in directories:
        full_path = os.path.join(upload_folder, directory)
        os.makedirs(full_path, exist_ok=True)

