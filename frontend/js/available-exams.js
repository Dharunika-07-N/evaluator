const API_URL = 'http://localhost:5001/api';

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');

    if (!token) {
        alert('Please login first');
        window.location.href = 'login.html';
        return;
    }

    if (role !== 'Candidate') {
        alert('Access denied. Candidates only.');
        window.location.href = 'profile.html';
        return;
    }

    await loadExams();
});

async function loadExams() {
    const token = localStorage.getItem('token');

    try {
        const response = await fetch(`${API_URL}/candidate/exams`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            displayExams(data.exams);
        } else {
            document.getElementById('examsGrid').innerHTML = `
                <div class="loading">
                    <p style="color: #dc3545;">Failed to load exams: ${data.message}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading exams:', error);
        document.getElementById('examsGrid').innerHTML = `
            <div class="loading">
                <p style="color: #dc3545;">Failed to load exams</p>
            </div>
        `;
    }
}

function displayExams(exams) {
    const examsGrid = document.getElementById('examsGrid');
    const noExams = document.getElementById('noExams');

    if (!exams || exams.length === 0) {
        examsGrid.style.display = 'none';
        noExams.style.display = 'block';
        return;
    }

    examsGrid.innerHTML = exams.map(exam => {
        const questionCount = exam.question_count || 0;
        
        return `
            <div class="exam-card">
                <div class="exam-icon">📝</div>
                <div class="exam-title">${exam.title}</div>
                <div class="exam-description">${exam.description || 'No description available'}</div>
                <div class="exam-meta">
                    <div class="meta-item">
                        <span class="meta-icon">⏱️</span>
                        <span>${exam.duration} minutes</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-icon">📋</span>
                        <span>${questionCount} questions</span>
                    </div>
                </div>
                <div class="exam-actions">
                    <button onclick="startExam(${exam.id})" class="btn btn-primary">
                        🚀 Start Exam
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function startExam(examId) {
    if (confirm('Are you sure you want to start this exam? The timer will begin immediately.')) {
        window.location.href = `take-exam.html?exam_id=${examId}`;
    }
}

function goToProfile() {
    window.location.href = 'profile.html';
}
