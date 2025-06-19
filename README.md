# AlphaZee Client Platform - Backend Implementation

## Overview

This is a complete backend implementation for the AlphaZee Client Platform, built with Flask and PostgreSQL. The backend provides a comprehensive API for managing clients, projects, contracts, payments, and communication.

## Features Implemented

### 🔐 Authentication & User Management
- User registration and login with JWT tokens
- Password reset functionality
- Identity verification with ID card and signature uploads
- Role-based access control (Admin/Client)
- Session management

### 📋 Project Management
- Project submission with automatic account creation
- Project status tracking and milestone management
- File uploads and project documentation
- Project type categorization
- Progress tracking and reporting

### 📄 Contract Management
- Contract creation and digital signing
- Contract lifecycle management (draft → sent → signed → active → completed)
- Digital signature verification
- Contract expiration handling
- PDF generation support

### 💳 Payment Processing
- Stripe payment integration
- Invoice generation and management
- Payment tracking and history
- Milestone-based payments
- Tax calculation

### 💬 Communication System
- Messaging between clients and admin
- Real-time notifications
- Message threading and replies
- File attachments support

### 👨‍💼 Admin Panel
- User management and verification
- Project oversight and status updates
- Contract and payment management
- System analytics and reporting
- Activity logging

## Technology Stack

- **Framework**: Flask 3.1.1
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Flask-JWT-Extended
- **Migrations**: Flask-Migrate
- **Email**: Flask-Mail
- **File Storage**: Local storage with AWS S3 support
- **Payments**: Stripe integration
- **CORS**: Flask-CORS

## Database Schema

The database includes the following main tables:

- `users` - User accounts and profiles
- `identity_verifications` - Identity verification data
- `projects` - Project information and status
- `project_types` - Project categorization
- `project_milestones` - Project milestone tracking
- `project_files` - File attachments
- `contracts` - Contract management
- `contract_signatures` - Digital signatures
- `payments` - Payment transactions
- `invoices` - Invoice management
- `messages` - Communication system
- `notifications` - User notifications
- `activity_logs` - System activity tracking

## API Endpoints

### Authentication (`/api/auth`)
- `POST /register` - User registration
- `POST /login` - User login
- `POST /logout` - User logout
- `POST /refresh` - Refresh JWT token
- `POST /forgot-password` - Request password reset
- `POST /reset-password` - Reset password

### Users (`/api/users`)
- `GET /profile` - Get user profile
- `PUT /profile` - Update user profile
- `POST /upload-avatar` - Upload profile picture
- `POST /verify-identity` - Submit identity verification
- `GET /verification-status` - Check verification status

### Projects (`/api/projects`)
- `GET /types` - Get project types
- `POST /submit` - Submit new project (public endpoint)
- `GET /` - Get user projects
- `GET /{id}` - Get project details
- `PUT /{id}/status` - Update project status (admin)
- `GET /{id}/milestones` - Get project milestones
- `POST /{id}/milestones` - Create milestone (admin)
- `PUT /{id}/milestones/{milestone_id}/complete` - Complete milestone (admin)
- `GET /{id}/files` - Get project files
- `POST /{id}/files` - Upload project file

### Contracts (`/api/contracts`)
- `GET /` - Get contracts
- `GET /{id}` - Get contract details
- `POST /` - Create contract (admin)
- `PUT /{id}/send` - Send contract to client (admin)
- `POST /{id}/sign` - Sign contract
- `PUT /{id}/activate` - Activate contract (admin)
- `PUT /{id}/complete` - Complete contract (admin)

### Payments (`/api/payments`)
- `GET /` - Get payments
- `GET /{id}` - Get payment details
- `POST /` - Create payment request (admin)
- `POST /{id}/process` - Process payment
- `POST /{id}/intent` - Create Stripe payment intent
- `POST /{id}/confirm` - Confirm payment
- `GET /invoices` - Get invoices
- `POST /invoices` - Create invoice (admin)

### Messages (`/api/messages`)
- `GET /` - Get messages
- `GET /{id}` - Get message details
- `POST /` - Send message
- `POST /{id}/reply` - Reply to message
- `PUT /{id}/read` - Mark message as read
- `GET /unread-count` - Get unread message count
- `GET /notifications` - Get notifications
- `PUT /notifications/{id}/read` - Mark notification as read

### Files (`/api/files`)
- `POST /upload` - Upload general file
- `GET /download/{path}` - Download file
- `GET /info/{path}` - Get file information
- `DELETE /delete/{path}` - Delete file

### Admin (`/api/admin`)
- `GET /dashboard` - Get admin dashboard
- `GET /users` - Get all users
- `GET /users/{id}` - Get user details
- `PUT /users/{id}/status` - Update user status
- `PUT /users/{id}/verification` - Update verification status
- `GET /project-types` - Manage project types
- `POST /project-types` - Create project type
- `GET /activity-logs` - Get activity logs
- `POST /system/cleanup` - System cleanup
- `POST /system/broadcast` - Broadcast message

## Installation & Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Virtual environment

### 1. Clone and Setup
```bash
cd alphazee_backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Database Setup
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres createdb alphazee_db
sudo -u postgres psql -c "CREATE USER alphazee_user WITH PASSWORD 'alphazee_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE alphazee_db TO alphazee_user;"
sudo -u postgres psql -c "ALTER USER alphazee_user CREATEDB;"
```

### 3. Environment Configuration
```bash
cp .env.example .env
# Edit .env file with your configuration
```

### 4. Database Migration
```bash
export FLASK_APP=src/main.py
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 5. Run Application
```bash
python src/main.py
```

The application will be available at `http://localhost:5000`

## Environment Variables

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database Configuration
DATABASE_URL=postgresql://alphazee_user:alphazee_password@localhost/alphazee_db

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@alphazee.com

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-publishable-key
STRIPE_SECRET_KEY=sk_test_your-stripe-secret-key

# Application URLs
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:5000

# CORS Configuration
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Production Deployment

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app
```

### Using Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "src.main:app"]
```

### Environment Setup for Production
- Set `DEBUG=False`
- Use strong secret keys
- Configure proper database credentials
- Set up SSL/TLS certificates
- Configure email server
- Set up Stripe production keys
- Configure file storage (AWS S3 recommended)

## Security Features

- JWT token-based authentication
- Password hashing with bcrypt
- CORS protection
- SQL injection prevention with SQLAlchemy ORM
- File upload validation
- Rate limiting (can be added with Flask-Limiter)
- Input validation and sanitization

## File Storage

The system supports both local file storage and AWS S3:

### Local Storage
Files are stored in the `uploads/` directory with organized subdirectories:
- `avatars/` - User profile pictures
- `identity/front_id/` - Front ID card images
- `identity/back_id/` - Back ID card images
- `identity/signatures/` - Digital signatures
- `projects/{project_id}/` - Project files
- `contracts/{contract_id}/signatures/` - Contract signatures

### AWS S3 Storage
Configure AWS credentials in environment variables to use S3 storage.

## Testing

The application includes comprehensive error handling and logging. Test the API endpoints using:

```bash
# Health check
curl http://localhost:5000/api/health

# Test project types endpoint
curl http://localhost:5000/api/projects/types
```

## Monitoring & Logging

- Application logs are written to console and can be redirected to files
- Activity logging tracks all user actions
- Database queries are logged in debug mode
- Error handling with proper HTTP status codes

## Support

For issues or questions regarding the backend implementation, please refer to the code comments and documentation within each module.

## License

This backend implementation is proprietary software for AlphaZee Client Platform.

