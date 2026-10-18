# MediBudAI - Medical Document Analysis System

A comprehensive medical document analysis system that uses AI to analyze PDF medical documents and provide structured insights.

## 🏥 Features

- **PDF Upload**: Drag-and-drop or click to upload medical documents
- **AI Analysis**: OpenAI GPT-5.4-mini/GPT-4o/GPT-4o-mini powered medical document analysis
- **User Comments**: Add contextual notes to enhance AI analysis
- **Structured Reports**: Organized analysis with key findings, diagnoses, medications, and recommendations
- **Unique Tracking**: Each analysis gets a unique ID for tracking
- **Comprehensive Logging**: Complete activity logs with timestamps
- **File Storage**: Permanent storage of uploaded files and analysis results
- **Modern UI**: Clean, responsive interface with smooth animations
- **Real-time Processing**: Live updates during document processing
- **Download Reports**: Export analysis results as text files
- **Server Ready**: Deployment-ready with Docker support

## 🚀 Quick Start

### ⚡ 60-Second Setup

#### Option 1: Automated Setup (Recommended)

```bash
# Navigate to project directory
cd "/Users/learnbay/Desktop/medi_budai"

# Run automated setup
./setup.sh

# Add your OpenAI API key to .env file
# Edit .env and set OPENAI_API_KEY=sk-...

# Start the application (development server)
python3 app.py
```

#### Option 2: Manual Setup

```bash
# Navigate to project directory
cd "/Users/champ/Desktop/1. medi_budai"

# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# Test your OpenAI key works before running the full app
python3 test_scripts/test_openai.py

# Run application (development server)
python3 app.py
```

### 🔑 Getting Your OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create account
3. Click "Create new secret key"
4. Copy the key and paste it in your `.env` file

### Prerequisites

- Python 3.8 or higher
- OpenAI API key
- Modern web browser
- 512MB RAM minimum
- 100MB storage + space for uploaded files
- Internet connection (for OpenAI API calls)

## ▶️ Running the Application (all methods)

There are three ways to run MediBudAI, in increasing order of production-readiness. All of them read configuration from `.env` in the project root.

### 1. Development server (Flask's built-in server)

Fine for local testing only — single-threaded-ish, not for production traffic.

```bash
source venv/bin/activate
python3 app.py
# Serves on FLASK_HOST:FLASK_PORT from .env (default 127.0.0.1:5001)
```

### 2. Gunicorn (production WSGI server, run directly on your machine/server)

This is what `Dockerfile` runs internally, and what `DEPLOYMENT.md`'s systemd/supervisor examples expect. `wsgi.py` exposes the Flask app as `application`.

```bash
source venv/bin/activate
pip install -r requirements.txt   # gunicorn is already pinned in requirements.txt

gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 4 \
  --threads 2 \
  --timeout 180 \
  --access-logfile - \
  --error-logfile - \
  wsgi:application
```

`--threads 2` (or more) matters here specifically: this app makes an OpenAI API call per uploaded file, which is I/O-bound, so threads let one worker process serve several concurrent slow requests instead of blocking on each one. Adjust `--workers`/`--threads` via the `GUNICORN_WORKERS`/`GUNICORN_THREADS`/`GUNICORN_TIMEOUT` env vars if you're scripting this.

### 3. Docker / Docker Compose (recommended for servers)

The container now runs Gunicorn internally (not the dev server) — see `Dockerfile`.

```bash
# Configure environment first
cp .env.example .env
nano .env   # set OPENAI_API_KEY and any overrides

# Option A: Docker Compose (recommended — handles volumes, env, healthcheck)
docker compose up -d --build    # build image and start container
docker compose logs -f          # tail logs
docker compose ps               # list this project's containers + health/port
docker compose down             # stop and remove container + network

# Option B: Plain Docker
docker build -t medibudai .
docker run -d \
  --name medibudai \
  -p 5000:5000 \
  --env-file .env \
  -v "$(pwd)/uploads:/app/uploads" \
  -v "$(pwd)/output:/app/output" \
  -v "$(pwd)/logs:/app/logs" \
  medibudai
```

> Note: `docker-compose` (hyphenated, v1) also works if that's what you have installed — the examples above use the newer `docker compose` (v2, bundled with Docker Desktop).

Verify the container came up correctly:

```bash
curl http://localhost:5000/api/health
# {"status": "healthy", "openai_configured": true, ...}
```

**Listing and stopping containers:**

```bash
docker ps                       # list all running containers (any project)
docker ps -a                    # include stopped containers
docker compose ps               # list only this project's container(s)

docker compose stop             # stop the container, keep it (and volumes/network) around
docker compose start            # start it again
docker compose down             # stop AND remove the container + network (uploads/output/logs on disk are untouched — they're bind mounts)

# Plain Docker equivalents (if you used `docker run` instead of compose):
docker stop medibudai           # graceful stop (SIGTERM, then SIGKILL after a timeout)
docker kill medibudai           # force stop immediately (SIGKILL)
docker rm medibudai             # remove the stopped container
```

**Troubleshooting:**
- **Port 5000 already in use** — on macOS this is commonly the AirPlay Receiver (System Settings → General → AirPlay & Handoff), which also listens on port 5000. Either turn that off, or change the host-side port mapping (e.g. `"5001:5000"` in `docker-compose.yml`, or `-p 5001:5000` for plain Docker) and browse to `http://localhost:5001`.
- **`mkdir ... operation not permitted` on the `uploads`/`output`/`logs` mount** — macOS restricts app access to `Desktop`/`Documents`/`Downloads`. Grant Docker Desktop access via System Settings → Privacy & Security → Files and Folders (or Full Disk Access), then restart Docker Desktop.

## 🎯 Using the Application

1. **Start the server**: `python3 app.py` (or Gunicorn/Docker — see above)
2. **Open browser**: Go to `http://localhost:5001` (or the configured port)
3. **Upload PDF(s)**: Drag & drop or click to select one or more medical documents (up to `MAX_FILES_PER_UPLOAD`, default 10) — they're parsed and analyzed **concurrently**
4. **Add Comments**: Optionally add contextual notes; these apply to every document in the batch
5. **Get Analysis**: Click "Analyze Document(s)" and wait for AI processing
6. **Review Results**: One result card per file, each with its own report ID, model used, and analysis time — failed files are shown individually without blocking the successful ones
7. **Download Report(s)**: Save a single report or all reports in the batch as text files

## 🔧 Configuration Options

### Environment Variables (.env)

```env
# Required
OPENAI_API_KEY=sk-your-api-key-here

# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_ENV=development
FLASK_DEBUG=True

# File Configuration
SECRET_KEY=your-secret-key
MAX_CONTENT_LENGTH=67108864   # 64MB max TOTAL request size (sum of all files in a batch)
MAX_FILE_SIZE=16777216        # 16MB max size for any single file
MAX_FILES_PER_UPLOAD=10       # Max number of files accepted in one upload request
MAX_CONCURRENT_ANALYSES=4     # How many files are parsed/analyzed in parallel per request
UPLOAD_FOLDER=uploads
OUTPUT_FOLDER=output
LOGS_FOLDER=logs

# Logging
LOG_LEVEL=INFO                # DEBUG for verbose per-file tracing
OPENAI_STARTUP_CHECK=true     # Live-test the OpenAI key once at process startup

# Gunicorn (used by Dockerfile / manual gunicorn runs)
GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=180
```

### Supported File Types

- **PDF files only** (up to 16MB)
- Medical reports, lab results, prescriptions, discharge summaries, etc.

### Local Development

1. **Clone or download the project**
   ```bash
   cd /path/to/medi_budai
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your API key**
   
   Edit the `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_actual_openai_api_key_here
   ```

4. **Start the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   
   Navigate to `http://localhost:5001`

### Production Deployment

For production deployment on any server, see the detailed [DEPLOYMENT.md](DEPLOYMENT.md) guide.

**Quick production deployment:**
```bash
# 1. Upload files to your server
# 2. Run deployment script
./deploy.sh

# 3. Configure for production
cp .env.example .env
nano .env  # Set your API key and production settings

# 4. Start with production settings
FLASK_ENV=production FLASK_HOST=0.0.0.0 python app.py
```

**Docker deployment:**
```bash
docker-compose up -d
```

## 📁 Project Structure

```
medi_budai/
├── app.py                 # Flask backend application
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables (configure this!)
├── wsgi.py               # WSGI entry point for production
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose setup
├── setup.sh             # Automated setup script
├── deploy.sh            # Deployment automation
├── test_scripts/        # Test and utility scripts
│   ├── test_openai.py   # OpenAI API test script
│   └── test_setup.py    # Setup validation script
├── uploads/             # Uploaded files storage
├── output/              # Analysis results storage
├── logs/                # Application logs (JSON format)
├── static/
│   ├── css/
│   │   └── style.css    # Frontend styles
│   └── js/
│       └── app.js       # Frontend JavaScript
├── templates/
│   └── index.html       # Main HTML template
├── README.md            # This comprehensive guide
├── FEATURES.md          # Detailed feature documentation
└── DEPLOYMENT.md        # Production deployment guide
```

## 🔧 Configuration

## 🚨 Common Issues & Solutions

### Issue: "OpenAI API key not set"
**Solution**: Edit `.env` file and set your API key

### Issue: "Module not found" errors
**Solution**: Run `pip install -r requirements.txt`

### Issue: "Permission denied" on setup.sh
**Solution**: Run `chmod +x setup.sh`

### Issue: Port 5001 already in use
**Solution**: Kill other processes using port 5001 or change port in `.env` file

### Issue: File upload errors
**Solution**: Ensure file is PDF format and under 16MB

## 📊 Sample Analysis Output

The system provides structured medical analysis including:
- **Document Type**: Identifies the medical document type
- **Key Findings**: Important medical observations and test results
- **Diagnoses**: Listed conditions and diagnoses
- **Medications**: Prescribed drugs, dosages, and administration instructions
- **Follow-ups**: Recommended next steps and appointments
- **Risk Assessment**: Health risk evaluation and warnings
- **Summary**: Comprehensive overview of the medical document
- **Recommendations**: Actionable medical insights and advice

Each analysis includes:
- **Unique Report ID**: For tracking and reference
- **Processing Time**: How long the analysis took
- **Model Used**: Which AI model processed the document
- **Timestamp**: When the analysis was performed
- **User Comments**: Any additional context provided

### API Endpoints

- `GET /`: Main application page
- `POST /api/upload`: Upload and analyze one or more medical documents. Send files under the `files` field (multiple allowed, up to `MAX_FILES_PER_UPLOAD`, default 10); an optional `comments` field applies to every file in the batch. Files are parsed and analyzed **concurrently** (thread pool, size configurable via `MAX_CONCURRENT_ANALYSES`). Returns `200` if every file succeeded, `207` if some succeeded and some failed, `400` if all failed — always with a `results` array containing one entry per file (`success`, `analysis` or `error`, `model_used`, timings, etc).
- `GET /api/logs/<date>`: Daily activity log (JSON) for a given date (`YYYY-MM-DD`)
- `GET /api/report/<report_id>`: Retrieve a saved analysis report by ID
- `GET /api/stats`: Aggregate usage statistics across all logged days
- `GET /api/health`: Health check endpoint (also reports whether an OpenAI key is configured)

## 🤖 AI Analysis Features

The system provides comprehensive analysis of medical documents including:

1. **Document Type Identification**: Automatically identifies the type of medical document
2. **Key Medical Findings**: Extracts and summarizes important medical observations
3. **Diagnosed Conditions**: Lists any diagnoses mentioned in the document
4. **Prescribed Medications**: Identifies medications and dosages
5. **Recommended Follow-ups**: Extracts follow-up care instructions
6. **Risk Assessment**: Provides risk analysis based on document content
7. **Summary and Recommendations**: Comprehensive overview and actionable insights

## 🛡️ Privacy & Security

- **File Validation**: Only PDF files accepted, with size limits (16MB max)
- **Secure Processing**: Files are processed locally and stored securely
- **Unique Tracking**: Each analysis gets a unique ID for organization
- **Comprehensive Logging**: All activities logged with timestamps
- **Encrypted Communication**: All OpenAI API communication is encrypted
- **Input Sanitization**: All user inputs are validated and sanitized
- **Secure File Handling**: Safe filename processing and storage

## ⚠️ Important Disclaimers

- **FOR EDUCATIONAL PURPOSES ONLY**
- **NOT A SUBSTITUTE FOR PROFESSIONAL MEDICAL ADVICE**
- **ALWAYS CONSULT HEALTHCARE PROVIDERS**
- **AI ANALYSIS MAY CONTAIN ERRORS**
- **NOT FOR CLINICAL DECISION MAKING**

## 📞 Need Help?

1. **Check Setup**: Run `python3 test_scripts/test_openai.py` to test your configuration
2. **View Logs**: Check terminal output and log files in the `logs/` folder
3. **Browser Console**: Press F12 to view frontend errors
4. **Documentation**: Check [FEATURES.md](FEATURES.md) and [DEPLOYMENT.md](DEPLOYMENT.md)

## 🎉 You're All Set!

Your MediBudAI system is ready to analyze medical documents with AI-powered insights.

**Next Steps:**
- Upload a sample PDF medical document
- Try adding comments to provide context
- Explore the unique tracking and logging features
- Download and review the generated reports
- Check the comprehensive logs in the `logs/` folder

## 🎨 Frontend Features

- **Responsive Design**: Works on desktop, tablet, and mobile
- **Drag & Drop**: Intuitive file upload interface
- **Real-time Feedback**: Loading animations and progress indicators
- **Error Handling**: User-friendly error messages
- **Export Functionality**: Download analysis results
- **Modern UI**: Clean, professional medical theme

## 📝 Usage Examples

### Basic Usage

1. **Upload Document**: Drag a PDF medical document onto the upload area or click to browse
2. **Wait for Analysis**: The system will process and analyze your document
3. **Review Results**: View the structured analysis results
4. **Download Report**: Export the analysis as a text file

### Supported Document Types

- Lab reports
- Radiology reports
- Discharge summaries
- Prescription records
- Medical consultation notes
- Pathology reports
- Any other medical PDF documents

## ⚠️ Important Disclaimers

- **Educational Purpose Only**: This tool is for informational and educational purposes only
- **Not Medical Advice**: Results should not replace professional medical consultation
- **Data Privacy**: Uploaded files are processed temporarily and then deleted
- **Accuracy**: AI analysis may not be 100% accurate - always verify with healthcare professionals

## 🔧 Development

### Running in Development Mode

```bash
# Set environment variables
export FLASK_ENV=development
export FLASK_DEBUG=True

# Run the application
python app.py
```

### API Testing

```bash
# Health check (also reports whether an OpenAI key is configured)
curl http://localhost:5001/api/health

# Single-file upload
curl -X POST -F "files=@test_document.pdf" http://localhost:5001/api/upload

# Multi-file upload — note the repeated "files" field, and an optional shared comment
curl -X POST \
  -F "files=@report1.pdf" \
  -F "files=@report2.pdf" \
  -F "files=@report3.pdf" \
  -F "comments=Flag anything related to blood pressure" \
  http://localhost:5001/api/upload

# Response is a batch object: {"batch_id", "total_files", "successful", "failed",
# "results": [{...one entry per file...}]}. HTTP 200 = all succeeded, 207 = mixed
# success/failure, 400 = all failed.
```

## 🛠️ Customization

### Modifying AI Prompts

Edit the `analyze_medical_document()` function in `app.py` to customize the AI analysis prompts and response format.

### Styling Changes

Modify `static/css/style.css` to customize the appearance and branding.

### Adding New Features

- Add new API endpoints in `app.py`
- Extend the frontend in `static/js/app.js`
- Update the UI in `templates/index.html`

## 📚 Dependencies

### Backend
- **Flask**: Web framework
- **OpenAI**: AI analysis
- **PyPDF2**: PDF text extraction
- **Flask-CORS**: Cross-origin requests
- **python-dotenv**: Environment management

### Frontend
- **Vanilla JavaScript**: No frameworks required
- **Modern CSS**: Grid, Flexbox, animations
- **Web APIs**: File API, Fetch API

## 🤝 Contributing

This is a demonstration project. Feel free to fork and modify for your needs.

## 📄 License

This project is for educational and demonstration purposes.

## 🆘 Troubleshooting

### Common Issues

1. **OpenAI API Key Error**
   - Make sure you have set `OPENAI_API_KEY` in your `.env` file
   - Verify your API key is valid and has sufficient credits
   - Run `python3 test_scripts/test_openai.py` to test your API key

2. **File Upload Issues**
   - Ensure the file is a valid PDF
   - Check that file size is under 16MB
   - Verify the `uploads/` directory exists and has proper permissions

3. **Analysis Failures**
   - Check your internet connection
   - Verify OpenAI API status
   - Look at console logs and log files for detailed error messages

4. **Port Already in Use**
   - Change `FLASK_PORT` in `.env` file
   - Kill processes using the current port: `lsof -ti:5001 | xargs kill -9`

5. **Module Import Errors**
   - Ensure you're using the correct Python environment
   - Run `pip install -r requirements.txt` to install dependencies

### Logs and Debugging

- Check the terminal where you ran `python app.py` for server logs
- Review JSON log files in the `logs/` directory for detailed activity logs
- Open browser developer tools (F12) for frontend errors
- Enable Flask debug mode for detailed error pages
- Use `python3 test_scripts/test_openai.py` to test OpenAI connectivity

## 📞 Support

This is a comprehensive medical document analysis system for educational and demonstration purposes.

For issues:
1. Check the troubleshooting section above
2. Review the detailed documentation in FEATURES.md and DEPLOYMENT.md
3. Test your setup with `python3 test_scripts/test_openai.py`
4. Check log files in the `logs/` directory
5. Review the code comments for implementation details

---

**Made with ❤️ for medical AI education and demonstration purposes.**
**Happy analyzing! 🏥🤖**
