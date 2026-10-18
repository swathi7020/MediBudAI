#!/bin/bash

# MediBudAI Setup Script
# This script helps you set up the MediBudAI system on macOS/Linux

echo "🏥 MediBudAI Setup Script"
echo "========================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment (recommended)
read -p "Do you want to create a virtual environment? (y/n): " create_venv

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    echo "✓ Virtual environment created and activated"
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Check if .env file needs configuration
if grep -q "your_openai_api_key_here" .env; then
    echo ""
    echo "⚠️  Configuration needed:"
    echo "   Please edit the .env file and add your OpenAI API key"
    echo "   Replace 'your_openai_api_key_here' with your actual API key"
    echo ""
    echo "   You can get an API key from: https://platform.openai.com/api-keys"
    echo ""
fi

# Run system test
echo "Running system test..."
python3 test_setup.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your OpenAI API key (if not done yet)"
echo "2. Run the application: python3 app.py"
echo "3. Open your browser to: http://localhost:5000"
echo ""

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "Note: Don't forget to activate your virtual environment next time:"
    echo "      source venv/bin/activate"
fi
