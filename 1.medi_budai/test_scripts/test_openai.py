#!/usr/bin/env python3
"""
OpenAI API Connection Test
Test script to verify OpenAI API key and connection
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_openai_connection():
    """Test OpenAI API connection and key validity"""
    
    # Check if API key is set
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in environment variables")
        return False
    
    # Check if API key format looks correct
    if not api_key.startswith('sk-'):
        print("❌ ERROR: API key doesn't start with 'sk-' - invalid format")
        return False
    
    print(f"✅ API Key found: {api_key[:20]}...{api_key[-10:]}")
    
    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=api_key)
        print("✅ OpenAI client initialized successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize OpenAI client: {e}")
        return False
    
    # Test API connection with a simple request
    try:
        print("🔄 Testing API connection...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10,
            temperature=0
        )
        
        print("✅ API connection successful!")
        print(f"Response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: API connection failed: {e}")
        
        # Check for specific error types
        error_str = str(e).lower()
        if "invalid_api_key" in error_str or "unauthorized" in error_str:
            print("💡 SOLUTION: The API key appears to be invalid or expired")
            print("   - Check if the API key is correct")
            print("   - Verify the API key hasn't expired")
            print("   - Ensure you have sufficient credits")
        elif "rate_limit" in error_str:
            print("💡 SOLUTION: Rate limit exceeded")
            print("   - Wait a few minutes and try again")
            print("   - Check your usage limits")
        elif "quota" in error_str or "billing" in error_str:
            print("💡 SOLUTION: Billing or quota issue")
            print("   - Check your OpenAI account billing")
            print("   - Ensure you have sufficient credits")
        else:
            print("💡 SOLUTION: General connection issue")
            print("   - Check your internet connection")
            print("   - Verify the API endpoint is accessible")
        
        return False

def test_available_models():
    """Test which models are available"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return
    
    try:
        client = OpenAI(api_key=api_key)
        print("\n🔄 Checking available models...")
        
        # Test specific models used in the app
        models_to_test = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
        
        for model in models_to_test:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=1,
                    temperature=0
                )
                print(f"✅ {model} - Available and working")
            except Exception as e:
                error_str = str(e).lower()
                if "model_not_found" in error_str or "does not exist" in error_str:
                    print(f"❌ {model} - Not available (model not found)")
                else:
                    print(f"⚠️ {model} - Error: {str(e)[:50]}...")
                    
    except Exception as e:
        print(f"❌ ERROR: Could not test models: {e}")

if __name__ == "__main__":
    print("🧪 OpenAI API Connection Test")
    print("=" * 40)
    
    # Test basic connection
    connection_success = test_openai_connection()
    
    if connection_success:
        # Test available models
        test_available_models()
        print("\n✅ All tests completed successfully!")
    else:
        print("\n❌ Connection test failed. Please fix the issues above.")
        sys.exit(1)
