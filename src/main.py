import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from src.config import config
from src.extensions import db, jwt, mail, migrate

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    
    # Import all models to ensure they are registered with SQLAlchemy
    from src.models.user import User, IdentityVerification
    from src.models.project import Project, ProjectType, ProjectMilestone, ProjectFile
    from src.models.contract import Contract, ContractSignature, Payment, Invoice
    from src.models.communication import Message, Notification, ActivityLog
    
    # Enable CORS for all routes
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Register blueprints
    from src.routes.auth import auth_bp
    from src.routes.users import users_bp
    from src.routes.projects import projects_bp
    from src.routes.contracts import contracts_bp
    from src.routes.payments import payments_bp
    from src.routes.messages import messages_bp
    from src.routes.files import files_bp
    from src.routes.admin import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(contracts_bp, url_prefix='/api/contracts')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    app.register_blueprint(files_bp, url_prefix='/api/files')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy', 'message': 'AlphaZee Backend API is running'})
    
    # Serve frontend static files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return jsonify({'message': 'AlphaZee Backend API', 'version': '1.0.0'}), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
