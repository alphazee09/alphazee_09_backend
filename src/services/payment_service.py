from flask import current_app
import stripe

def init_stripe():
    """Initialize Stripe with API key"""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')

def process_stripe_payment(amount, currency, token, description, metadata=None):
    """Process payment using Stripe"""
    try:
        init_stripe()
        
        # Convert amount to cents for Stripe
        amount_cents = int(amount * 100)
        
        # Create charge
        charge = stripe.Charge.create(
            amount=amount_cents,
            currency=currency,
            source=token,
            description=description,
            metadata=metadata or {}
        )
        
        return {
            'success': True,
            'transaction_id': charge.id,
            'response': {
                'id': charge.id,
                'amount': charge.amount,
                'currency': charge.currency,
                'status': charge.status,
                'paid': charge.paid,
                'created': charge.created
            }
        }
        
    except stripe.error.CardError as e:
        # Card was declined
        return {
            'success': False,
            'error': f"Card was declined: {e.user_message}",
            'response': {
                'code': e.code,
                'decline_code': e.decline_code,
                'message': e.user_message
            }
        }
        
    except stripe.error.RateLimitError as e:
        return {
            'success': False,
            'error': "Rate limit exceeded. Please try again later.",
            'response': {'message': str(e)}
        }
        
    except stripe.error.InvalidRequestError as e:
        return {
            'success': False,
            'error': f"Invalid request: {str(e)}",
            'response': {'message': str(e)}
        }
        
    except stripe.error.AuthenticationError as e:
        current_app.logger.error(f"Stripe authentication error: {str(e)}")
        return {
            'success': False,
            'error': "Payment processing configuration error.",
            'response': {'message': str(e)}
        }
        
    except stripe.error.APIConnectionError as e:
        return {
            'success': False,
            'error': "Network error. Please try again.",
            'response': {'message': str(e)}
        }
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return {
            'success': False,
            'error': "Payment processing error. Please try again.",
            'response': {'message': str(e)}
        }
        
    except Exception as e:
        current_app.logger.error(f"Unexpected payment error: {str(e)}")
        return {
            'success': False,
            'error': "An unexpected error occurred. Please try again.",
            'response': {'message': str(e)}
        }

def create_payment_intent(amount, currency, metadata=None):
    """Create Stripe Payment Intent for modern payment flow"""
    try:
        init_stripe()
        
        # Convert amount to cents for Stripe
        amount_cents = int(amount * 100)
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata or {},
            automatic_payment_methods={
                'enabled': True,
            },
        )
        
        return intent
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe payment intent error: {str(e)}")
        raise Exception(f"Failed to create payment intent: {str(e)}")
        
    except Exception as e:
        current_app.logger.error(f"Unexpected payment intent error: {str(e)}")
        raise Exception(f"An unexpected error occurred: {str(e)}")

def retrieve_payment_intent(payment_intent_id):
    """Retrieve Stripe Payment Intent"""
    try:
        init_stripe()
        
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe retrieve payment intent error: {str(e)}")
        raise Exception(f"Failed to retrieve payment intent: {str(e)}")

def create_customer(email, name, metadata=None):
    """Create Stripe customer"""
    try:
        init_stripe()
        
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )
        
        return customer
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe create customer error: {str(e)}")
        raise Exception(f"Failed to create customer: {str(e)}")

def create_subscription(customer_id, price_id, metadata=None):
    """Create Stripe subscription"""
    try:
        init_stripe()
        
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_id}],
            metadata=metadata or {}
        )
        
        return subscription
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe create subscription error: {str(e)}")
        raise Exception(f"Failed to create subscription: {str(e)}")

def cancel_subscription(subscription_id):
    """Cancel Stripe subscription"""
    try:
        init_stripe()
        
        subscription = stripe.Subscription.delete(subscription_id)
        return subscription
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe cancel subscription error: {str(e)}")
        raise Exception(f"Failed to cancel subscription: {str(e)}")

def create_refund(charge_id, amount=None, reason=None):
    """Create Stripe refund"""
    try:
        init_stripe()
        
        refund_data = {'charge': charge_id}
        
        if amount:
            refund_data['amount'] = int(amount * 100)  # Convert to cents
        
        if reason:
            refund_data['reason'] = reason
        
        refund = stripe.Refund.create(**refund_data)
        
        return {
            'success': True,
            'refund_id': refund.id,
            'response': {
                'id': refund.id,
                'amount': refund.amount,
                'currency': refund.currency,
                'status': refund.status,
                'reason': refund.reason,
                'created': refund.created
            }
        }
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe refund error: {str(e)}")
        return {
            'success': False,
            'error': f"Refund failed: {str(e)}",
            'response': {'message': str(e)}
        }

def handle_webhook(payload, sig_header):
    """Handle Stripe webhook"""
    try:
        endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        
        if not endpoint_secret:
            current_app.logger.warning("Stripe webhook secret not configured")
            return None
        
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        
        return event
        
    except ValueError as e:
        current_app.logger.error(f"Invalid webhook payload: {str(e)}")
        raise Exception("Invalid payload")
        
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f"Invalid webhook signature: {str(e)}")
        raise Exception("Invalid signature")

def get_publishable_key():
    """Get Stripe publishable key for frontend"""
    return current_app.config.get('STRIPE_PUBLISHABLE_KEY')

