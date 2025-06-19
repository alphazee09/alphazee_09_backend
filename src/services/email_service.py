from flask import current_app, render_template_string
from flask_mail import Message
from src.extensions import mail
import os

def send_email(to, subject, template, **kwargs):
    """Send email using Flask-Mail"""
    try:
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            html=template,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False

def send_welcome_email(user, auto_generated_password=None):
    """Send welcome email to new user"""
    subject = "Welcome to AlphaZee Platform"
    
    if auto_generated_password:
        template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Welcome to AlphaZee Platform!</h1>
                <p>Dear {user.first_name},</p>
                <p>Thank you for joining AlphaZee Platform. Your account has been created successfully.</p>
                
                <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #1f2937;">Your Login Credentials:</h3>
                    <p><strong>Email:</strong> {user.email}</p>
                    <p><strong>Password:</strong> {auto_generated_password}</p>
                </div>
                
                <p style="color: #dc2626;"><strong>Important:</strong> Please log in and change your password as soon as possible for security reasons.</p>
                
                <div style="margin: 30px 0;">
                    <a href="{current_app.config.get('FRONTEND_URL', '')}/login" 
                       style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        Login to Your Account
                    </a>
                </div>
                
                <p>If you have any questions, please don't hesitate to contact our support team.</p>
                
                <p>Best regards,<br>
                <strong>AlphaZee Team</strong></p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                <p style="font-size: 12px; color: #6b7280;">
                    This email was sent to {user.email}. If you did not request this account, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
    else:
        template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Welcome to AlphaZee Platform!</h1>
                <p>Dear {user.first_name},</p>
                <p>Thank you for registering with AlphaZee Platform. Your account has been created successfully.</p>
                
                <div style="margin: 30px 0;">
                    <a href="{current_app.config.get('FRONTEND_URL', '')}/login" 
                       style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        Login to Your Account
                    </a>
                </div>
                
                <p>You can now:</p>
                <ul>
                    <li>Submit new project requests</li>
                    <li>Track your project progress</li>
                    <li>Communicate with our team</li>
                    <li>Manage payments and contracts</li>
                </ul>
                
                <p>If you have any questions, please don't hesitate to contact our support team.</p>
                
                <p>Best regards,<br>
                <strong>AlphaZee Team</strong></p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                <p style="font-size: 12px; color: #6b7280;">
                    This email was sent to {user.email}. If you did not create this account, please contact us immediately.
                </p>
            </div>
        </body>
        </html>
        """
    
    return send_email(user.email, subject, template)

def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    subject = "Password Reset Request - AlphaZee Platform"
    reset_link = f"{current_app.config.get('FRONTEND_URL', '')}/reset-password?token={reset_token}"
    
    template = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563eb;">Password Reset Request</h1>
            <p>Dear {user.first_name},</p>
            <p>You have requested to reset your password for your AlphaZee Platform account.</p>
            
            <div style="margin: 30px 0;">
                <a href="{reset_link}" 
                   style="background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Reset Your Password
                </a>
            </div>
            
            <p>This link will expire in 1 hour for security reasons.</p>
            
            <p>If you did not request this password reset, please ignore this email. Your password will remain unchanged.</p>
            
            <p>For security reasons, please do not share this link with anyone.</p>
            
            <p>Best regards,<br>
            <strong>AlphaZee Team</strong></p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            <p style="font-size: 12px; color: #6b7280;">
                This email was sent to {user.email}. If you did not request this reset, please contact us immediately.
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, template)

def send_project_submitted_email(user, project):
    """Send project submission confirmation email"""
    subject = "Project Submission Received - AlphaZee Platform"
    
    template = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563eb;">Project Submission Received</h1>
            <p>Dear {user.first_name},</p>
            <p>We have received your project submission: <strong>{project.name}</strong></p>
            
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #1f2937;">Project Details:</h3>
                <p><strong>Project Name:</strong> {project.name}</p>
                <p><strong>Type:</strong> {project.project_type.name if project.project_type else 'N/A'}</p>
                <p><strong>Timeline:</strong> {project.timeline or 'Not specified'}</p>
                <p><strong>Budget Range:</strong> {project.budget_range or 'Not specified'}</p>
            </div>
            
            <p>Our team will review your project and get back to you within 24-48 hours with:</p>
            <ul>
                <li>Project feasibility assessment</li>
                <li>Detailed cost estimate</li>
                <li>Proposed timeline</li>
                <li>Next steps</li>
            </ul>
            
            <div style="margin: 30px 0;">
                <a href="{current_app.config.get('FRONTEND_URL', '')}/dashboard" 
                   style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    View Project Status
                </a>
            </div>
            
            <p>Thank you for choosing AlphaZee Platform for your development needs.</p>
            
            <p>Best regards,<br>
            <strong>AlphaZee Team</strong></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, template)

def send_project_approved_email(user, project):
    """Send project approval email"""
    subject = "Project Approved - Contract Ready"
    
    template = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #16a34a;">Project Approved!</h1>
            <p>Dear {user.first_name},</p>
            <p>Great news! Your project <strong>{project.name}</strong> has been approved.</p>
            
            <div style="background-color: #f0fdf4; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #16a34a;">
                <h3 style="margin-top: 0; color: #15803d;">Project Details:</h3>
                <p><strong>Estimated Cost:</strong> {project.estimated_cost} OMR</p>
                <p><strong>Timeline:</strong> {project.timeline}</p>
                <p><strong>Start Date:</strong> {project.start_date.strftime('%B %d, %Y') if project.start_date else 'TBD'}</p>
            </div>
            
            <p>Your contract is ready for review and signing. Please log in to your dashboard to:</p>
            <ul>
                <li>Review the detailed contract</li>
                <li>Complete identity verification (if not done)</li>
                <li>Sign the contract digitally</li>
                <li>Make the initial payment</li>
            </ul>
            
            <div style="margin: 30px 0;">
                <a href="{current_app.config.get('FRONTEND_URL', '')}/dashboard" 
                   style="background-color: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Review Contract
                </a>
            </div>
            
            <p>We're excited to work with you on this project!</p>
            
            <p>Best regards,<br>
            <strong>AlphaZee Team</strong></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, template)

def send_milestone_completed_email(user, project, milestone):
    """Send milestone completion email"""
    subject = f"Milestone Completed - {project.name}"
    
    template = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563eb;">Milestone Completed</h1>
            <p>Dear {user.first_name},</p>
            <p>We have completed a milestone for your project <strong>{project.name}</strong>.</p>
            
            <div style="background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2563eb;">
                <h3 style="margin-top: 0; color: #1d4ed8;">Milestone: {milestone.title}</h3>
                <p>{milestone.description}</p>
                <p><strong>Project Progress:</strong> {project.progress}%</p>
            </div>
            
            <p>Please review the completed work in your dashboard and provide any feedback.</p>
            
            <div style="margin: 30px 0;">
                <a href="{current_app.config.get('FRONTEND_URL', '')}/dashboard" 
                   style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Review Milestone
                </a>
            </div>
            
            <p>Thank you for your continued trust in our services.</p>
            
            <p>Best regards,<br>
            <strong>AlphaZee Team</strong></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, template)

