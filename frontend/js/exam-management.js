const API_URL = 'http://localhost:5001/api';
let currentExamId = null;
let selectedQuestions = new Set();
let allQuestions = [];

// Check authentication on page load
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    const user = JSON.parse(localStorage.getItem('user') || '{}');

    if (!token || user.role !== 'Admin') {
        alert('Access denied. Admin only.');
        window.location.href = 'login.html';
        return;
    }

    loadExams();
});

// Load all exams
async function loadExams() {
    const token = localStorage.getItem('token');
    const examsList = document.getElementById('exams-list');
    
    examsList.innerHTML = '<div class="loading">Loading exams...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/exams`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            if (data.exams.length === 0) {
                examsList.innerHTML = `
                    <div class="empty-state">
                        <p style="font-size: 18px;">No exams created yet</p>
                        <p style="margin-top: 10px;">Click "Create New Exam" to get started</p>
                    </div>
                `;
                return;
            }

            examsList.innerHTML = data.exams.map(exam => `
                <div class="exam-card">
                    <div class="exam-card-header">
                        <div>
                            <div class="exam-card-title">${exam.title}</div>
                        </div>
                        <span class="exam-status ${exam.is_active ? 'active' : 'inactive'}">
                            ${exam.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </div>
                    <div class="exam-card-info">
                        <div>📝 <strong>${exam.question_count || 0}</strong> questions</div>
                        <div>⏱️ <strong>${exam.duration}</strong> minutes</div>
                        <div>🎯 <strong>${exam.total_marks}</strong> marks</div>
                        <div>👤 ${exam.creator_name || 'Unknown'}</div>
                    </div>
                    ${exam.description ? `<p style="color: #666; font-size: 14px; margin-bottom: 15px;">${exam.description}</p>` : ''}
                    <div class="exam-card-actions">
                        <button class="btn-primary btn-small" onclick="viewExam(${exam.id})">View Details</button>
                        <button class="btn-success btn-small" onclick="addQuestionsToExam(${exam.id})">Add Questions</button>
                        <button class="btn-secondary btn-small" onclick="toggleExamStatus(${exam.id}, ${exam.is_active})">
                            ${exam.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button class="btn-danger btn-small" onclick="deleteExam(${exam.id})">Delete</button>
                    </div>
                </div>
            `).join('');
        } else {
            examsList.innerHTML = `<div class="empty-state">${data.message}</div>`;
        }
    } catch (error) {
        console.error('Error loading exams:', error);
        examsList.innerHTML = '<div class="empty-state">Failed to load exams</div>';
    }
}

// Show create exam modal
function showCreateExamModal() {
    document.getElementById('createExamModal').style.display = 'block';
    document.getElementById('createExamForm').reset();
}

// Close create exam modal
function closeCreateExamModal() {
    document.getElementById('createExamModal').style.display = 'none';
}

// Handle create exam form submission
document.getElementById('createExamForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const token = localStorage.getItem('token');
    const title = document.getElementById('examTitle').value;
    const description = document.getElementById('examDescription').value;
    const duration = parseInt(document.getElementById('examDuration').value);
    const total_marks = parseInt(document.getElementById('examMarks').value);

    try {
        const response = await fetch(`${API_URL}/admin/exams`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                title,
                description,
                duration,
                total_marks
            })
        });

        const data = await response.json();

        if (response.ok) {
            alert('Exam created successfully!');
            closeCreateExamModal();
            loadExams();
        } else {
            alert(data.message || 'Failed to create exam');
        }
    } catch (error) {
        console.error('Error creating exam:', error);
        alert('Failed to create exam');
    }
});

// View exam details
async function viewExam(examId) {
    const token = localStorage.getItem('token');
    
    try {
        const response = await fetch(`${API_URL}/admin/exams/${examId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            const exam = data.exam;
            document.getElementById('viewExamTitle').textContent = exam.title;
            
            let detailsHTML = `
                <div class="exam-info">
                    <div class="exam-info-row">
                        <div class="exam-info-label">Description:</div>
                        <div class="exam-info-value">${exam.description || 'N/A'}</div>
                    </div>
                    <div class="exam-info-row">
                        <div class="exam-info-label">Duration:</div>
                        <div class="exam-info-value">${exam.duration} minutes</div>
                    </div>
                    <div class="exam-info-row">
                        <div class="exam-info-label">Total Marks:</div>
                        <div class="exam-info-value">${exam.total_marks}</div>
                    </div>
                    <div class="exam-info-row">
                        <div class="exam-info-label">Total Questions:</div>
                        <div class="exam-info-value">${exam.question_count}</div>
                    </div>
                    <div class="exam-info-row">
                        <div class="exam-info-label">Status:</div>
                        <div class="exam-info-value">${exam.is_active ? 'Active' : 'Inactive'}</div>
                    </div>
                    <div class="exam-info-row">
                        <div class="exam-info-label">Creator:</div>
                        <div class="exam-info-value">${exam.creator_name}</div>
                    </div>
                </div>
                
                <div class="exam-questions-list">
                    <h3>Questions (${exam.questions.length})</h3>
            `;

            if (exam.questions.length === 0) {
                detailsHTML += '<p style="color: #999; text-align: center; padding: 20px;">No questions added yet</p>';
            } else {
                exam.questions.forEach((q, index) => {
                    detailsHTML += `
                        <div class="exam-question-item">
                            <div class="exam-question-header">
                                <span class="question-number">Question ${index + 1}</span>
                                <div>
                                    <span style="color: #666; font-size: 12px; margin-right: 10px;">Marks: ${q.marks}</span>
                                    <button class="btn-danger btn-small" onclick="removeQuestionFromExam(${examId}, ${q.id})">Remove</button>
                                </div>
                            </div>
                            <div class="exam-question-text">${q.question_text}</div>
                            <div class="exam-question-options">
                                <div>A) ${q.option_a}</div>
                                <div>B) ${q.option_b}</div>
                                <div>C) ${q.option_c}</div>
                                <div>D) ${q.option_d}</div>
                            </div>
                            <div style="margin-top: 10px; font-size: 12px; color: #28a745; font-weight: 600;">
                                Correct Answer: ${q.correct_answer}
                            </div>
                            ${q.topic ? `<div style="margin-top: 5px; font-size: 12px; color: #666;">Topic: ${q.topic}</div>` : ''}
                        </div>
                    `;
                });
            }

            detailsHTML += '</div>';
            
            document.getElementById('examDetails').innerHTML = detailsHTML;
            document.getElementById('viewExamModal').style.display = 'block';
        } else {
            alert(data.message || 'Failed to load exam details');
        }
    } catch (error) {
        console.error('Error loading exam:', error);
        alert('Failed to load exam details');
    }
}

// Close view exam modal
function closeViewExamModal() {
    document.getElementById('viewExamModal').style.display = 'none';
}

// Add questions to exam
async function addQuestionsToExam(examId) {
    currentExamId = examId;
    selectedQuestions.clear();
    await loadAvailableQuestions();
    document.getElementById('addQuestionsModal').style.display = 'block';
}

// Load available questions
async function loadAvailableQuestions() {
    const token = localStorage.getItem('token');
    const questionsContainer = document.getElementById('availableQuestions');
    
    questionsContainer.innerHTML = '<div class="loading">Loading questions...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/questions`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            allQuestions = data.questions || [];
            
            if (allQuestions.length === 0) {
                questionsContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: #999;">No questions available. Create questions first.</div>';
                return;
            }

            renderQuestions(allQuestions);
        } else {
            questionsContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: #999;">Failed to load questions</div>';
        }
    } catch (error) {
        console.error('Error loading questions:', error);
        questionsContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: #999;">Failed to load questions</div>';
    }
}

// Render questions
function renderQuestions(questions) {
    const questionsContainer = document.getElementById('availableQuestions');
    
    questionsContainer.innerHTML = questions.map(q => `
        <div class="question-item ${selectedQuestions.has(q.id) ? 'selected' : ''}" onclick="toggleQuestionSelection(${q.id})">
            <input type="checkbox" ${selectedQuestions.has(q.id) ? 'checked' : ''} onclick="event.stopPropagation(); toggleQuestionSelection(${q.id})">
            <div class="question-content">
                <div class="question-text">${q.question_text}</div>
                <div class="question-meta">
                    ${q.topic ? `Topic: ${q.topic} | ` : ''}Options: A) ${q.option_a.substring(0, 30)}... 
                </div>
            </div>
        </div>
    `).join('');
}

// Toggle question selection
function toggleQuestionSelection(questionId) {
    if (selectedQuestions.has(questionId)) {
        selectedQuestions.delete(questionId);
    } else {
        selectedQuestions.add(questionId);
    }
    renderQuestions(allQuestions);
}

// Search questions
document.getElementById('questionSearch').addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    const filtered = allQuestions.filter(q => 
        q.question_text.toLowerCase().includes(searchTerm) ||
        (q.topic && q.topic.toLowerCase().includes(searchTerm))
    );
    renderQuestions(filtered);
});

// Save selected questions
async function saveSelectedQuestions() {
    if (selectedQuestions.size === 0) {
        alert('Please select at least one question');
        return;
    }

    const token = localStorage.getItem('token');
    const questionIds = Array.from(selectedQuestions);

    try {
        const response = await fetch(`${API_URL}/admin/exams/${currentExamId}/questions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                question_ids: questionIds,
                marks: 1
            })
        });

        const data = await response.json();

        if (response.ok) {
            alert(data.message);
            closeAddQuestionsModal();
            loadExams();
        } else {
            alert(data.message || 'Failed to add questions');
        }
    } catch (error) {
        console.error('Error adding questions:', error);
        alert('Failed to add questions');
    }
}

// Close add questions modal
function closeAddQuestionsModal() {
    document.getElementById('addQuestionsModal').style.display = 'none';
}

// Remove question from exam
async function removeQuestionFromExam(examId, questionId) {
    if (!confirm('Remove this question from the exam?')) {
        return;
    }

    const token = localStorage.getItem('token');

    try {
        const response = await fetch(`${API_URL}/admin/exams/${examId}/questions`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ question_id: questionId })
        });

        const data = await response.json();

        if (response.ok) {
            alert('Question removed successfully');
            viewExam(examId); // Refresh the exam view
            loadExams(); // Refresh the exam list
        } else {
            alert(data.message || 'Failed to remove question');
        }
    } catch (error) {
        console.error('Error removing question:', error);
        alert('Failed to remove question');
    }
}

// Toggle exam active status
async function toggleExamStatus(examId, currentStatus) {
    const token = localStorage.getItem('token');
    const newStatus = currentStatus ? 0 : 1;

    try {
        const response = await fetch(`${API_URL}/admin/exams/${examId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ is_active: newStatus })
        });

        const data = await response.json();

        if (response.ok) {
            alert(`Exam ${newStatus ? 'activated' : 'deactivated'} successfully`);
            loadExams();
        } else {
            alert(data.message || 'Failed to update exam status');
        }
    } catch (error) {
        console.error('Error updating exam:', error);
        alert('Failed to update exam status');
    }
}

// Delete exam
async function deleteExam(examId) {
    if (!confirm('Are you sure you want to delete this exam? This action cannot be undone.')) {
        return;
    }

    const token = localStorage.getItem('token');

    try {
        const response = await fetch(`${API_URL}/admin/exams/${examId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            alert('Exam deleted successfully');
            loadExams();
        } else {
            alert(data.message || 'Failed to delete exam');
        }
    } catch (error) {
        console.error('Error deleting exam:', error);
        alert('Failed to delete exam');
    }
}

// Close modals when clicking outside
window.onclick = function(event) {
    const createModal = document.getElementById('createExamModal');
    const addQuestionsModal = document.getElementById('addQuestionsModal');
    const viewModal = document.getElementById('viewExamModal');
    
    if (event.target === createModal) {
        closeCreateExamModal();
    }
    if (event.target === addQuestionsModal) {
        closeAddQuestionsModal();
    }
    if (event.target === viewModal) {
        closeViewExamModal();
    }
}
