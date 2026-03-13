const API_URL = 'http://localhost:5001/api';
let parsedQuestions = [];

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
});

function checkAuth() {
    const token = localStorage.getItem('token');
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const role = (user.role || '').toLowerCase();

    if (!token || role !== 'admin') {
        alert('Access denied. Admin only.');
        window.location.href = 'login.html';
        return;
    }

    document.getElementById('adminName').textContent = user.fullname || 'Admin';
}

async function handleUpload(e) {
    e.preventDefault();

    const fileInput = document.getElementById('questionFile');
    const file = fileInput.files[0];

    if (!file) {
        showStatus('Please choose a file first.', 'error');
        return;
    }

    try {
        showStatus('Parsing file...', 'info');
        parsedQuestions = await parseFile(file);

        if (!parsedQuestions.length) {
            showStatus('No valid questions found in file.', 'error');
            renderPreview([]);
            return;
        }

        renderPreview(parsedQuestions);
        showStatus(`Parsed ${parsedQuestions.length} questions. Uploading...`, 'info');

        const response = await fetch(`${API_URL}/admin/questions/upload`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ questions: parsedQuestions })
        });

        const data = await response.json();

        if (response.ok) {
            const failedText = data.failed_count > 0 ? `, ${data.failed_count} failed` : '';
            showStatus(`Upload completed: ${data.created_count} created${failedText}.`, 'success');
        } else {
            showStatus(data.message || 'Upload failed.', 'error');
        }
    } catch (error) {
        console.error(error);
        showStatus('Failed to parse/upload file. Check format and try again.', 'error');
    }
}

function parseFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => {
            const text = reader.result;
            const name = file.name.toLowerCase();

            try {
                if (name.endsWith('.json')) {
                    const json = JSON.parse(text);
                    const list = Array.isArray(json) ? json : json.questions || [];
                    resolve(normalizeQuestions(list));
                    return;
                }

                if (name.endsWith('.csv')) {
                    resolve(parseCsv(text));
                    return;
                }

                reject(new Error('Unsupported file type'));
            } catch (err) {
                reject(err);
            }
        };

        reader.onerror = reject;
        reader.readAsText(file);
    });
}

function parseCsv(csvText) {
    const lines = csvText.split(/\r?\n/).filter(line => line.trim());
    if (lines.length < 2) return [];

    const headers = splitCsvLine(lines[0]).map(h => h.trim().toLowerCase());
    const rows = [];

    for (let i = 1; i < lines.length; i++) {
        const cols = splitCsvLine(lines[i]);
        const obj = {};
        headers.forEach((h, idx) => {
            obj[h] = (cols[idx] || '').trim();
        });
        rows.push(obj);
    }

    return normalizeQuestions(rows);
}

function splitCsvLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const ch = line[i];

        if (ch === '"') {
            inQuotes = !inQuotes;
            continue;
        }

        if (ch === ',' && !inQuotes) {
            result.push(current);
            current = '';
        } else {
            current += ch;
        }
    }

    result.push(current);
    return result;
}

function normalizeQuestions(list) {
    const normalized = [];

    list.forEach(item => {
        const q = {
            question_text: (item.question_text || '').trim(),
            option_a: (item.option_a || '').trim(),
            option_b: (item.option_b || '').trim(),
            option_c: (item.option_c || '').trim(),
            option_d: (item.option_d || '').trim(),
            correct_answer: (item.correct_answer || '').trim().toUpperCase(),
            topic: (item.topic || 'General').trim()
        };

        const valid = q.question_text && q.option_a && q.option_b && q.option_c && q.option_d && ['A', 'B', 'C', 'D'].includes(q.correct_answer);

        if (valid) normalized.push(q);
    });

    return normalized;
}

function renderPreview(questions) {
    const empty = document.getElementById('previewEmpty');
    const wrapper = document.getElementById('previewTableWrapper');
    const body = document.getElementById('previewBody');

    if (!questions.length) {
        empty.style.display = 'block';
        wrapper.style.display = 'none';
        body.innerHTML = '';
        return;
    }

    empty.style.display = 'none';
    wrapper.style.display = 'block';

    body.innerHTML = questions.slice(0, 50).map((q, idx) => `
        <tr>
            <td>${idx + 1}</td>
            <td>${escapeHtml(q.question_text)}</td>
            <td>${escapeHtml(q.topic)}</td>
            <td>${q.correct_answer}</td>
        </tr>
    `).join('');
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function showStatus(message, type) {
    const status = document.getElementById('uploadStatus');
    status.className = `status-message ${type}`;
    status.textContent = message;
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('role');
    window.location.href = 'login.html';
}
