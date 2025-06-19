from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date, timedelta
from src.extensions import db
from src.models.user import User, IdentityVerification
from src.models.project import Project
from src.models.contract import Contract, ContractSignature
from src.utils.helpers import admin_required, client_or_admin_required, paginate_query, generate_contract_number
from src.services.file_service import upload_file

contracts_bp = Blueprint('contracts', __name__)

@contracts_bp.route('/', methods=['GET'])
@client_or_admin_required
def get_contracts():
    """Get contracts (filtered by user role)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '')
        
        # Build query based on user role
        if user.role == 'admin':
            query = Contract.query
        else:
            query = Contract.query.filter_by(client_id=user.id)
        
        # Apply filters
        if status:
            query = query.filter(Contract.status == status)
        
        # Order by creation date
        query = query.order_by(Contract.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert contracts to dict
        contracts_data = []
        for contract in result['items']:
            contract_data = contract.to_dict()
            
            # Include project info
            if contract.project:
                contract_data['project'] = {
                    'id': str(contract.project.id),
                    'name': contract.project.name,
                    'status': contract.project.status
                }
            
            # Include client info for admin
            if user.role == 'admin' and contract.client:
                contract_data['client'] = {
                    'id': str(contract.client.id),
                    'name': contract.client.full_name,
                    'email': contract.client.email,
                    'company': contract.client.company
                }
            
            contracts_data.append(contract_data)
        
        return jsonify({
            'contracts': contracts_data,
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
        current_app.logger.error(f"Get contracts error: {str(e)}")
        return jsonify({'error': 'Failed to get contracts'}), 500

@contracts_bp.route('/<contract_id>', methods=['GET'])
@client_or_admin_required
def get_contract(contract_id):
    """Get contract by ID"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and contract.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        contract_data = contract.to_dict(include_content=True)
        
        # Include project info
        if contract.project:
            contract_data['project'] = contract.project.to_dict()
        
        # Include client info
        if contract.client:
            contract_data['client'] = {
                'id': str(contract.client.id),
                'name': contract.client.full_name,
                'email': contract.client.email,
                'company': contract.client.company
            }
        
        # Include signatures
        signatures = ContractSignature.query.filter_by(contract_id=contract_id).all()
        contract_data['signatures'] = [sig.to_dict() for sig in signatures]
        
        return jsonify({'contract': contract_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get contract error: {str(e)}")
        return jsonify({'error': 'Failed to get contract'}), 500

@contracts_bp.route('/', methods=['POST'])
@admin_required
def create_contract():
    """Create new contract (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['project_id', 'title', 'content', 'amount']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate project exists
        project = Project.query.get(data['project_id'])
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Generate contract number
        contract_number = generate_contract_number()
        
        # Calculate expiry date (default 180 days)
        expiry_days = int(current_app.config.get('CONTRACT_EXPIRY_DAYS', 180))
        expiry_date = date.today() + timedelta(days=expiry_days)
        
        contract = Contract(
            project_id=project.id,
            client_id=project.client_id,
            contract_number=contract_number,
            title=data['title'],
            content=data['content'],
            amount=data['amount'],
            currency=data.get('currency', 'OMR'),
            expiry_date=expiry_date,
            terms_and_conditions=data.get('terms_and_conditions'),
            created_by=get_jwt_identity()
        )
        
        db.session.add(contract)
        db.session.commit()
        
        return jsonify({
            'message': 'Contract created successfully',
            'contract': contract.to_dict(include_content=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create contract error: {str(e)}")
        return jsonify({'error': 'Failed to create contract'}), 500

@contracts_bp.route('/<contract_id>/send', methods=['PUT'])
@admin_required
def send_contract(contract_id):
    """Send contract to client (admin only)"""
    try:
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if contract.status != 'draft':
            return jsonify({'error': 'Contract can only be sent from draft status'}), 400
        
        contract.status = 'sent'
        contract.sent_date = date.today()
        contract.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # TODO: Send email notification to client
        
        return jsonify({
            'message': 'Contract sent to client successfully',
            'contract': contract.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Send contract error: {str(e)}")
        return jsonify({'error': 'Failed to send contract'}), 500

@contracts_bp.route('/<contract_id>/sign', methods=['POST'])
@jwt_required()
def sign_contract(contract_id):
    """Sign contract"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Check if user can sign this contract
        if contract.client_id != user.id:
            return jsonify({'error': 'You are not authorized to sign this contract'}), 403
        
        # Check contract status
        if contract.status not in ['sent']:
            return jsonify({'error': 'Contract is not available for signing'}), 400
        
        # Check if contract is expired
        if contract.is_expired:
            return jsonify({'error': 'Contract has expired'}), 400
        
        # Check if user has verified identity
        identity_verification = IdentityVerification.query.filter_by(user_id=user.id).first()
        if not identity_verification or identity_verification.verification_status != 'verified':
            return jsonify({'error': 'Identity verification required before signing contracts'}), 400
        
        # Check if already signed
        existing_signature = ContractSignature.query.filter_by(
            contract_id=contract_id,
            signer_id=user.id
        ).first()
        if existing_signature:
            return jsonify({'error': 'Contract already signed'}), 400
        
        # Handle signature upload
        if 'signature' not in request.files:
            return jsonify({'error': 'Signature image is required'}), 400
        
        signature_file = request.files['signature']
        if signature_file.filename == '':
            return jsonify({'error': 'No signature file selected'}), 400
        
        # Upload signature
        signature_url = upload_file(signature_file, f'contracts/{contract_id}/signatures')
        
        # Create signature record
        signature = ContractSignature(
            contract_id=contract_id,
            signer_id=user.id,
            signature_image_url=signature_url,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        # Update contract status
        contract.status = 'signed'
        contract.signed_date = date.today()
        contract.updated_at = datetime.utcnow()
        
        db.session.add(signature)
        db.session.commit()
        
        return jsonify({
            'message': 'Contract signed successfully',
            'contract': contract.to_dict(),
            'signature': signature.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Sign contract error: {str(e)}")
        return jsonify({'error': 'Failed to sign contract'}), 500

@contracts_bp.route('/<contract_id>/activate', methods=['PUT'])
@admin_required
def activate_contract(contract_id):
    """Activate signed contract (admin only)"""
    try:
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if contract.status != 'signed':
            return jsonify({'error': 'Contract must be signed before activation'}), 400
        
        contract.status = 'active'
        contract.updated_at = datetime.utcnow()
        
        # Update project status to in-progress if not already
        if contract.project and contract.project.status in ['approved']:
            contract.project.status = 'in-progress'
            contract.project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Contract activated successfully',
            'contract': contract.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Activate contract error: {str(e)}")
        return jsonify({'error': 'Failed to activate contract'}), 500

@contracts_bp.route('/<contract_id>/complete', methods=['PUT'])
@admin_required
def complete_contract(contract_id):
    """Mark contract as completed (admin only)"""
    try:
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if contract.status != 'active':
            return jsonify({'error': 'Contract must be active to complete'}), 400
        
        contract.status = 'completed'
        contract.completion_date = date.today()
        contract.updated_at = datetime.utcnow()
        
        # Update project status to completed if not already
        if contract.project and contract.project.status != 'completed':
            contract.project.status = 'completed'
            contract.project.completion_date = date.today()
            contract.project.progress = 100
            contract.project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Contract completed successfully',
            'contract': contract.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Complete contract error: {str(e)}")
        return jsonify({'error': 'Failed to complete contract'}), 500

@contracts_bp.route('/<contract_id>/cancel', methods=['PUT'])
@admin_required
def cancel_contract(contract_id):
    """Cancel contract (admin only)"""
    try:
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if contract.status in ['completed', 'cancelled']:
            return jsonify({'error': 'Cannot cancel completed or already cancelled contract'}), 400
        
        data = request.get_json()
        cancellation_reason = data.get('reason', 'No reason provided')
        
        contract.status = 'cancelled'
        contract.updated_at = datetime.utcnow()
        
        # Add cancellation reason to terms
        if contract.terms_and_conditions:
            contract.terms_and_conditions += f"\n\nCancellation Reason: {cancellation_reason}"
        else:
            contract.terms_and_conditions = f"Cancellation Reason: {cancellation_reason}"
        
        db.session.commit()
        
        return jsonify({
            'message': 'Contract cancelled successfully',
            'contract': contract.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Cancel contract error: {str(e)}")
        return jsonify({'error': 'Failed to cancel contract'}), 500

@contracts_bp.route('/<contract_id>/download', methods=['GET'])
@client_or_admin_required
def download_contract(contract_id):
    """Download contract as PDF"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        contract = Contract.query.get(contract_id)
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and contract.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # TODO: Generate PDF and return file
        # For now, return contract data
        return jsonify({
            'message': 'PDF generation not implemented yet',
            'contract': contract.to_dict(include_content=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Download contract error: {str(e)}")
        return jsonify({'error': 'Failed to download contract'}), 500

@contracts_bp.route('/stats', methods=['GET'])
@admin_required
def get_contract_stats():
    """Get contract statistics (admin only)"""
    try:
        stats = {
            'total_contracts': Contract.query.count(),
            'draft': Contract.query.filter_by(status='draft').count(),
            'sent': Contract.query.filter_by(status='sent').count(),
            'signed': Contract.query.filter_by(status='signed').count(),
            'active': Contract.query.filter_by(status='active').count(),
            'completed': Contract.query.filter_by(status='completed').count(),
            'cancelled': Contract.query.filter_by(status='cancelled').count(),
            'expired': Contract.query.filter(Contract.is_expired == True).count(),
            'total_value': db.session.query(db.func.sum(Contract.amount)).filter(Contract.status.in_(['signed', 'active', 'completed'])).scalar() or 0
        }
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get contract stats error: {str(e)}")
        return jsonify({'error': 'Failed to get contract statistics'}), 500

