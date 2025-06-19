#!/bin/bash

# AlphaZee Backend Deployment Script
# This script sets up the complete backend environment

set -e

echo "🚀 Starting AlphaZee Backend Deployment..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please do not run this script as root"
    exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt update

# Install PostgreSQL if not installed
if ! command -v psql &> /dev/null; then
    echo "🐘 Installing PostgreSQL..."
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
else
    echo "✅ PostgreSQL already installed"
fi

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

# Setup database
echo "🗄️ Setting up database..."
DB_NAME="alphazee_db"
DB_USER="alphazee_user"
DB_PASS="alphazee_password"

# Check if database exists
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "✅ Database $DB_NAME already exists"
else
    echo "📊 Creating database and user..."
    sudo -u postgres createdb $DB_NAME
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    sudo -u postgres psql -c "ALTER USER $DB_USER CREATEDB;"
fi

# Setup environment file
if [ ! -f ".env" ]; then
    echo "⚙️ Creating environment file..."
    cp .env.example .env
    echo "📝 Please edit .env file with your configuration before running the application"
else
    echo "✅ Environment file already exists"
fi

# Run database migrations
echo "🔄 Running database migrations..."
export FLASK_APP=src/main.py
flask db upgrade

# Create upload directories
echo "📁 Creating upload directories..."
mkdir -p uploads/{avatars,identity/{front_id,back_id,signatures},projects,contracts}

# Set permissions
chmod 755 uploads
chmod -R 755 uploads/*

echo "✅ AlphaZee Backend deployment completed successfully!"
echo ""
echo "🎯 Next steps:"
echo "1. Edit .env file with your configuration (email, Stripe keys, etc.)"
echo "2. Start the application: python src/main.py"
echo "3. Test the API: curl http://localhost:5000/api/health"
echo ""
echo "📚 Documentation: See README.md for detailed information"
echo "🌐 API will be available at: http://localhost:5000"

