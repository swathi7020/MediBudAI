import os
import json
import logging
import threading
import uuid
import mimetypes

mimetypes.add_type("text/css", ".css")
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from logging.handlers import RotatingFileHandler

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import PyPDF2
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API key authentication
API_KEY = os.getenv("API_KEY")


def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")

        if not API_KEY:
            return jsonify({"error": "API key is not configured"}), 500

        if provided_key != API_KEY:
            return jsonify({"error": "Invalid or missing API key"}), 401

        return f(*args, **kwargs)


    return decorated

# ---------------------------------------------------------------------------
# Paths / directories (computed before logging is configured, since the log
# file lives under LOGS_FOLDER)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, os.getenv('UPLOAD_FOLDER', 'uploads'))
OUTPUT_FOLDER = os.path.join(BASE_DIR, os.getenv('OUTPUT_FOLDER', 'output'))
LOGS_FOLDER = os.path.join(BASE_DIR, os.getenv('LOGS_FOLDER', 'logs'))

for _folder in (UPLOAD_FOLDER, OUTPUT_FOLDER, LOGS_FOLDER):
    os.makedirs(_folder, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
#
# Structured, timestamped logging to both the console (picked up by
# `docker-compose logs` / gunicorn's --access-logfile -/--error-logfile -)
# and a rotating file under logs/app.log so history survives container
# restarts as long as the logs/ volume is mounted.
#
# LOG_LEVEL is configurable via env (.env / docker-compose) without a code
# change: DEBUG for verbose per-file tracing, INFO for normal operation.
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
_LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(threadName)s | %(name)s | %(message)s'


def configure_logging():
    formatter = logging.Formatter(_LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Reconfiguring is safe to call more than once (e.g. reloader/tests)
    # without stacking duplicate handlers.
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        os.path.join(LOGS_FOLDER, 'app.log'),
        maxBytes=5 * 1024 * 1024,  # 5MB per file
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Third-party libraries are noisy at DEBUG; keep them quiet unless we're
    # specifically debugging HTTP/OpenAI transport issues.
    for noisy_logger in ('httpx', 'httpcore', 'openai', 'urllib3'):
        logging.getLogger(noisy_logger).setLevel('WARNING')


configure_logging()
logger = logging.getLogger('medibudai')
logger.info("Logging configured (level=%s, file=%s)", LOG_LEVEL, os.path.join(LOGS_FOLDER, 'app.log'))

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.after_request
def fix_static_mime(response):
    if request.path.endswith(".css"):
        response.headers["Content-Type"] = "text/css; charset=utf-8"
    return response
CORS(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 67108864))  # 64MB total request
app.config['BASE_DIR'] = BASE_DIR
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['LOGS_FOLDER'] = LOGS_FOLDER

# Per-file size cap (independent of the aggregate MAX_CONTENT_LENGTH above,
# which bounds the whole multi-file request body).
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 16777216))  # 16MB per file
# How many files a single upload request may contain.
MAX_FILES_PER_UPLOAD = int(os.getenv('MAX_FILES_PER_UPLOAD', 10))
# How many files are analyzed concurrently (thread pool size). Keep this
# modest — it's bounded by both OpenAI rate limits and gunicorn worker count.
MAX_CONCURRENT_ANALYSES = int(os.getenv('MAX_CONCURRENT_ANALYSES', 4))
# Whether to make a live OpenAI call at process startup to verify the key.
# Set to false to skip (e.g. in CI, or to avoid the extra API call on every
# gunicorn worker boot).
OPENAI_STARTUP_CHECK = os.getenv('OPENAI_STARTUP_CHECK', 'true').lower() == 'true'

ALLOWED_EXTENSIONS = {'pdf'}

logger.info(
    "Config: MAX_FILE_SIZE=%dMB, MAX_FILES_PER_UPLOAD=%d, MAX_CONCURRENT_ANALYSES=%d",
    MAX_FILE_SIZE // (1024 * 1024), MAX_FILES_PER_UPLOAD, MAX_CONCURRENT_ANALYSES
)

# ---------------------------------------------------------------------------
# OpenAI client — initialized ONCE per process (not per-request).
#
# Bug fixed here: the original code re-tested the API key with a live
# `chat.completions.create` call inside `get_openai_client()` every single
# time no cached client existed yet. Because the connectivity self-test only
# ran from the `if __name__ == "__main__":` block, it never executed when
# the app was launched via `wsgi:application` under Gunicorn — meaning under
# Gunicorn, every single analysis request paid for an extra throwaway
# "test" completion before doing the real one. This version initializes and
# validates the client exactly once at import time (i.e. once per worker
# process, whether started via `python app.py` or via Gunicorn/wsgi.py),
# then reuses the cached client for every request.
# ---------------------------------------------------------------------------
openai_client = None
_openai_client_lock = threading.Lock()
_PLACEHOLDER_KEY = 'your_openai_api_key_here_replace_this_with_valid_key'


def initialize_openai_client(run_connectivity_check=True):
    """Create and cache the OpenAI client. Safe to call multiple times;
    only does real work the first time (guarded by _openai_client_lock)."""
    global openai_client

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or api_key in (_PLACEHOLDER_KEY, 'your_openai_api_key_here'):
        logger.error("OpenAI API key not configured. Set OPENAI_API_KEY in .env")
        openai_client = None
        return None

    try:
        client = OpenAI(api_key=api_key)
        if run_connectivity_check:
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            logger.info("OpenAI client initialized and connectivity verified")
        else:
            logger.info("OpenAI client initialized (startup connectivity check skipped)")
        openai_client = client
        return client
    except Exception as e:
        logger.error("Failed to initialize OpenAI client: %s", e)
        openai_client = None
        return None


def get_openai_client():
    """Return the cached OpenAI client, initializing it once if needed."""
    global openai_client
    if openai_client is not None:
        return openai_client
    with _openai_client_lock:
        if openai_client is None:
            initialize_openai_client(run_connectivity_check=False)
    return openai_client


# Run the (optional) live connectivity check exactly once, at process/module
# import time — this covers both `python app.py` and Gunicorn workers
# importing `wsgi.py`, each of which imports this module exactly once.
if os.getenv('OPENAI_API_KEY'):
    initialize_openai_client(run_connectivity_check=OPENAI_STARTUP_CHECK)
else:
    logger.warning(
        "OPENAI_API_KEY not set — document analysis will fail until it is configured in .env"
    )

# ---------------------------------------------------------------------------
# Daily activity log (JSON) — written to by every worker thread, so access
# is serialized with a lock to avoid lost updates from concurrent
# read-modify-write cycles when several files are analyzed in parallel.
# ---------------------------------------------------------------------------
_daily_log_lock = threading.Lock()


def generate_unique_id():
    return str(uuid.uuid4())


def get_daily_log_file():
    today = date.today().isoformat()
    return os.path.join(app.config['LOGS_FOLDER'], f'activity_{today}.json')


def load_daily_log():
    log_file = get_daily_log_file()
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Could not load log file %s, creating new one", log_file)

    return {
        'date': date.today().isoformat(),
        'uploads': [],
        'total_uploads': 0,
        'successful_analyses': 0,
        'failed_analyses': 0,
        'models_used': {},
        'file_types': {},
    }


def save_daily_log(log_data):
    log_file = get_daily_log_file()
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error("Failed to save log file: %s", e)


def log_upload_activity(report_id, filename, file_size, user_comments,
                         model_used, success, analysis_time, error_msg=None):
    """Log upload and analysis activity. Thread-safe (guarded by
    _daily_log_lock) since multiple files in a batch are processed
    concurrently and all write to the same daily log file."""
    with _daily_log_lock:
        log_data = load_daily_log()

        upload_entry = {
            'report_id': report_id,
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'file_size': file_size,
            'has_user_comments': bool(user_comments),
            'model_used': model_used,
            'success': success,
            'analysis_time_seconds': analysis_time,
            'error_message': error_msg,
        }

        log_data['uploads'].append(upload_entry)
        log_data['total_uploads'] += 1

        if success:
            log_data['successful_analyses'] += 1
            log_data['models_used'][model_used] = log_data['models_used'].get(model_used, 0) + 1
        else:
            log_data['failed_analyses'] += 1

        file_ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
        log_data['file_types'][file_ext] = log_data['file_types'].get(file_ext, 0) + 1

        save_daily_log(log_data)


def save_analysis_output(report_id, filename, analysis, user_comments=None):
    """Save analysis output to a text file. Each report_id is unique (UUID),
    so concurrent writes from different files never touch the same path."""
    output_file = os.path.join(app.config['OUTPUT_FOLDER'], f'{report_id}_analysis.txt')

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("MEDICAL DOCUMENT ANALYSIS REPORT\n")
            f.write("Generated by MediBudAI\n")
            f.write("=" * 50 + "\n\n")

            f.write(f"Report ID: {report_id}\n")
            f.write(f"Original Filename: {filename}\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            if user_comments:
                f.write(f"User Comments: {user_comments}\n")

            f.write("\n" + "=" * 50 + "\n\n")

            f.write("DOCUMENT TYPE\n")
            f.write(f"{analysis.get('document_type', 'Not specified')}\n\n")

            f.write("KEY FINDINGS\n")
            f.write(f"{analysis.get('key_findings', 'Not specified')}\n\n")

            f.write("DIAGNOSES\n")
            f.write(f"{analysis.get('diagnoses', 'Not specified')}\n\n")

            f.write("MEDICATIONS\n")
            f.write(f"{analysis.get('medications', 'Not specified')}\n\n")

            f.write("FOLLOW-UPS\n")
            f.write(f"{analysis.get('follow_ups', 'Not specified')}\n\n")

            f.write("RISK ASSESSMENT\n")
            f.write(f"{analysis.get('risk_assessment', 'Not specified')}\n\n")

            f.write("SUMMARY\n")
            f.write(f"{analysis.get('summary', 'Not specified')}\n\n")

            f.write("RECOMMENDATIONS\n")
            f.write(f"{analysis.get('recommendations', 'Not specified')}\n\n")

            f.write("=" * 50 + "\n")
            f.write("DISCLAIMER: This analysis is for informational purposes only and should not replace professional medical advice.\n")
            f.write("Generated by MediBudAI - AI-powered medical document analysis\n")

        logger.debug("Analysis saved to: %s", output_file)
        return output_file

    except IOError as e:
        logger.error("Failed to save analysis output for report %s: %s", report_id, e)
        return None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_responses_api_model(model):
    """GPT-5.x and o-series models use the Responses API."""
    return model.startswith(("gpt-5", "o1", "o3", "o4"))


def call_openai_for_analysis(client, model, system_prompt, user_prompt):
    """Route to Responses API (GPT-5.x) or Chat Completions (GPT-4o)."""
    if is_responses_api_model(model):
        response = client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            temperature=0.2,
            max_output_tokens=3000,
            text={"format": {"type": "json_object"}},
        )
        return response.output_text

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def extract_text_from_pdf(file_path):
    """Extract text from PDF file."""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error("Error extracting text from PDF %s: %s", file_path, e)
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def analyze_medical_document(text, file_path=None, user_comments=None, log_prefix=""):
    """Analyze medical document using OpenAI. Tries gpt-5.4-mini first (via
    the Responses API), falling back to gpt-4o then gpt-4o-mini (Chat
    Completions API) if the primary model errors or is unavailable."""
    start_time = datetime.now()
    model_used = None

    try:
        system_prompt = """
        You are a specialized medical AI assistant with expertise in analyzing medical documents, reports, and health data.
        You must provide a comprehensive, structured analysis of medical documents.

        Your analysis should include:
        1. Document Type Identification - What type of medical document this is
        2. Key Medical Findings - The most important medical observations, test results, or findings
        3. Diagnosed Conditions - Any diseases, conditions, or medical diagnoses mentioned
        4. Prescribed Medications - All medications, dosages, and administration instructions
        5. Recommended Follow-ups - Any follow-up appointments, tests, or procedures recommended
        6. Risk Assessment - Assessment of health risks based on the findings
        7. Summary - A concise overview of the document's contents
        8. Recommendations - Clinical recommendations and next steps

        CRITICAL: You must respond with a valid JSON object using exactly these keys:
        {
            "document_type": "string",
            "key_findings": "string",
            "diagnoses": "string",
            "medications": "string",
            "follow_ups": "string",
            "risk_assessment": "string",
            "summary": "string",
            "recommendations": "string"
        }

        If any information is not available, use "Not specified" or "None found".
        Be thorough but concise. Focus on medical accuracy and clinical relevance.
        """

        user_prompt = f"""
        Please analyze this medical document text and provide a structured JSON response:

        DOCUMENT TEXT:
        {text}
        """

        if user_comments and user_comments.strip():
            user_prompt += f"""

        ADDITIONAL USER COMMENTS/CONTEXT:
        {user_comments.strip()}

        Please consider these additional comments when analyzing the document and provide more focused insights based on the user's specific interests or concerns.
        """

        user_prompt += "\n\nProvide your analysis as a valid JSON object with the specified structure."

        client = get_openai_client()
        if not client:
            logger.error("%s OpenAI client unavailable — API key missing or invalid", log_prefix)
            return {
                'error': 'OpenAI API is not configured. Please set a valid API key in .env file',
            }, None, (datetime.now() - start_time).total_seconds()

        main_model_to_try = ["gpt-5.4-mini"]
        backup_models_to_try = ["gpt-4o", "gpt-4o-mini"]
        models_to_try = main_model_to_try + backup_models_to_try

        analysis_text = None
        last_error = None
        for model in models_to_try:
            try:
                logger.debug("%s Trying model: %s", log_prefix, model)
                analysis_text = call_openai_for_analysis(client, model, system_prompt, user_prompt)
                model_used = model
                logger.info("%s Model succeeded: %s", log_prefix, model)
                break
            except Exception as model_error:
                last_error = model_error
                logger.warning("%s Model %s failed: %s", log_prefix, model, model_error)
                continue

        if analysis_text is None:
            raise last_error or Exception("All configured models failed")

        try:
            analysis_json = json.loads(analysis_text)
            required_keys = [
                "document_type", "key_findings", "diagnoses",
                "medications", "follow_ups", "risk_assessment",
                "summary", "recommendations",
            ]
            for key in required_keys:
                if key not in analysis_json:
                    analysis_json[key] = "Not specified"

        except json.JSONDecodeError:
            logger.warning("%s Model response was not valid JSON, using raw-text fallback", log_prefix)
            analysis_json = {
                "document_type": "Medical Document",
                "key_findings": (analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text),
                "diagnoses": "Please review the full analysis text",
                "medications": "Please review the full analysis text",
                "follow_ups": "Please review the full analysis text",
                "risk_assessment": "Please review the full analysis text",
                "summary": analysis_text,
                "recommendations": "Consult with healthcare provider for detailed interpretation",
            }

        analysis_time = (datetime.now() - start_time).total_seconds()
        return analysis_json, model_used, analysis_time

    except Exception as error:
        analysis_time = (datetime.now() - start_time).total_seconds()
        logger.error("%s Error analyzing medical document: %s", log_prefix, error)
        raise Exception(f"Failed to analyze document: {str(error)}") from error


def process_single_document(task, user_comments, batch_id):
    """Full pipeline for ONE file: save -> extract text -> analyze -> persist
    output -> log activity. Designed to run inside a worker thread submitted
    by ThreadPoolExecutor from the /api/upload handler, so multiple files in
    the same upload are parsed and analyzed concurrently instead of one at a
    time. Returns a plain dict (JSON-serializable), never raises — every
    failure path is caught and reported back as a per-file result so one bad
    file in a batch doesn't sink the whole request.
    """
    report_id = task['report_id']
    filename = task['original_filename']
    file_bytes = task['file_bytes']
    file_size = task['file_size']
    start_time = datetime.now()
    model_used = None
    stored_filename = None

    log_prefix = f"[batch:{batch_id[:8]}][report:{report_id[:8]}][{filename}]"
    logger.info("%s Starting processing (%.1f KB)", log_prefix, file_size / 1024)

    try:
        secure_name = secure_filename(filename) or 'document.pdf'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        stored_filename = f"{report_id}_{timestamp}{secure_name}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)

        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        logger.debug("%s Saved upload to %s", log_prefix, file_path)

        extracted_text = extract_text_from_pdf(file_path)
        logger.debug("%s Extracted %d characters of text", log_prefix, len(extracted_text))

        if not extracted_text.strip():
            analysis_time = (datetime.now() - start_time).total_seconds()
            error_msg = "No text could be extracted from the PDF (it may be a scanned image without OCR text)"
            logger.warning("%s %s", log_prefix, error_msg)
            log_upload_activity(report_id, filename, file_size, user_comments, None, False, analysis_time, error_msg)
            return {
                'report_id': report_id,
                'filename': filename,
                'stored_filename': stored_filename,
                'success': False,
                'error': error_msg,
                'analysis_time_seconds': round(analysis_time, 2),
            }

        analysis, model_used, analysis_time = analyze_medical_document(
            extracted_text, file_path, user_comments, log_prefix=log_prefix
        )

        if isinstance(analysis, dict) and 'error' in analysis:
            logger.error("%s Analysis failed: %s", log_prefix, analysis['error'])
            log_upload_activity(report_id, filename, file_size, user_comments, model_used, False, analysis_time, analysis['error'])
            return {
                'report_id': report_id,
                'filename': filename,
                'stored_filename': stored_filename,
                'success': False,
                'error': analysis['error'],
                'analysis_time_seconds': round(analysis_time, 2),
            }

        output_file = save_analysis_output(report_id, filename, analysis, user_comments)
        log_upload_activity(report_id, filename, file_size, user_comments, model_used, True, analysis_time)

        logger.info("%s Done — model=%s, time=%.2fs", log_prefix, model_used, analysis_time)

        return {
            'report_id': report_id,
            'filename': filename,
            'stored_filename': stored_filename,
            'success': True,
            'analysis': analysis,
            'extracted_text_length': len(extracted_text),
            'user_comments_included': bool(user_comments),
            'model_used': model_used,
            'analysis_time_seconds': round(analysis_time, 2),
            'output_file': output_file,
            'timestamp': datetime.now().isoformat(),
        }

    except Exception as exc:
        analysis_time = (datetime.now() - start_time).total_seconds()
        logger.exception("%s Unhandled error while processing file", log_prefix)
        log_upload_activity(report_id, filename, file_size, user_comments, model_used, False, analysis_time, str(exc))
        return {
            'report_id': report_id,
            'filename': filename,
            'stored_filename': stored_filename,
            'success': False,
            'error': str(exc),
            'analysis_time_seconds': round(analysis_time, 2),
        }


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle one or more file uploads in a single request.

    Accepts multiple files under the 'files' form field (what the current
    frontend sends). Also accepts a single legacy 'file' field for backward
    compatibility with any existing API consumers.

    Files are read into memory in this request-handling thread (FileStorage
    objects aren't safe to touch from other threads), then fanned out to a
    ThreadPoolExecutor so PDF parsing + the OpenAI call for each file happen
    concurrently rather than one after another. A slow/failing file never
    blocks the others, and the response reports per-file success/failure.
    """
    batch_id = generate_unique_id()
    batch_start = datetime.now()

    logger.info("[batch:%s] Upload request received from %s", batch_id[:8], request.remote_addr)

    incoming_files = request.files.getlist('files')
    if not incoming_files:
        legacy_file = request.files.get('file')
        if legacy_file:
            incoming_files = [legacy_file]

    if not incoming_files:
        logger.warning("[batch:%s] Rejected: no files in request", batch_id[:8])
        return jsonify({'error': 'No file(s) provided. Attach one or more PDF files under the "files" field.'}), 400

    if len(incoming_files) > MAX_FILES_PER_UPLOAD:
        logger.warning(
            "[batch:%s] Rejected: %d files exceeds limit of %d",
            batch_id[:8], len(incoming_files), MAX_FILES_PER_UPLOAD
        )
        return jsonify({'error': f'Too many files in one upload. Maximum is {MAX_FILES_PER_UPLOAD}.'}), 400

    user_comments = request.form.get('comments', '').strip()

    prepared_tasks = []
    results = []

    # Validate + read every file up front, in this thread, before dispatching
    # to the executor.
    for storage in incoming_files:
        filename = storage.filename or ''

        if filename == '':
            results.append({'filename': filename, 'success': False, 'error': 'No file selected'})
            continue

        if not allowed_file(filename):
            logger.warning("[batch:%s] Rejected '%s': not a PDF", batch_id[:8], filename)
            results.append({'filename': filename, 'success': False, 'error': 'Only PDF files are allowed'})
            continue

        file_bytes = storage.read()
        file_size = len(file_bytes)

        if file_size == 0:
            results.append({'filename': filename, 'success': False, 'error': 'File is empty'})
            continue

        if file_size > MAX_FILE_SIZE:
            logger.warning("[batch:%s] Rejected '%s': %d bytes exceeds per-file limit", batch_id[:8], filename, file_size)
            results.append({
                'filename': filename, 'success': False,
                'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB per file',
            })
            continue

        prepared_tasks.append({
            'report_id': generate_unique_id(),
            'original_filename': filename,
            'file_bytes': file_bytes,
            'file_size': file_size,
        })

    if prepared_tasks:
        worker_count = min(MAX_CONCURRENT_ANALYSES, len(prepared_tasks))
        logger.info(
            "[batch:%s] Dispatching %d file(s) to %d worker thread(s)",
            batch_id[:8], len(prepared_tasks), worker_count
        )

        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix=f'upload-{batch_id[:8]}') as executor:
            future_to_task = {
                executor.submit(process_single_document, task, user_comments, batch_id): task
                for task in prepared_tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    # Safety net — process_single_document already catches its
                    # own errors, so this should be unreachable in practice.
                    logger.exception("[batch:%s] Unhandled worker error for '%s'", batch_id[:8], task['original_filename'])
                    results.append({
                        'report_id': task['report_id'],
                        'filename': task['original_filename'],
                        'success': False,
                        'error': f'Unexpected processing error: {exc}',
                    })

    # Preserve the order files were submitted in (ThreadPoolExecutor
    # completion order is nondeterministic).
    submission_order = {}
    for i, storage in enumerate(incoming_files):
        name = storage.filename or ''
        submission_order.setdefault(name, i)
    results.sort(key=lambda r: submission_order.get(r.get('filename'), len(submission_order)))

    successful = sum(1 for r in results if r.get('success'))
    failed = len(results) - successful
    batch_time = (datetime.now() - batch_start).total_seconds()

    logger.info(
        "[batch:%s] Completed in %.2fs — %d succeeded, %d failed (of %d total)",
        batch_id[:8], batch_time, successful, failed, len(results)
    )

    if successful and failed:
        status_code = 207  # Multi-Status: partial success
    elif successful:
        status_code = 200
    else:
        status_code = 400

    return jsonify({
        'success': successful > 0,
        'batch_id': batch_id,
        'total_files': len(results),
        'successful': successful,
        'failed': failed,
        'batch_time_seconds': round(batch_time, 2),
        'timestamp': datetime.now().isoformat(),
        'results': results,
    }), status_code


@app.route('/api/logs/<date_str>', methods=['GET'])
def get_daily_logs(date_str):
    """Get daily activity logs."""
    try:
        log_file = os.path.join(app.config['LOGS_FOLDER'], f'activity_{date_str}.json')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            return jsonify(log_data), 200
        else:
            return jsonify({'error': f'No logs found for date {date_str}'}), 404
    except Exception as error:
        logger.error("Error retrieving logs: %s", error)
        return jsonify({'error': 'Failed to retrieve logs'}), 500


@app.route('/api/report/<report_id>', methods=['GET'])
def get_report(report_id):
    """Get a specific analysis report."""
    try:
        output_file = os.path.join(app.config['OUTPUT_FOLDER'], f'{report_id}_analysis.txt')
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            return jsonify({'report_id': report_id, 'content': report_content, 'exists': True}), 200
        else:
            return jsonify({'report_id': report_id, 'error': f'Report {report_id} not found', 'exists': False}), 404
    except Exception as error:
        logger.error("Error retrieving report %s: %s", report_id, error)
        return jsonify({'error': 'Failed to retrieve report'}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics."""
    try:
        stats = {
            'total_reports': 0,
            'total_successful': 0,
            'total_failed': 0,
            'models_usage': {},
            'file_types': {},
            'daily_activity': {},
        }

        logs_dir = app.config['LOGS_FOLDER']
        if os.path.exists(logs_dir):
            for filename in os.listdir(logs_dir):
                if filename.startswith('activity_') and filename.endswith('.json'):
                    date_str = filename.replace('activity_', '').replace('.json', '')
                    log_file = os.path.join(logs_dir, filename)

                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            daily_log = json.load(f)

                        stats['total_reports'] += daily_log.get('total_uploads', 0)
                        stats['total_successful'] += daily_log.get('successful_analyses', 0)
                        stats['total_failed'] += daily_log.get('failed_analyses', 0)

                        for model, count in daily_log.get('models_used', {}).items():
                            stats['models_usage'][model] = stats['models_usage'].get(model, 0) + count

                        for file_type, count in daily_log.get('file_types', {}).items():
                            stats['file_types'][file_type] = stats['file_types'].get(file_type, 0) + count

                        stats['daily_activity'][date_str] = {
                            'uploads': daily_log.get('total_uploads', 0),
                            'successful': daily_log.get('successful_analyses', 0),
                            'failed': daily_log.get('failed_analyses', 0),
                        }

                    except (json.JSONDecodeError, IOError):
                        continue

        return jsonify(stats), 200

    except Exception as error:
        logger.error("Error generating stats: %s", error)
        return jsonify({'error': 'Failed to generate statistics'}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'openai_configured': openai_client is not None,
    })


@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'Upload too large. Check individual file sizes and the total request size.'}), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error("Internal server error: %s", e)
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    logger.info("Starting MediBudAI dev server on %s:%s (debug=%s)", host, port, debug)
    logger.info("Base directory: %s", BASE_DIR)
    logger.info("Upload folder: %s", app.config['UPLOAD_FOLDER'])
    logger.info("Output folder: %s", app.config['OUTPUT_FOLDER'])
    logger.info("Logs folder: %s", app.config['LOGS_FOLDER'])
    logger.info("OpenAI configured: %s", openai_client is not None)

    app.run(debug=debug, host=host, port=port)
