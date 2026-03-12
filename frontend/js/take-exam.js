const API_URL = 'http://localhost:5001/api';
let examData = null;
let currentQuestionIndex = 0;
let answers = {}; // {question_id: {selected_answer, time_taken}}
let attemptId = null;
let examStartTime = null;
let questionStartTime = null;
let examTimerInterval = null;
let questionTimerInterval = null;
let remainingTime = 0; // in seconds
let tabSwitchCount = 0;
const MAX_TAB_SWITCHES = 3;
let isViolated = false;
let cameraStream = null;

// Check authentication and get exam ID
document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    if (!token) {
        alert('Please login first');
        window.location.href = 'login.html';
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const examId = urlParams.get('exam_id');

    if (!examId) {
        alert('No exam selected');
        window.location.href = 'profile.html';
        return;
    }

    await loadExam(examId);
});

// Load exam data
async function loadExam(examId) {
    const token = localStorage.getItem('token');

    try {
        // Start exam attempt
        const startResponse = await fetch(`${API_URL}/candidate/exams/${examId}/start`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const startData = await startResponse.json();

        if (!startResponse.ok) {
            alert(startData.message);
            window.location.href = 'profile.html';
            return;
        }

        attemptId = startData.attempt_id;

        // Get exam with shuffled questions
        const examResponse = await fetch(`${API_URL}/candidate/exams/${examId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const examDataResponse = await examResponse.json();

        if (examResponse.ok) {
            examData = examDataResponse.exam;
            initializeExam();
        } else {
            alert(examDataResponse.message);
            window.location.href = 'profile.html';
        }
    } catch (error) {
        console.error('Error loading exam:', error);
        alert('Failed to load exam');
        window.location.href = 'profile.html';
    }
}

// Initialize exam
function initializeExam() {
    // Set exam info
    document.getElementById('examTitle').textContent = examData.title;
    document.getElementById('examDuration').textContent = `⏱️ ${examData.duration} minutes`;
    document.getElementById('totalQuestions').textContent = `📝 ${examData.questions.length} questions`;
    document.getElementById('totalQuestionsCount').textContent = examData.questions.length;

    // Initialize answers object
    examData.questions.forEach(q => {
        answers[q.id] = {
            selected_answer: null,
            time_taken: 0
        };
    });

    // Start camera monitoring
    startCameraMonitoring();

    // Setup tab switch detection
    setupTabSwitchDetection();

    // Start timers
    examStartTime = Date.now();
    remainingTime = examData.duration * 60; // Convert minutes to seconds
    startExamTimer();
    startQuestionTimer();

    // Display first question
    displayQuestion(0);

    // Create question navigator
    createQuestionNavigator();

    // Warn before leaving page
    window.addEventListener('beforeunload', (e) => {
        if (!isViolated) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}

// Start exam timer
function startExamTimer() {
    updateExamTimerDisplay();
    
    examTimerInterval = setInterval(() => {
        remainingTime--;
        updateExamTimerDisplay();

        // Warning when 5 minutes left
        if (remainingTime === 300) {
            document.querySelector('.timer').classList.add('warning');
            alert('Warning: 5 minutes remaining!');
        }

        // Auto-submit when time expires
        if (remainingTime <= 0) {
            clearInterval(examTimerInterval);
            alert('Time is up! Submitting exam...');
            submitExam();
        }
    }, 1000);
}

// Update exam timer display
function updateExamTimerDisplay() {
    const minutes = Math.floor(remainingTime / 60);
    const seconds = remainingTime % 60;
    document.getElementById('timerValue').textContent = 
        `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// Start question timer
function startQuestionTimer() {
    questionStartTime = Date.now();
    
    const updateQuestionTimer = () => {
        const elapsed = Math.floor((Date.now() - questionStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        document.getElementById('questionTimer').textContent = 
            `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    };

    updateQuestionTimer();
    questionTimerInterval = setInterval(updateQuestionTimer, 1000);
}

// Stop question timer and save time
function stopQuestionTimer() {
    if (questionTimerInterval) {
        clearInterval(questionTimerInterval);
        const elapsed = Math.floor((Date.now() - questionStartTime) / 1000);
        const currentQuestion = examData.questions[currentQuestionIndex];
        answers[currentQuestion.id].time_taken = elapsed;
    }
}

// Display question
function displayQuestion(index) {
    const question = examData.questions[index];
    const questionSection = document.getElementById('questionSection');

    // Update progress
    document.getElementById('currentQuestion').textContent = index + 1;
    const progress = ((index + 1) / examData.questions.length) * 100;
    document.getElementById('progressFill').style.width = `${progress}%`;

    // Build question HTML
    const selectedAnswer = answers[question.id].selected_answer;
    
    questionSection.innerHTML = `
        <div class="question-content">
            <div class="question-number">Question ${index + 1} of ${examData.questions.length}</div>
            <div class="question-text">${question.question_text}</div>
            <div class="options-container">
                ${question.options.map(option => `
                    <div class="option ${selectedAnswer === option.key ? 'selected' : ''}" 
                         onclick="selectOption('${option.key}', ${question.id})">
                        <input type="radio" 
                               name="question_${question.id}" 
                               value="${option.key}" 
                               ${selectedAnswer === option.key ? 'checked' : ''}
                               onchange="selectOption('${option.key}', ${question.id})">
                        <label class="option-label">
                            <span class="option-key">${option.key}</span>
                            <span>${option.text}</span>
                        </label>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    // Update navigation buttons
    updateNavigationButtons();
    updateQuestionNavigator();
}

// Select option
function selectOption(optionKey, questionId) {
    answers[questionId].selected_answer = optionKey;
    
    // Update UI
    const options = document.querySelectorAll('.option');
    options.forEach(option => {
        option.classList.remove('selected');
        const radio = option.querySelector('input[type="radio"]');
        if (radio && radio.value === optionKey) {
            option.classList.add('selected');
            radio.checked = true;
        }
    });

    updateNavigationButtons();
    updateQuestionNavigator();
}

// Update navigation buttons
function updateNavigationButtons() {
    const previousBtn = document.getElementById('previousBtn');
    const skipBtn = document.getElementById('skipBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');

    // Previous button
    previousBtn.disabled = currentQuestionIndex === 0;

    // Show/hide skip/next/submit buttons
    const currentAnswer = answers[examData.questions[currentQuestionIndex].id].selected_answer;
    const isLastQuestion = currentQuestionIndex === examData.questions.length - 1;

    if (currentAnswer) {
        skipBtn.style.display = 'none';
        if (isLastQuestion) {
            nextBtn.style.display = 'none';
            submitBtn.style.display = 'flex';
        } else {
            nextBtn.style.display = 'flex';
            submitBtn.style.display = 'none';
        }
    } else {
        skipBtn.style.display = 'flex';
        nextBtn.style.display = 'none';
        if (isLastQuestion) {
            submitBtn.style.display = 'flex';
        } else {
            submitBtn.style.display = 'none';
        }
    }
}

// Previous question
function previousQuestion() {
    if (currentQuestionIndex > 0) {
        stopQuestionTimer();
        currentQuestionIndex--;
        displayQuestion(currentQuestionIndex);
        startQuestionTimer();
    }
}

// Skip question
function skipQuestion() {
    if (currentQuestionIndex < examData.questions.length - 1) {
        stopQuestionTimer();
        currentQuestionIndex++;
        displayQuestion(currentQuestionIndex);
        startQuestionTimer();
    }
}

// Next question
function nextQuestion() {
    if (currentQuestionIndex < examData.questions.length - 1) {
        stopQuestionTimer();
        currentQuestionIndex++;
        displayQuestion(currentQuestionIndex);
        startQuestionTimer();
    }
}

// Create question navigator
function createQuestionNavigator() {
    const questionGrid = document.getElementById('questionGrid');
    
    questionGrid.innerHTML = examData.questions.map((q, index) => `
        <div class="question-nav-item" 
             data-index="${index}"
             onclick="jumpToQuestion(${index})">
            ${index + 1}
        </div>
    `).join('');
}

// Update question navigator
function updateQuestionNavigator() {
    const navItems = document.querySelectorAll('.question-nav-item');
    
    navItems.forEach((item, index) => {
        const question = examData.questions[index];
        const answer = answers[question.id];
        
        // Remove all status classes
        item.classList.remove('current', 'answered', 'skipped');
        
        // Add appropriate class
        if (index === currentQuestionIndex) {
            item.classList.add('current');
        } else if (answer.selected_answer) {
            item.classList.add('answered');
        } else if (answer.time_taken > 0) {
            item.classList.add('skipped');
        }
    });
}

// Jump to question
function jumpToQuestion(index) {
    stopQuestionTimer();
    currentQuestionIndex = index;
    displayQuestion(currentQuestionIndex);
    startQuestionTimer();
}

// Submit exam
function submitExam() {
    stopQuestionTimer();
    
    // Count answered questions
    const answeredCount = Object.values(answers).filter(a => a.selected_answer).length;
    const unansweredCount = examData.questions.length - answeredCount;
    
    let message = `You have answered ${answeredCount} out of ${examData.questions.length} questions.`;
    if (unansweredCount > 0) {
        message += `\n\n${unansweredCount} questions are unanswered. They will be marked as incorrect.`;
    }
    message += '\n\nAre you sure you want to submit?';
    
    document.getElementById('submitMessage').textContent = message;
    document.getElementById('submitModal').style.display = 'block';
}

// Close submit modal
function closeSubmitModal() {
    document.getElementById('submitModal').style.display = 'none';
    startQuestionTimer(); // Resume timer
}

// Confirm submit
async function confirmSubmit() {
    document.getElementById('submitModal').style.display = 'none';
    
    // Stop timers
    clearInterval(examTimerInterval);
    clearInterval(questionTimerInterval);

    const token = localStorage.getItem('token');
    
    // Prepare answers array
    const answersArray = examData.questions.map(q => ({
        question_id: q.id,
        selected_answer: answers[q.id].selected_answer,
        time_taken: answers[q.id].time_taken
    }));

    try {
        const response = await fetch(`${API_URL}/candidate/attempts/${attemptId}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ answers: answersArray })
        });

        const data = await response.json();

        if (response.ok) {
            // Redirect to results page
            window.location.href = `exam-result.html?attempt_id=${attemptId}`;
        } else {
            alert(data.message || 'Failed to submit exam');
        }
    } catch (error) {
        console.error('Error submitting exam:', error);
        alert('Failed to submit exam');
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('submitModal');
    if (event.target === modal) {
        closeSubmitModal();
    }
}
