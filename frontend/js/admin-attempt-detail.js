const API_URL = 'http://localhost:5001/api';

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');

    if (!token) {
        alert('Please login first');
        window.location.href = 'login.html';
        return;
    }

    if (role !== 'Admin') {
        alert('Access denied. Admin only.');
        window.location.href = 'profile.html';
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const attemptId = urlParams.get('attempt_id');

    if (!attemptId) {
        alert('Invalid attempt');
        window.location.href = 'admin-results.html';
        return;
    }

    await loadAttemptDetails(attemptId);
});

async function loadAttemptDetails(attemptId) {
    const token = localStorage.getItem('token');

    try {
        const response = await fetch(`${API_URL}/admin/attempts/${attemptId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            displayAttemptDetails(data.attempt);
        } else {
            document.getElementById('answersContainer').innerHTML = `
                <div class="loading">
                    <p style="color: #dc3545;">Failed to load attempt details: ${data.message}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading attempt details:', error);
        document.getElementById('answersContainer').innerHTML = `
            <div class="loading">
                <p style="color: #dc3545;">Failed to load attempt details</p>
            </div>
        `;
    }
}

function displayAttemptDetails(attempt) {
    // Set candidate info
    document.getElementById('candidateName').textContent = attempt.candidate_name;
    document.getElementById('candidateEmail').textContent = attempt.candidate_email;

    // Set exam info
    document.getElementById('examTitle').textContent = attempt.exam_title;
    const submittedDate = new Date(attempt.submitted_at);
    document.getElementById('submittedAt').textContent = submittedDate.toLocaleString();

    // Parse score
    const [correct, total] = attempt.score.split('/').map(Number);
    const percentage = ((correct / total) * 100).toFixed(1);

    // Set summary
    document.getElementById('scoreValue').textContent = attempt.score;
    document.getElementById('percentage').textContent = `${percentage}%`;

    // Format total time
    const hours = Math.floor(attempt.total_time / 3600);
    const minutes = Math.floor((attempt.total_time % 3600) / 60);
    const seconds = attempt.total_time % 60;
    document.getElementById('totalTime').textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

    // Calculate average time per question
    const avgTimeSeconds = Math.floor(attempt.total_time / total);
    const avgMinutes = Math.floor(avgTimeSeconds / 60);
    const avgSeconds = avgTimeSeconds % 60;
    document.getElementById('avgTimePerQ').textContent = 
        `${String(avgMinutes).padStart(2, '0')}:${String(avgSeconds).padStart(2, '0')}`;

    // Set tab switches count
    const tabSwitches = attempt.tab_switches || 0;
    document.getElementById('tabSwitches').textContent = tabSwitches;
    
    // Color code tab switch card
    const tabSwitchCard = document.getElementById('tabSwitchCard');
    if (tabSwitches >= 3) {
        tabSwitchCard.style.borderLeft = '4px solid #dc3545';
        tabSwitchCard.style.backgroundColor = '#fff5f5';
    } else if (tabSwitches > 0) {
        tabSwitchCard.style.borderLeft = '4px solid #ffc107';
        tabSwitchCard.style.backgroundColor = '#fffef5';
    } else {
        tabSwitchCard.style.borderLeft = '4px solid #28a745';
        tabSwitchCard.style.backgroundColor = '#f0fff4';
    }

    // Set exam status
    const status = attempt.status || 'completed';
    document.getElementById('examStatus').textContent = status === 'violated' ? 'Violated' : 'Completed';
    
    // Show violation alert if violated
    if (status === 'violated' && attempt.violation_reason) {
        document.getElementById('violationAlert').style.display = 'flex';
        document.getElementById('violationReason').textContent = attempt.violation_reason;
        
        const statusCard = document.getElementById('statusCard');
        statusCard.style.borderLeft = '4px solid #dc3545';
        statusCard.style.backgroundColor = '#fff5f5';
        
        const statusIcon = statusCard.querySelector('.summary-icon');
        statusIcon.textContent = '⚠️';
    }

    // Display answers
    displayAnswers(attempt.answers);
}

function displayAnswers(answers) {
    const container = document.getElementById('answersContainer');

    if (!answers || answers.length === 0) {
        container.innerHTML = '<p>No answers found</p>';
        return;
    }

    container.innerHTML = answers.map((answer, index) => {
        const isCorrect = answer.is_correct;
        const isSkipped = !answer.selected_answer;
        
        let cardClass = 'answer-card';
        let badgeHTML = '';
        
        if (isSkipped) {
            cardClass += ' skipped';
            badgeHTML = '<span class="badge badge-skipped">⏭️ Skipped</span>';
        } else if (isCorrect) {
            cardClass += ' correct';
            badgeHTML = '<span class="badge badge-correct">✅ Correct</span>';
        } else {
            cardClass += ' incorrect';
            badgeHTML = '<span class="badge badge-incorrect">❌ Incorrect</span>';
        }

        // Format time taken
        const timeMinutes = Math.floor(answer.time_taken / 60);
        const timeSeconds = answer.time_taken % 60;
        const timeFormatted = `${String(timeMinutes).padStart(2, '0')}:${String(timeSeconds).padStart(2, '0')}`;

        // Generate options HTML
        const optionsHTML = answer.options.map(option => {
            let optionClass = 'option';
            let optionLabel = '';

            const isCorrectOption = option.key === answer.correct_answer;
            const isCandidateAnswer = option.key === answer.selected_answer;

            if (isCorrectOption) {
                optionClass += ' correct-answer';
                optionLabel = '<span class="option-label">✅ Correct Answer</span>';
            }

            if (isCandidateAnswer && !isCorrect) {
                optionClass += ' candidate-wrong';
                optionLabel = '<span class="option-label">❌ Your Answer</span>';
            } else if (isCandidateAnswer && isCorrect) {
                optionLabel = '<span class="option-label">✅ Your Answer</span>';
            }

            return `
                <div class="${optionClass}">
                    <span class="option-key">${option.key}</span>
                    <span class="option-text">${option.text}</span>
                    ${optionLabel}
                </div>
            `;
        }).join('');

        return `
            <div class="${cardClass}">
                <div class="answer-header">
                    <div class="question-number">Question ${index + 1}</div>
                    <div class="answer-badges">
                        ${badgeHTML}
                        <span class="badge badge-time">⏱️ ${timeFormatted}</span>
                    </div>
                </div>
                <div class="question-text">${answer.question_text}</div>
                <div class="options-container">
                    ${optionsHTML}
                </div>
            </div>
        `;
    }).join('');
}

function goBack() {
    window.location.href = 'admin-results.html';
}
