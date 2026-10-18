# 🚀 MediBudAI Deployment Guide

This guide explains how to deploy MediBudAI on any server with minimal configuration changes.

## 📋 Quick Deployment Options

### Option 1: Automated Script Deployment (Recommended)
```bash
# 1. Upload project files to your server
# 2. Run the deployment script
./deploy.sh

# 3. Edit .env file with your settings
nano .env

# 4. Start the application
source venv/bin/activate
python app.py
```

### Option 2: Docker Deployment
```bash
# 1. Copy .env.example to .env and configure
cp .env.example .env
nano .env

# 2. Build and run with Docker Compose
docker-compose up -d
```

### Option 3: Manual Deployment
```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Create directories
mkdir -p uploads output logs

# 4. Run application
python app.py
```

## 🔧 Configuration

### Environment Variables (.env)

All paths are relative to the application directory:

```env
# Required: OpenAI API Key
OPENAI_API_KEY=your_api_key_here

# Server Configuration
FLASK_HOST=0.0.0.0          # 0.0.0.0 for external access
FLASK_PORT=5000             # Port number
FLASK_ENV=production        # production/development
FLASK_DEBUG=False           # False for production

# Security
SECRET_KEY=your_secret_key_here

# File Settings
MAX_CONTENT_LENGTH=16777216 # 16MB file size limit

# Directory Configuration (relative paths)
UPLOAD_FOLDER=uploads       # Uploaded PDF files
OUTPUT_FOLDER=output        # Analysis results
LOGS_FOLDER=logs           # Activity logs
```

## 🌐 Server Deployment

### Local Development
```bash
# Listen on localhost only
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

### Production Server
```bash
# Listen on all interfaces
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### Behind Reverse Proxy
```bash
# Flask behind nginx/apache
FLASK_HOST=127.0.0.1
FLASK_PORT=8000
```

## 🏗️ Directory Structure

The application creates these directories relative to its location:

```
your-deployment-directory/
├── app.py                  # Main application
├── .env                    # Configuration (create this)
├── uploads/                # PDF file storage (auto-created)
├── output/                 # Analysis reports (auto-created)
├── logs/                   # Activity logs (auto-created)
├── static/                 # Frontend assets
├── templates/              # HTML templates
├── venv/                   # Python virtual environment
└── requirements.txt        # Dependencies
```

## 🐳 Docker Deployment

### Simple Docker Run
```bash
# Build the image
docker build -t medibudai .

# Run the container
docker run -d \
  --name medibudai \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  medibudai
```

### Docker Compose (Recommended)
```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## 🔒 Production Security

### 1. Environment Security
```bash
# Generate strong secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Set secure file permissions
chmod 600 .env
chmod 755 uploads output logs
```

### 2. Reverse Proxy (Nginx Example)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 20M;
    }
}
```

### 3. SSL/HTTPS
```bash
# Use Let's Encrypt with certbot
certbot --nginx -d your-domain.com
```

## 📊 Monitoring & Maintenance

### Log Monitoring
```bash
# View application logs
tail -f logs/activity_$(date +%Y-%m-%d).json

# Monitor disk usage
df -h uploads/ output/ logs/
```

### Health Check
```bash
# Application health endpoint
curl http://your-server:5000/api/health

# Get statistics
curl http://your-server:5000/api/stats
```

### Cleanup Scripts
```bash
# Clean old files (example - adjust retention as needed)
find uploads/ -name "*.pdf" -mtime +30 -delete
find output/ -name "*.txt" -mtime +30 -delete
find logs/ -name "*.json" -mtime +90 -delete
```

## 🔧 Process Management

### Using Systemd (Linux)
```ini
# /etc/systemd/system/medibudai.service
[Unit]
Description=MediBudAI Medical Document Analysis
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/medibudai
Environment=PATH=/path/to/medibudai/venv/bin
ExecStart=/path/to/medibudai/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable medibudai
sudo systemctl start medibudai
sudo systemctl status medibudai
```

### Using Supervisor
```ini
# /etc/supervisor/conf.d/medibudai.conf
[program:medibudai]
command=/path/to/medibudai/venv/bin/python app.py
directory=/path/to/medibudai
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/supervisor/medibudai.log
```

## 🚀 Production WSGI Deployment

### Using Gunicorn
```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 wsgi:application
```

### Gunicorn Configuration (gunicorn.conf.py)
```python
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 120
keepalive = 2
```

## 📋 Deployment Checklist

- [ ] Copy all application files to server
- [ ] Create and configure .env file
- [ ] Set OPENAI_API_KEY
- [ ] Set production environment variables
- [ ] Create upload/output/logs directories
- [ ] Set proper file permissions
- [ ] Install Python dependencies
- [ ] Test application startup
- [ ] Configure reverse proxy (if needed)
- [ ] Set up SSL/HTTPS
- [ ] Configure process management
- [ ] Set up monitoring and alerts
- [ ] Configure log rotation
- [ ] Set up backup procedures

## 🆘 Troubleshooting

### Common Issues

1. **Permission Errors**
   ```bash
   chmod 755 uploads output logs
   chown -R www-data:www-data /path/to/medibudai
   ```

2. **Port Already in Use**
   ```bash
   # Change FLASK_PORT in .env file
   FLASK_PORT=8000
   ```

3. **OpenAI API Errors**
   ```bash
   # Check API key in .env
   # Verify internet connectivity
   # Check API quota and billing
   ```

4. **File Upload Issues**
   ```bash
   # Check nginx/apache upload limits
   # Verify disk space
   # Check directory permissions
   ```

### Log Locations

- **Application Logs**: `logs/activity_YYYY-MM-DD.json`
- **System Logs**: `/var/log/syslog` (Linux)
- **Supervisor Logs**: `/var/log/supervisor/medibudai.log`
- **Nginx Logs**: `/var/log/nginx/access.log` `/var/log/nginx/error.log`

## 🎯 Performance Optimization

1. **Use a reverse proxy** (nginx/apache)
2. **Enable gzip compression**
3. **Set up caching** for static files
4. **Use multiple workers** with Gunicorn
5. **Monitor resource usage**
6. **Implement log rotation**
7. **Set up file cleanup policies**

This deployment configuration ensures MediBudAI can run on any server with minimal path-specific changes!
