from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date, timedelta
from src.extensions import db
from src.models.user import User
from src.models.project import Project, ProjectMilestone
from src.models.contract import Contract, Payment, Invoice
from src.utils.helpers import admin_required, client_or_admin_required, paginate_query, generate_invoice_number, calculate_tax
from src.services.payment_service import process_stripe_payment, create_payment_intent

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/', methods=['GET'])
@client_or_admin_required
def get_payments():
    """Get payments (filtered by user role)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '')
        project_id = request.args.get('project_id', '')
        
        # Build query based on user role
        if user.role == 'admin':
            query = Payment.query
        else:
            query = Payment.query.filter_by(client_id=user.id)
        
        # Apply filters
        if status:
            query = query.filter(Payment.status == status)
        
        if project_id:
            query = query.filter(Payment.project_id == project_id)
        
        # Order by creation date
        query = query.order_by(Payment.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert payments to dict
        payments_data = []
        for payment in result['items']:
            payment_data = payment.to_dict()
            
            # Include project info
            if payment.project:
                payment_data['project'] = {
                    'id': str(payment.project.id),
                    'name': payment.project.name,
                    'status': payment.project.status
                }
            
            # Include milestone info
            if payment.milestone:
                payment_data['milestone'] = {
                    'id': str(payment.milestone.id),
                    'title': payment.milestone.title
                }
            
            # Include client info for admin
            if user.role == 'admin' and payment.client:
                payment_data['client'] = {
                    'id': str(payment.client.id),
                    'name': payment.client.full_name,
                    'email': payment.client.email,
                    'company': payment.client.company
                }
            
            payments_data.append(payment_data)
        
        return jsonify({
            'payments': payments_data,
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
        current_app.logger.error(f"Get payments error: {str(e)}")
        return jsonify({'error': 'Failed to get payments'}), 500

@payments_bp.route('/<payment_id>', methods=['GET'])
@client_or_admin_required
def get_payment(payment_id):
    """Get payment by ID"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Check access permissions
        if user.role != 'admin' and payment.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        payment_data = payment.to_dict()
        
        # Include related data
        if payment.project:
            payment_data['project'] = payment.project.to_dict()
        
        if payment.milestone:
            payment_data['milestone'] = payment.milestone.to_dict()
        
        if payment.contract:
            payment_data['contract'] = payment.contract.to_dict()
        
        return jsonify({'payment': payment_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get payment error: {str(e)}")
        return jsonify({'error': 'Failed to get payment'}), 500

@payments_bp.route('/', methods=['POST'])
@admin_required
def create_payment():
    """Create payment request (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['project_id', 'amount', 'description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate project exists
        project = Project.query.get(data['project_id'])
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Calculate due date
        due_days = int(current_app.config.get('PAYMENT_DUE_DAYS', 30))
        due_date = date.today() + timedelta(days=due_days)
        
        payment = Payment(
            project_id=project.id,
            client_id=project.client_id,
            milestone_id=data.get('milestone_id'),
            contract_id=data.get('contract_id'),
            amount=data['amount'],
            currency=data.get('currency', 'OMR'),
            description=data['description'],
            due_date=due_date,
            invoice_number=generate_invoice_number()
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'message': 'Payment request created successfully',
            'payment': payment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create payment error: {str(e)}")
        return jsonify({'error': 'Failed to create payment request'}), 500

@payments_bp.route('/<payment_id>/process', methods=['POST'])
@jwt_required()
def process_payment(payment_id):
    """Process payment"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Check access permissions
        if payment.client_id != user.id:
            return jsonify({'error': 'You are not authorized to process this payment'}), 403
        
        # Check payment status
        if payment.status != 'pending':
            return jsonify({'error': 'Payment is not available for processing'}), 400
        
        data = request.get_json()
        payment_method = data.get('payment_method', 'stripe')
        
        if payment_method == 'stripe':
            # Process Stripe payment
            stripe_token = data.get('stripe_token')
            if not stripe_token:
                return jsonify({'error': 'Stripe token is required'}), 400
            
            try:
                result = process_stripe_payment(
                    amount=float(payment.amount),
                    currency=payment.currency.lower(),
                    token=stripe_token,
                    description=f"Payment for {payment.project.name}",
                    metadata={
                        'payment_id': str(payment.id),
                        'project_id': str(payment.project_id),
                        'client_id': str(payment.client_id)
                    }
                )
                
                if result['success']:
                    # Update payment
                    payment.status = 'completed'
                    payment.paid_date = date.today()
                    payment.payment_method = 'stripe'
                    payment.payment_gateway = 'stripe'
                    payment.transaction_id = result['transaction_id']
                    payment.gateway_response = result['response']
                    payment.updated_at = datetime.utcnow()
                    
                    db.session.commit()
                    
                    return jsonify({
                        'message': 'Payment processed successfully',
                        'payment': payment.to_dict()
                    }), 200
                else:
                    return jsonify({'error': result['error']}), 400
                    
            except Exception as e:
                current_app.logger.error(f"Stripe payment error: {str(e)}")
                return jsonify({'error': 'Payment processing failed'}), 500
        
        else:
            return jsonify({'error': 'Unsupported payment method'}), 400
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Process payment error: {str(e)}")
        return jsonify({'error': 'Failed to process payment'}), 500

@payments_bp.route('/<payment_id>/intent', methods=['POST'])
@jwt_required()
def create_payment_intent_endpoint(payment_id):
    """Create Stripe payment intent"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Check access permissions
        if payment.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check payment status
        if payment.status != 'pending':
            return jsonify({'error': 'Payment is not available for processing'}), 400
        
        try:
            intent = create_payment_intent(
                amount=float(payment.amount),
                currency=payment.currency.lower(),
                metadata={
                    'payment_id': str(payment.id),
                    'project_id': str(payment.project_id),
                    'client_id': str(payment.client_id)
                }
            )
            
            return jsonify({
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }), 200
            
        except Exception as e:
            current_app.logger.error(f"Create payment intent error: {str(e)}")
            return jsonify({'error': 'Failed to create payment intent'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Create payment intent endpoint error: {str(e)}")
        return jsonify({'error': 'Failed to create payment intent'}), 500

@payments_bp.route('/<payment_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_payment(payment_id):
    """Confirm payment completion"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Check access permissions
        if payment.client_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        payment_intent_id = data.get('payment_intent_id')
        
        if not payment_intent_id:
            return jsonify({'error': 'Payment intent ID is required'}), 400
        
        # Update payment
        payment.status = 'completed'
        payment.paid_date = date.today()
        payment.payment_method = 'stripe'
        payment.payment_gateway = 'stripe'
        payment.transaction_id = payment_intent_id
        payment.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment confirmed successfully',
            'payment': payment.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Confirm payment error: {str(e)}")
        return jsonify({'error': 'Failed to confirm payment'}), 500

@payments_bp.route('/invoices', methods=['GET'])
@client_or_admin_required
def get_invoices():
    """Get invoices (filtered by user role)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '')
        
        # Build query based on user role
        if user.role == 'admin':
            query = Invoice.query
        else:
            query = Invoice.query.filter_by(client_id=user.id)
        
        # Apply filters
        if status:
            query = query.filter(Invoice.status == status)
        
        # Order by creation date
        query = query.order_by(Invoice.created_at.desc())
        
        # Paginate
        result = paginate_query(query, page, per_page)
        
        # Convert invoices to dict
        invoices_data = []
        for invoice in result['items']:
            invoice_data = invoice.to_dict()
            
            # Include project info
            if invoice.project:
                invoice_data['project'] = {
                    'id': str(invoice.project.id),
                    'name': invoice.project.name
                }
            
            # Include client info for admin
            if user.role == 'admin' and invoice.client:
                invoice_data['client'] = {
                    'id': str(invoice.client.id),
                    'name': invoice.client.full_name,
                    'email': invoice.client.email,
                    'company': invoice.client.company
                }
            
            invoices_data.append(invoice_data)
        
        return jsonify({
            'invoices': invoices_data,
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
        current_app.logger.error(f"Get invoices error: {str(e)}")
        return jsonify({'error': 'Failed to get invoices'}), 500

@payments_bp.route('/invoices', methods=['POST'])
@admin_required
def create_invoice():
    """Create invoice (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['project_id', 'amount', 'due_date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate project exists
        project = Project.query.get(data['project_id'])
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Calculate tax and total
        amount = float(data['amount'])
        tax_rate = float(current_app.config.get('TAX_RATE', 0.05))
        tax_amount = calculate_tax(amount, tax_rate)
        total_amount = amount + tax_amount
        
        invoice = Invoice(
            project_id=project.id,
            client_id=project.client_id,
            invoice_number=generate_invoice_number(),
            amount=amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency=data.get('currency', 'OMR'),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date(),
            description=data.get('description'),
            line_items=data.get('line_items', [])
        )
        
        db.session.add(invoice)
        db.session.commit()
        
        return jsonify({
            'message': 'Invoice created successfully',
            'invoice': invoice.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create invoice error: {str(e)}")
        return jsonify({'error': 'Failed to create invoice'}), 500

@payments_bp.route('/stats', methods=['GET'])
@admin_required
def get_payment_stats():
    """Get payment statistics (admin only)"""
    try:
        stats = {
            'total_payments': Payment.query.count(),
            'pending': Payment.query.filter_by(status='pending').count(),
            'completed': Payment.query.filter_by(status='completed').count(),
            'failed': Payment.query.filter_by(status='failed').count(),
            'total_revenue': db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == 'completed').scalar() or 0,
            'pending_revenue': db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == 'pending').scalar() or 0,
            'overdue_payments': Payment.query.filter(Payment.is_overdue == True).count(),
            'total_invoices': Invoice.query.count(),
            'paid_invoices': Invoice.query.filter_by(status='paid').count(),
            'overdue_invoices': Invoice.query.filter(Invoice.is_overdue == True).count()
        }
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get payment stats error: {str(e)}")
        return jsonify({'error': 'Failed to get payment statistics'}), 500

