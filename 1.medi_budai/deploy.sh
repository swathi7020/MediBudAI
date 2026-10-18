#!/bin/bash

# MediBudAI Deployment Script
# This script sets up MediBudAI on any server with minimal configuration

set -e  # Exit on any error

echo "🏥 MediBudAI Deployment Script"
echo "=============================="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Application directory: $SCRIPT_DIR"

# Change to application directory
cd "$SCRIPT_DIR"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating application directories..."
mkdir -p uploads output logs

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ Created .env from template"
        echo ""
        echo "🔑 IMPORTANT: Please edit .env file and set your OpenAI API key:"
        echo "   OPENAI_API_KEY=your_actual_api_key_here"
        echo ""
    else
        echo "❌ No .env.example file found. Please create .env manually."
        exit 1
    fi
else
    echo "✓ .env file exists"
fi

# Check OpenAI API key
if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
    echo "⚠️  Please set your OpenAI API key in .env file before running the application"
fi

# Set proper permissions
echo "🔐 Setting file permissions..."
chmod 755 uploads output logs
chmod 600 .env

# Test the application
echo "🧪 Testing application setup..."
python3 -c "
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Basic imports test
try:
    import flask
    import openai
    import PyPDF2
    print('✓ All required packages imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)

# Directory test
base_dir = os.path.dirname(os.path.abspath(__file__))
for folder in ['uploads', 'output', 'logs']:
    folder_path = os.path.join(base_dir, folder)
    if os.path.exists(folder_path):
        print(f'✓ Directory exists: {folder_path}')
    else:
        print(f'❌ Directory missing: {folder_path}')
        sys.exit(1)

print('✓ Application structure validated')
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Edit .env file with your OpenAI API key (if not done already)"
    echo "2. For production deployment, set FLASK_ENV=production in .env"
    echo "3. Start the application:"
    echo "   source venv/bin/activate"
    echo "   python3 app.py"
    echo ""
    echo "🌐 The application will be available at:"
    echo "   http://localhost:5000 (local)"
    echo "   http://your-server-ip:5000 (external, if FLASK_HOST=0.0.0.0)"
    echo ""
    echo "🔧 Production notes:"
    echo "- Consider using a reverse proxy (nginx/apache)"
    echo "- Set up SSL/HTTPS termination"
    echo "- Use a process manager (supervisor/systemd)"
    echo "- Monitor disk usage in uploads/output/logs directories"
else
    echo "❌ Deployment failed. Please check the errors above."
    exit 1
fi
