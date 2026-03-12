const API_URL = 'http://localhost:5001/api';

// Check authentication on page load
document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    loadQuestions();
    setupEventListeners();
});

function checkAuth() {
    const token = localStorage.getItem('token');
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    
    if (!token || !user.role) {
        window.location.href = 'login.html';
        return;
    }
    
    // Check if user is admin
    if (user.role !== 'Admin') {
        alert('Access denied. This page is for administrators only.');
        window.location.href = 'profile.html';
        return;
    }
    
    document.getElementById('adminName').textContent = user.fullname;
}

function setupEventListeners() {
    // Generate questions form
    document.getElementById('generateForm').addEventListener('submit', handleGenerateQuestions);
    
    // Manual form toggle
    document.getElementById('toggleManualForm').addEventListener('click', function() {
        const form = document.getElementById('manualForm');
        if (form.style.display === 'none') {
            form.style.display = 'block';
            this.textContent = 'Hide Manual Entry Form';
        } else {
            form.style.display = 'none';
            this.textContent = 'Show Manual Entry Form';
        }
    });
    
    // Manual form submit
    document.getElementById('manualForm').addEventListener('submit', handleManualQuestion);
    
    // Cancel manual form
    document.getElementById('cancelManual').addEventListener('click', function() {
        document.getElementById('manualForm').reset();
        document.getElementById('manualForm').style.display = 'none';
        document.getElementById('toggleManualForm').textContent = 'Show Manual Entry Form';
    });
    
    // Search filter
    document.getElementById('searchTopic').addEventListener('input', filterQuestions);
}

async function handleGenerateQuestions(e) {
    e.preventDefault();
    
    const statusDiv = document.getElementById('generateStatus');
    statusDiv.className = 'status-message info';
    statusDiv.textContent = 'Generating questions... This may take a moment.';
    
    const formData = {
        url: document.getElementById('url').value,
        topic: document.getElementById('topic').value,
        num_questions: document.getElementById('numQuestions').value
    };
    
    try {
        const response = await fetch(`${API_URL}/admin/generate-questions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.className = 'status-message success';
            statusDiv.textContent = data.message;
            document.getElementById('generateForm').reset();
            loadQuestions(); // Reload questions list
        } else {
            statusDiv.className = 'status-message error';
            statusDiv.textContent = data.message || 'Failed to generate questions';
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = 'Error generating questions. Please check the URL and try again.';
        console.error('Error:', error);
    }
}

async function handleManualQuestion(e) {
    e.preventDefault();
    
    const statusDiv = document.getElementById('manualStatus');
    statusDiv.className = 'status-message info';
    statusDiv.textContent = 'Adding question...';
    
    const formData = {
        question_text: document.getElementById('manualQuestion').value,
        topic: document.getElementById('manualTopic').value,
        option_a: document.getElementById('optionA').value,
        option_b: document.getElementById('optionB').value,
        option_c: document.getElementById('optionC').value,
        option_d: document.getElementById('optionD').value,
        correct_answer: document.getElementById('correctAnswer').value
    };
    
    try {
        const response = await fetch(`${API_URL}/admin/questions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.className = 'status-message success';
            statusDiv.textContent = data.message;
            document.getElementById('manualForm').reset();
            loadQuestions(); // Reload questions list
            
            // Hide form after success
            setTimeout(() => {
                document.getElementById('manualForm').style.display = 'none';
                document.getElementById('toggleManualForm').textContent = 'Show Manual Entry Form';
                statusDiv.style.display = 'none';
            }, 2000);
        } else {
            statusDiv.className = 'status-message error';
            statusDiv.textContent = data.message || 'Failed to add question';
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = 'Error adding question. Please try again.';
        console.error('Error:', error);
    }
}

async function loadQuestions() {
    const questionsList = document.getElementById('questionsList');
    questionsList.innerHTML = '<p class="loading">Loading questions...</p>';
    
    try {
        const response = await fetch(`${API_URL}/admin/questions`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayQuestions(data.questions);
        } else {
            questionsList.innerHTML = '<p class="error">Failed to load questions</p>';
        }
    } catch (error) {
        questionsList.innerHTML = '<p class="error">Error loading questions</p>';
        console.error('Error:', error);
    }
}

function displayQuestions(questions) {
    const questionsList = document.getElementById('questionsList');
    
    if (!questions || questions.length === 0) {
        questionsList.innerHTML = '<p class="no-questions">No questions found. Generate or add questions to get started!</p>';
        return;
    }
    
    questionsList.innerHTML = questions.map(q => `
        <div class="question-card" data-id="${q.id}" data-topic="${q.topic}">
            <div class="question-header">
                <span class="question-topic">${q.topic || 'General'}</span>
                <div class="question-actions">
                    <button class="btn-edit" onclick="editQuestion(${q.id})">Edit</button>
                    <button class="btn-danger" onclick="deleteQuestion(${q.id})">Delete</button>
                </div>
            </div>
            <div class="question-text">${q.question_text}</div>
            <div class="options-list">
                <div class="option ${q.correct_answer === 'A' ? 'correct' : ''}">
                    <span class="option-label">A.</span> ${q.option_a}
                </div>
                <div class="option ${q.correct_answer === 'B' ? 'correct' : ''}">
                    <span class="option-label">B.</span> ${q.option_b}
                </div>
                <div class="option ${q.correct_answer === 'C' ? 'correct' : ''}">
                    <span class="option-label">C.</span> ${q.option_c}
                </div>
                <div class="option ${q.correct_answer === 'D' ? 'correct' : ''}">
                    <span class="option-label">D.</span> ${q.option_d}
                </div>
            </div>
            <div class="question-meta">
                Correct Answer: ${q.correct_answer} | Created: ${new Date(q.created_at).toLocaleDateString()}
                ${q.source_url ? `| Source: <a href="${q.source_url}" target="_blank">View</a>` : ''}
            </div>
        </div>
    `).join('');
}

function filterQuestions() {
    const searchTerm = document.getElementById('searchTopic').value.toLowerCase();
    const questionCards = document.querySelectorAll('.question-card');
    
    questionCards.forEach(card => {
        const topic = card.dataset.topic.toLowerCase();
        if (topic.includes(searchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

function editQuestion(questionId) {
    const card = document.querySelector(`.question-card[data-id="${questionId}"]`);
    
    // Get current values
    const questionText = card.querySelector('.question-text').textContent;
    const topic = card.querySelector('.question-topic').textContent;
    const options = card.querySelectorAll('.option');
    
    // Create edit form (replace card content)
    card.innerHTML = `
        <form class="edit-form" onsubmit="saveEdit(event, ${questionId})">
            <div class="form-group">
                <label>Question:</label>
                <textarea name="question_text" rows="3" required>${questionText}</textarea>
            </div>
            <div class="form-group">
                <label>Topic:</label>
                <input type="text" name="topic" value="${topic}" required>
            </div>
            <div class="options-grid">
                <div class="form-group">
                    <label>Option A:</label>
                    <input type="text" name="option_a" value="${options[0].textContent.replace('A.', '').trim()}" required>
                </div>
                <div class="form-group">
                    <label>Option B:</label>
                    <input type="text" name="option_b" value="${options[1].textContent.replace('B.', '').trim()}" required>
                </div>
                <div class="form-group">
                    <label>Option C:</label>
                    <input type="text" name="option_c" value="${options[2].textContent.replace('C.', '').trim()}" required>
                </div>
                <div class="form-group">
                    <label>Option D:</label>
                    <input type="text" name="option_d" value="${options[3].textContent.replace('D.', '').trim()}" required>
                </div>
            </div>
            <div class="form-group">
                <label>Correct Answer:</label>
                <select name="correct_answer" required>
                    <option value="A">A</option>
                    <option value="B">B</option>
                    <option value="C">C</option>
                    <option value="D">D</option>
                </select>
            </div>
            <button type="submit" class="btn-primary">Save</button>
            <button type="button" class="btn-secondary" onclick="loadQuestions()">Cancel</button>
        </form>
    `;
}

async function saveEdit(event, questionId) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);
    
    try {
        const response = await fetch(`${API_URL}/admin/questions/${questionId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            loadQuestions(); // Reload questions
        } else {
            alert('Failed to update question');
        }
    } catch (error) {
        alert('Error updating question');
        console.error('Error:', error);
    }
}

async function deleteQuestion(questionId) {
    if (!confirm('Are you sure you want to delete this question?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/admin/questions/${questionId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (response.ok) {
            loadQuestions(); // Reload questions
        } else {
            alert('Failed to delete question');
        }
    } catch (error) {
        alert('Error deleting question');
        console.error('Error:', error);
    }
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'login.html';
}
