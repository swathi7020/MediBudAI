#!/usr/bin/env python3
"""
Test script for MediBudAI system
Run this script to verify your setup before using the application.
"""

import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Check environment setup."""
    print("🔍 Checking Environment Setup...")
    
    # Load environment variables
    load_dotenv()
    
    # Check Python version
    python_version = sys.version_info
    print(f"✓ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    
    # Check OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or api_key == 'your_openai_api_key_here':
        print("❌ OpenAI API key not set in .env file")
        print("   Please set OPENAI_API_KEY in your .env file")
        return False
    else:
        print(f"✓ OpenAI API key found (starts with: {api_key[:8]}...)")
    
    # Check directories
    upload_dir = 'uploads'
    if os.path.exists(upload_dir):
        print(f"✓ Upload directory exists: {upload_dir}")
    else:
        print(f"❌ Upload directory missing: {upload_dir}")
        return False
    
    return True

def check_dependencies():
    """Check required dependencies."""
    print("\n📦 Checking Dependencies...")
    
    required_packages = [
        ('flask', 'flask'),
        ('flask_cors', 'flask_cors'),
        ('openai', 'openai'),
        ('PyPDF2', 'PyPDF2'),
        ('python-dotenv', 'dotenv'),
        ('requests', 'requests'),
        ('werkzeug', 'werkzeug')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✓ {package_name}")
        except ImportError:
            print(f"❌ {package_name} not installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def test_openai_connection():
    """Test OpenAI API connection with latest models."""
    print("\n🤖 Testing OpenAI Connection...")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Test with the latest models that support medical analysis
        models_to_test = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4"]
        
        for model in models_to_test:
            try:
                print(f"  Testing model: {model}")
                
                # Simple test request with medical context
                response = client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user", 
                        "content": "Respond with a JSON object containing just one key 'status' with value 'ok'"
                    }],
                    max_tokens=50,
                    response_format={"type": "json_object"}
                )
                
                if response.choices[0].message.content:
                    print(f"  ✓ {model} - Available and working")
                    return True
                    
            except Exception as model_error:
                print(f"  ⚠️ {model} - Not available: {str(model_error)}")
                continue
        
        print("❌ No working OpenAI models found")
        return False
            
    except Exception as e:
        print(f"❌ OpenAI API connection failed: {str(e)}")
        print("   Check your API key and internet connection")
        return False

def check_file_structure():
    """Check required files and directories."""
    print("\n📁 Checking File Structure...")
    
    required_files = [
        'app.py',
        'requirements.txt',
        '.env',
        'templates/index.html',
        'static/css/style.css',
        'static/js/app.js'
    ]
    
    required_dirs = [
        'templates',
        'static',
        'static/css',
        'static/js',
        'uploads'
    ]
    
    all_good = True
    
    # Check directories
    for dir_path in required_dirs:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"✓ Directory: {dir_path}")
        else:
            print(f"❌ Missing directory: {dir_path}")
            all_good = False
    
    # Check files
    for file_path in required_files:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            print(f"✓ File: {file_path}")
        else:
            print(f"❌ Missing file: {file_path}")
            all_good = False
    
    return all_good

def main():
    """Main test function."""
    print("🏥 MediBudAI System Test\n")
    print("=" * 50)
    
    tests = [
        ("Environment Setup", check_environment),
        ("File Structure", check_file_structure),
        ("Dependencies", check_dependencies),
        ("OpenAI Connection", test_openai_connection)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with error: {str(e)}")
            results[test_name] = False
        print()
    
    # Summary
    print("=" * 50)
    print("📊 Test Summary:")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 50)
    
    if all_passed:
        print("🎉 All tests passed! Your MediBudAI system is ready to use.")
        print("\nTo start the application:")
        print("  python app.py")
        print("\nThen open: http://localhost:5000")
    else:
        print("⚠️  Some tests failed. Please fix the issues above before running the application.")
        print("\nCommon fixes:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Set OpenAI API key in .env file")
        print("  3. Check file permissions")

if __name__ == "__main__":
    main()
