# Test Scripts

This folder contains utility scripts for testing and validating the MediBudAI system.

## 📋 Available Scripts

### `test_openai.py`
- **Purpose**: Test OpenAI API connection and key validity
- **Usage**: `python3 test_scripts/test_openai.py`
- **Features**:
  - Validates API key format and authenticity
  - Tests connection to OpenAI API
  - Checks available models (GPT-4o, GPT-4o-mini, etc.)
  - Provides detailed error messages and solutions

### `test_setup.py`
- **Purpose**: Validate complete system setup and dependencies
- **Usage**: `python3 test_scripts/test_setup.py`
- **Features**:
  - Checks Python version compatibility
  - Validates required packages installation
  - Tests environment configuration
  - Verifies folder structure and permissions

## 🚀 Quick Test Commands

```bash
# Test OpenAI API connection
python3 test_scripts/test_openai.py

# Validate complete setup
python3 test_scripts/test_setup.py
```

## 🔧 Running from Project Root

Make sure to run these scripts from the main project directory (`medi_budai/`) so they can access the `.env` file and other project resources properly.

## 📝 Notes

- Both scripts require the `.env` file to be configured
- The OpenAI test requires a valid API key
- Run these tests after any configuration changes
- Use these for troubleshooting setup issues
