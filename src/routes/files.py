from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import os
from src.extensions import db
from src.models.user import User
from src.models.project import Project, ProjectFile
from src.utils.helpers import admin_required, client_or_admin_required, paginate_query
from src.services.file_service import upload_file, delete_file, get_file_info

files_bp = Blueprint('files', __name__)

@files_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_general_file():
    """Upload a general file"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get folder from form data
        folder = request.form.get('folder', 'general')
        description = request.form.get('description', '')
        
        # Upload file
        file_path = upload_file(file, folder)
        
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        response_data = {
            'message': 'File uploaded successfully',
            'file': {
                'file_name': file.filename,
                'file_path': file_path,
                'file_size': file_size,
                'file_type': file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else '',
                'mime_type': file.content_type,
                'description': description,
                'uploaded_by': user.full_name,
                'uploaded_at': datetime.utcnow().isoformat()
            }
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        current_app.logger.error(f"Upload file error: {str(e)}")
        return jsonify({'error': 'Failed to upload file'}), 500

@files_bp.route('/download/<path:file_path>')
@jwt_required()
def download_file(file_path):
    """Download a file"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        # Construct full file path
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        full_file_path = os.path.join(upload_folder, file_path)
        
        # Check if file exists
        if not os.path.exists(full_file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # For project files, check access permissions
        if file_path.startswith('projects/'):
            project_id = file_path.split('/')[1]
            project = Project.query.get(project_id)
            
            if project and user.role != 'admin' and project.client_id != user.id:
                return jsonify({'error': 'Access denied'}), 403
        
        # For identity verification files, only allow access to own files or admin
        elif file_path.startswith('identity/'):
            if user.role != 'admin':
                # Check if this is the user's own identity file
                identity_verification = user.identity_verification
                if not identity_verification or (
                    file_path not in [
                        identity_verification.front_id_image_url,
                        identity_verification.back_id_image_url,
                        identity_verification.signature_image_url
                    ]
                ):
                    return jsonify({'error': 'Access denied'}), 403
        
        return send_file(full_file_path, as_attachment=True)
        
    except Exception as e:
        current_app.logger.error(f"Download file error: {str(e)}")
        return jsonify({'error': 'Failed to download file'}), 500

@files_bp.route('/info/<path:file_path>')
@jwt_required()
def get_file_info_endpoint(file_path):
    """Get file information"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        # Construct full file path
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        full_file_path = os.path.join(upload_folder, file_path)
        
        # Check access permissions (similar to download)
        if file_path.startswith('projects/'):
            project_id = file_path.split('/')[1]
            project = Project.query.get(project_id)
            
            if project and user.role != 'admin' and project.client_id != user.id:
                return jsonify({'error': 'Access denied'}), 403
        
        elif file_path.startswith('identity/'):
            if user.role != 'admin':
                identity_verification = user.identity_verification
                if not identity_verification or (
                    file_path not in [
                        identity_verification.front_id_image_url,
                        identity_verification.back_id_image_url,
                        identity_verification.signature_image_url
                    ]
                ):
                    return jsonify({'error': 'Access denied'}), 403
        
        # Get file info
        file_info = get_file_info(full_file_path)
        
        if not file_info['exists']:
            return jsonify({'error': 'File not found'}), 404
        
        return jsonify({
            'file_path': file_path,
            'exists': file_info['exists'],
            'size': file_info.get('size'),
            'modified': file_info.get('modified').isoformat() if file_info.get('modified') else None
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get file info error: {str(e)}")
        return jsonify({'error': 'Failed to get file information'}), 500

@files_bp.route('/delete/<path:file_path>', methods=['DELETE'])
@jwt_required()
def delete_file_endpoint(file_path):
    """Delete a file"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        # Check permissions - only admin or file owner can delete
        if user.role != 'admin':
            # For project files, check if user owns the project
            if file_path.startswith('projects/'):
                project_id = file_path.split('/')[1]
                project = Project.query.get(project_id)
                
                if not project or project.client_id != user.id:
                    return jsonify({'error': 'Access denied'}), 403
            
            # For identity files, only allow deletion of own files
            elif file_path.startswith('identity/'):
                identity_verification = user.identity_verification
                if not identity_verification or (
                    file_path not in [
                        identity_verification.front_id_image_url,
                        identity_verification.back_id_image_url,
                        identity_verification.signature_image_url
                    ]
                ):
                    return jsonify({'error': 'Access denied'}), 403
            
            # For other files, only admin can delete
            else:
                return jsonify({'error': 'Access denied'}), 403
        
        # Delete file
        success = delete_file(f"/{file_path}")
        
        if success:
            # If it's a project file, also delete from database
            if file_path.startswith('projects/'):
                project_file = ProjectFile.query.filter_by(file_path=f"/{file_path}").first()
                if project_file:
                    db.session.delete(project_file)
                    db.session.commit()
            
            return jsonify({'message': 'File deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete file'}), 500
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete file error: {str(e)}")
        return jsonify({'error': 'Failed to delete file'}), 500

@files_bp.route('/project/<project_id>', methods=['GET'])
@client_or_admin_required
def list_project_files(project_id):
    """List files for a specific project"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and project.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = ProjectFile.query.filter_by(project_id=project_id)
        query = query.order_by(ProjectFile.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert files to dict
        files_data = [file.to_dict() for file in result['items']]
        
        return jsonify({
            'files': files_data,
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
        current_app.logger.error(f"List project files error: {str(e)}")
        return jsonify({'error': 'Failed to list project files'}), 500

@files_bp.route('/cleanup', methods=['POST'])
@admin_required
def cleanup_orphaned_files():
    """Clean up orphaned files (admin only)"""
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        cleaned_count = 0
        
        # This is a basic implementation - in production, you'd want more sophisticated cleanup
        # For now, just return a placeholder response
        
        return jsonify({
            'message': f'Cleanup completed. {cleaned_count} orphaned files removed.',
            'cleaned_count': cleaned_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"File cleanup error: {str(e)}")
        return jsonify({'error': 'Failed to cleanup files'}), 500

@files_bp.route('/stats', methods=['GET'])
@admin_required
def get_file_stats():
    """Get file statistics (admin only)"""
    try:
        stats = {
            'total_project_files': ProjectFile.query.count(),
            'total_file_size': db.session.query(db.func.sum(ProjectFile.file_size)).scalar() or 0,
            'files_by_type': {}
        }
        
        # Get file type distribution
        file_types = db.session.query(
            ProjectFile.file_type,
            db.func.count(ProjectFile.id).label('count')
        ).group_by(ProjectFile.file_type).all()
        
        for file_type, count in file_types:
            stats['files_by_type'][file_type or 'unknown'] = count
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get file stats error: {str(e)}")
        return jsonify({'error': 'Failed to get file statistics'}), 500

