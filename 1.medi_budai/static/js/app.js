// ---------------------------------------------------------------------------
// MediBudAI frontend — multi-file upload & analysis
//
// Flow: user selects/drops one or more PDFs -> they accumulate in
// `selectedFiles` -> on submit, all files are sent in ONE multipart request
// (field name "files") -> the backend parses + analyzes them concurrently
// and returns a single JSON batch response with a per-file result array ->
// we render one result card per file, including any that failed.
// ---------------------------------------------------------------------------

const MAX_FILE_SIZE = 16 * 1024 * 1024; // 16MB per file, mirrors backend MAX_FILE_SIZE
const MAX_FILES = 10; // mirrors backend MAX_FILES_PER_UPLOAD

let selectedFiles = []; // Array<File>
let lastBatchResult = null; // last successful /api/upload response, for "download all"

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileListEl = document.getElementById('fileList');
const uploadBtn = document.getElementById('uploadBtn');
const uploadBtnText = document.getElementById('uploadBtnText');
const userComments = document.getElementById('userComments');
const charCount = document.getElementById('charCount');
const uploadSection = document.querySelector('.upload-section');
const loadingSection = document.getElementById('loadingSection');
const loadingFileList = document.getElementById('loadingFileList');
const resultsSection = document.getElementById('resultsSection');
const batchSummary = document.getElementById('batchSummary');
const resultsList = document.getElementById('resultsList');
const errorSection = document.getElementById('errorSection');

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    checkServerHealth();
});

function initializeEventListeners() {
    uploadArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => addFiles(e.target.files));
    uploadBtn.addEventListener('click', handleUpload);
    userComments.addEventListener('input', updateCharCounter);

    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleFileDrop);

    document.addEventListener('dragover', e => e.preventDefault());
    document.addEventListener('drop', e => e.preventDefault());
}

function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleFileDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    addFiles(e.dataTransfer.files);
}

// --- File selection state ---------------------------------------------

function addFiles(fileListArg) {
    const incoming = Array.from(fileListArg || []);
    let rejected = [];

    for (const file of incoming) {
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            rejected.push(`${file.name}: not a PDF`);
            continue;
        }
        if (file.size > MAX_FILE_SIZE) {
            rejected.push(`${file.name}: exceeds 16MB`);
            continue;
        }
        // Skip exact duplicates (same name + size) already queued
        const isDuplicate = selectedFiles.some(f => f.name === file.name && f.size === file.size);
        if (isDuplicate) {
            continue;
        }
        selectedFiles.push(file);
    }

    if (selectedFiles.length > MAX_FILES) {
        rejected.push(`Only the first ${MAX_FILES} files are kept — batch limit is ${MAX_FILES}`);
        selectedFiles = selectedFiles.slice(0, MAX_FILES);
    }

    if (rejected.length > 0) {
        showTransientNotice(rejected.join(' · '));
    }

    renderFileList();
    fileInput.value = ''; // allow re-selecting the same file later
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
}

function renderFileList() {
    fileListEl.innerHTML = '';

    selectedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `
            <div class="file-item-info">
                <span class="file-item-icon">📄</span>
                <div>
                    <div class="file-item-name">${escapeHtml(file.name)}</div>
                    <div class="file-item-size">${formatFileSize(file.size)}</div>
                </div>
            </div>
            <button type="button" class="file-item-remove" data-index="${index}" aria-label="Remove file">✕</button>
        `;
        fileListEl.appendChild(item);
    });

    fileListEl.querySelectorAll('.file-item-remove').forEach(btn => {
        btn.addEventListener('click', () => removeFile(parseInt(btn.dataset.index, 10)));
    });

    uploadBtn.disabled = selectedFiles.length === 0;
    uploadBtnText.textContent = selectedFiles.length > 1
        ? `Analyze ${selectedFiles.length} Documents`
        : 'Analyze Document';

    uploadArea.style.borderColor = selectedFiles.length ? '#38b2ac' : '#e2e8f0';
    uploadArea.style.backgroundColor = selectedFiles.length ? '#e6fffa' : '#f7fafc';
}

function showTransientNotice(message) {
    // Lightweight inline notice under the drop zone; doesn't block the flow.
    let notice = document.getElementById('uploadNotice');
    if (!notice) {
        notice = document.createElement('div');
        notice.id = 'uploadNotice';
        notice.className = 'upload-notice';
        uploadArea.insertAdjacentElement('afterend', notice);
    }
    notice.textContent = message;
    notice.style.display = 'block';
    clearTimeout(showTransientNotice._t);
    showTransientNotice._t = setTimeout(() => { notice.style.display = 'none'; }, 6000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function updateCharCounter() {
    const length = userComments.value.length;
    const maxLength = 500;
    charCount.textContent = length;

    const counter = document.querySelector('.char-counter');
    counter.classList.remove('warning', 'error');
    if (length > maxLength * 0.9) {
        counter.classList.add('error');
    } else if (length > maxLength * 0.8) {
        counter.classList.add('warning');
    }
}

// --- Upload + analysis ---------------------------------------------------

async function handleUpload() {
    if (selectedFiles.length === 0) {
        showError('Please select at least one PDF file.');
        return;
    }

    showLoading(selectedFiles);

    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('files', file));

    const comments = userComments.value.trim();
    if (comments) {
        formData.append('comments', comments);
    }

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
        });

        // 200 = all succeeded, 207 = partial success, 400/413/500 = hard failure
        const result = await response.json();

        if (response.ok || response.status === 207) {
            if (result.results && result.results.length > 0) {
                lastBatchResult = result;
                showResults(result);
            } else {
                showError(result.error || 'No files were processed.');
            }
        } else {
            showError(result.error || 'An error occurred while analyzing the documents.');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showError('Network error: please check your connection and try again.');
    }
}

function showLoading(files) {
    hideAllSections();
    loadingSection.style.display = 'block';

    document.getElementById('loadingTitle').textContent =
        files.length > 1 ? `Analyzing ${files.length} Documents...` : 'Analyzing Document...';

    loadingFileList.innerHTML = files.map(f => `
        <div class="loading-file-item">
            <span class="loading-file-spinner"></span>
            <span>${escapeHtml(f.name)}</span>
        </div>
    `).join('');
}

// --- Results rendering -----------------------------------------------------

function showResults(batch) {
    hideAllSections();
    resultsSection.style.display = 'block';

    batchSummary.innerHTML = `
        <div class="meta-item">
            <span class="meta-label">📦 Batch ID</span>
            <span class="report-id">${batch.batch_id}</span>
        </div>
        <div class="meta-item">
            <span class="meta-label">📄 Files</span>
            <span class="filename">${batch.total_files} total</span>
        </div>
        <div class="meta-item">
            <span class="meta-label">✅ Succeeded</span>
            <span class="model-used">${batch.successful}</span>
        </div>
        <div class="meta-item">
            <span class="meta-label">❌ Failed</span>
            <span class="${batch.failed > 0 ? 'comments-included' : 'timestamp'}">${batch.failed}</span>
        </div>
        <div class="meta-item">
            <span class="meta-label">⏱️ Batch Time</span>
            <span class="analysis-time">${batch.batch_time_seconds != null ? batch.batch_time_seconds.toFixed(2) : 'N/A'}s</span>
        </div>
    `;

    resultsList.innerHTML = '';
    batch.results.forEach((result, index) => {
        resultsList.appendChild(buildResultCard(result, index));
    });
}

function buildResultCard(result, index) {
    const card = document.createElement('div');
    card.className = `result-card ${result.success ? 'result-card-success' : 'result-card-error'}`;

    if (!result.success) {
        card.innerHTML = `
            <div class="result-card-header">
                <span class="filename">📄 ${escapeHtml(result.filename || 'Unknown file')}</span>
                <span class="status-badge status-badge-error">Failed</span>
            </div>
            <p class="result-error-message">${escapeHtml(result.error || 'Unknown error')}</p>
        `;
        return card;
    }

    const analysis = result.analysis || {};

    card.innerHTML = `
        <div class="result-card-header">
            <span class="filename">📄 ${escapeHtml(result.filename)}</span>
            <span class="status-badge status-badge-success">Success</span>
        </div>
        <div class="result-meta">
            <div class="meta-item">
                <span class="meta-label">🆔 Report ID</span>
                <span class="report-id">${result.report_id}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">⏱️ Analysis Time</span>
                <span class="analysis-time">${result.analysis_time_seconds != null ? result.analysis_time_seconds.toFixed(2) : 'N/A'}s</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">🤖 Model Used</span>
                <span class="model-used">${result.model_used || 'Unknown'}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">📅 Date</span>
                <span class="timestamp">${formatTimestamp(result.timestamp)}</span>
            </div>
            ${result.user_comments_included ? '<div class="meta-item"><span class="meta-label">💬 Comments</span><span class="comments-included">Included</span></div>' : ''}
        </div>

        <div class="analysis-grid">
            <div class="analysis-item">
                <h3>📋 Document Type</h3>
                <div class="analysis-content">${formatTextContent(analysis.document_type)}</div>
            </div>
            <div class="analysis-item">
                <h3>🔍 Key Findings</h3>
                <div class="analysis-content">${formatTextContent(analysis.key_findings)}</div>
            </div>
            <div class="analysis-item">
                <h3>🩺 Diagnoses</h3>
                <div class="analysis-content">${formatTextContent(analysis.diagnoses)}</div>
            </div>
            <div class="analysis-item">
                <h3>💊 Medications</h3>
                <div class="analysis-content">${formatTextContent(analysis.medications)}</div>
            </div>
            <div class="analysis-item">
                <h3>📅 Follow-ups</h3>
                <div class="analysis-content">${formatTextContent(analysis.follow_ups)}</div>
            </div>
            <div class="analysis-item">
                <h3>⚠️ Risk Assessment</h3>
                <div class="analysis-content">${formatTextContent(analysis.risk_assessment)}</div>
            </div>
        </div>

        <div class="summary-section">
            <h3>📊 Summary</h3>
            <div class="summary-content">${formatTextContent(analysis.summary)}</div>
        </div>

        <div class="recommendations-section">
            <h3>💡 Recommendations</h3>
            <div class="recommendations-content">${formatTextContent(analysis.recommendations)}</div>
        </div>

        <div class="result-card-actions">
            <button class="btn btn-outline" data-index="${index}">Download This Report</button>
        </div>
    `;

    card.querySelector('.result-card-actions button').addEventListener('click', () => downloadSingleResult(index));

    return card;
}

function showError(message) {
    hideAllSections();
    errorSection.style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
}

function hideAllSections() {
    uploadSection.style.display = 'none';
    loadingSection.style.display = 'none';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'none';
}

function resetForm() {
    selectedFiles = [];
    renderFileList();

    userComments.value = '';
    updateCharCounter();

    lastBatchResult = null;

    hideAllSections();
    uploadSection.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
}

function formatTextContent(content) {
    if (!content || content === 'Not specified' || content === 'None found') {
        return `<em style="color: #a0aec0;">${escapeHtml(content || 'Not specified')}</em>`;
    }
    const escaped = escapeHtml(content);
    const withBreaks = escaped.replace(/\n/g, '<br>');
    return withBreaks.replace(/^- (.+)$/gm, '• $1');
}

function buildReportText(result) {
    const analysis = result.analysis || {};
    return `
MEDICAL DOCUMENT ANALYSIS REPORT
Generated by MediBudAI
=====================================

Report ID: ${result.report_id || 'unknown'}
Document: ${result.filename}
Analysis Date: ${formatTimestamp(result.timestamp)}
Model Used: ${result.model_used || 'Unknown'}
Analysis Time: ${result.analysis_time_seconds != null ? result.analysis_time_seconds.toFixed(2) : 'N/A'} seconds
User Comments: ${result.user_comments_included ? 'Included' : 'None'}

=====================================

DOCUMENT TYPE
${analysis.document_type || 'Not specified'}

KEY FINDINGS
${analysis.key_findings || 'Not specified'}

DIAGNOSES
${analysis.diagnoses || 'Not specified'}

MEDICATIONS
${analysis.medications || 'Not specified'}

FOLLOW-UPS
${analysis.follow_ups || 'Not specified'}

RISK ASSESSMENT
${analysis.risk_assessment || 'Not specified'}

SUMMARY
${analysis.summary || 'Not specified'}

RECOMMENDATIONS
${analysis.recommendations || 'Not specified'}

=====================================
DISCLAIMER: This analysis is for informational purposes only and should not replace professional medical advice.
Generated by MediBudAI - AI-powered medical document analysis
`.trim();
}

function triggerDownload(filename, content) {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

function downloadSingleResult(index) {
    if (!lastBatchResult) return;
    const result = lastBatchResult.results[index];
    if (!result || !result.success) return;
    triggerDownload(`medical-analysis-${result.report_id}.txt`, buildReportText(result));
}

function downloadAllResults() {
    if (!lastBatchResult) {
        showError('No analysis results to download.');
        return;
    }

    const successfulResults = lastBatchResult.results.filter(r => r.success);
    if (successfulResults.length === 0) {
        showError('No successful analyses to download.');
        return;
    }

    const combined = successfulResults.map(buildReportText).join('\n\n' + '#'.repeat(60) + '\n\n');
    triggerDownload(`medical-analysis-batch-${lastBatchResult.batch_id}.txt`, combined);
}

// --- Health check ----------------------------------------------------------

async function checkServerHealth() {
    try {
        const response = await fetch('/api/health');
        const result = await response.json();
        console.log('Server health:', result);
        if (result.openai_configured === false) {
            showTransientNotice('Note: the server reports OpenAI is not configured yet — analysis requests will fail until an API key is set.');
        }
    } catch (error) {
        console.error('Server health check failed:', error);
    }
}
