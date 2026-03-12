const API_URL = 'http://localhost:5001/api';

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    if (!token) {
        alert('Please login first');
        window.location.href = 'login.html';
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const attemptId = urlParams.get('attempt_id');

    if (!attemptId) {
        alert('Invalid attempt');
        window.location.href = 'profile.html';
        return;
    }

    await loadResult(attemptId);
});

async function loadResult(attemptId) {
    const token = localStorage.getItem('token');

    try {
        const response = await fetch(`${API_URL}/candidate/attempts/${attemptId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            displayResult(data.result);
        } else {
            alert(data.message || 'Failed to load result');
            window.location.href = 'profile.html';
        }
    } catch (error) {
        console.error('Error loading result:', error);
        alert('Failed to load result');
        window.location.href = 'profile.html';
    }
}

function displayResult(result) {
    // Set exam title
    document.getElementById('examTitle').textContent = result.exam_title;

    // Set score
    document.getElementById('scoreValue').textContent = result.score;
    document.getElementById('correctAnswers').textContent = result.correct_answers;
    document.getElementById('totalQuestions').textContent = result.total_questions;

    // Calculate percentage
    const percentage = ((result.correct_answers / result.total_questions) * 100).toFixed(1);
    document.getElementById('percentage').textContent = `${percentage}%`;

    // Format time taken (total_time is in seconds)
    const hours = Math.floor(result.total_time / 3600);
    const minutes = Math.floor((result.total_time % 3600) / 60);
    const seconds = result.total_time % 60;
    document.getElementById('timeTaken').textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

    // Set message based on percentage
    const messageSection = document.getElementById('messageSection');
    const messageElement = document.getElementById('resultMessage');
    
    if (percentage >= 90) {
        messageSection.classList.add('excellent');
        messageElement.innerHTML = `🌟 <strong>Excellent!</strong> Outstanding performance! You've mastered the subject.`;
    } else if (percentage >= 75) {
        messageSection.classList.add('good');
        messageElement.innerHTML = `👍 <strong>Great Job!</strong> You have a good understanding of the material.`;
    } else if (percentage >= 60) {
        messageSection.classList.add('average');
        messageElement.innerHTML = `📚 <strong>Good Effort!</strong> Keep practicing to improve your score.`;
    } else {
        messageSection.classList.add('poor');
        messageElement.innerHTML = `💪 <strong>Keep Trying!</strong> Review the material and practice more.`;
    }

    // Animate score
    animateScore(result.score);
}

function animateScore(targetScore) {
    const scoreElement = document.getElementById('scoreValue');
    let currentScore = 0;
    const increment = Math.ceil(targetScore / 50);
    const duration = 1500; // 1.5 seconds
    const intervalTime = duration / (targetScore / increment);

    const interval = setInterval(() => {
        currentScore += increment;
        if (currentScore >= targetScore) {
            currentScore = targetScore;
            clearInterval(interval);
        }
        scoreElement.textContent = currentScore;
    }, intervalTime);
}

function goToProfile() {
    window.location.href = 'profile.html';
}
