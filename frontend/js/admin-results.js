const API_URL = 'http://localhost:5001/api';
let allAttempts = [];
let filteredAttempts = [];
let sortColumn = 'id';
let sortDirection = 'desc';

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

    // Setup event listeners
    document.getElementById('searchInput').addEventListener('input', filterResults);
    document.getElementById('examFilter').addEventListener('change', filterResults);

    await loadResults();
});

async function loadResults() {
    const token = localStorage.getItem('token');

    try {
        const response = await fetch(`${API_URL}/admin/attempts`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            allAttempts = data.attempts;
            filteredAttempts = [...allAttempts];
            
            // Populate exam filter
            populateExamFilter();
            
            // Calculate stats
            calculateStats();
            
            // Display results
            displayResults();
        } else {
            document.getElementById('resultsBody').innerHTML = `
                <tr>
                    <td colspan="8" class="loading">
                        <p style="color: #dc3545;">Failed to load results: ${data.message}</p>
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading results:', error);
        document.getElementById('resultsBody').innerHTML = `
            <tr>
                <td colspan="8" class="loading">
                    <p style="color: #dc3545;">Failed to load results</p>
                </td>
            </tr>
        `;
    }
}

function populateExamFilter() {
    const examFilter = document.getElementById('examFilter');
    const uniqueExams = [...new Set(allAttempts.map(a => a.exam_title))];
    
    examFilter.innerHTML = '<option value="">All Exams</option>';
    uniqueExams.forEach(exam => {
        const option = document.createElement('option');
        option.value = exam;
        option.textContent = exam;
        examFilter.appendChild(option);
    });
}

function calculateStats() {
    const totalAttempts = allAttempts.length;
    const uniqueExams = new Set(allAttempts.map(a => a.exam_id)).size;
    
    // Calculate average score (percentage)
    let totalPercentage = 0;
    allAttempts.forEach(attempt => {
        const scoreText = attempt.score;
        const [correct, total] = scoreText.split('/').map(Number);
        totalPercentage += (correct / total) * 100;
    });
    const avgScore = totalAttempts > 0 ? (totalPercentage / totalAttempts).toFixed(1) : 0;
    
    // Calculate average time
    const totalTime = allAttempts.reduce((sum, attempt) => sum + attempt.total_time, 0);
    const avgTimeSeconds = totalAttempts > 0 ? Math.floor(totalTime / totalAttempts) : 0;
    const avgTimeMinutes = Math.floor(avgTimeSeconds / 60);
    const avgTimeSecondsRemainder = avgTimeSeconds % 60;
    const avgTimeFormatted = `${String(avgTimeMinutes).padStart(2, '0')}:${String(avgTimeSecondsRemainder).padStart(2, '0')}`;
    
    // Update stats
    document.getElementById('totalAttempts').textContent = totalAttempts;
    document.getElementById('totalExams').textContent = uniqueExams;
    document.getElementById('avgScore').textContent = `${avgScore}%`;
    document.getElementById('avgTime').textContent = avgTimeFormatted;
}

function filterResults() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const examFilter = document.getElementById('examFilter').value;
    
    filteredAttempts = allAttempts.filter(attempt => {
        const matchesSearch = 
            attempt.candidate_name.toLowerCase().includes(searchTerm) ||
            attempt.candidate_email.toLowerCase().includes(searchTerm);
        
        const matchesExam = !examFilter || attempt.exam_title === examFilter;
        
        return matchesSearch && matchesExam;
    });
    
    displayResults();
}

function displayResults() {
    const tbody = document.getElementById('resultsBody');
    const noResults = document.getElementById('noResults');
    const tableContainer = document.querySelector('.table-container');
    
    if (filteredAttempts.length === 0) {
        tableContainer.style.display = 'none';
        noResults.style.display = 'block';
        return;
    }
    
    tableContainer.style.display = 'block';
    noResults.style.display = 'none';
    
    // Sort attempts
    const sorted = sortAttempts(filteredAttempts);
    
    tbody.innerHTML = sorted.map(attempt => {
        // Parse score
        const [correct, total] = attempt.score.split('/').map(Number);
        const percentage = ((correct / total) * 100).toFixed(1);
        
        // Determine score badge class
        let badgeClass = 'score-poor';
        if (percentage >= 90) badgeClass = 'score-excellent';
        else if (percentage >= 75) badgeClass = 'score-good';
        else if (percentage >= 60) badgeClass = 'score-average';
        
        // Format time
        const hours = Math.floor(attempt.total_time / 3600);
        const minutes = Math.floor((attempt.total_time % 3600) / 60);
        const seconds = attempt.total_time % 60;
        const timeFormatted = hours > 0 
            ? `${hours}h ${minutes}m ${seconds}s`
            : `${minutes}m ${seconds}s`;
        
        // Format submitted date
        const submittedDate = new Date(attempt.submitted_at);
        const formattedDate = submittedDate.toLocaleString();
        
        return `
            <tr>
                <td>#${attempt.id}</td>
                <td>${attempt.candidate_name}</td>
                <td>${attempt.candidate_email}</td>
                <td>${attempt.exam_title}</td>
                <td>
                    <span class="score-badge ${badgeClass}">
                        ${attempt.score} (${percentage}%)
                    </span>
                </td>
                <td>
                    <span class="time-badge">${timeFormatted}</span>
                </td>
                <td>${formattedDate}</td>
                <td>
                    <button onclick="viewDetails(${attempt.id})" class="btn btn-small">
                        👁️ View
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function sortAttempts(attempts) {
    return [...attempts].sort((a, b) => {
        let aValue, bValue;
        
        switch(sortColumn) {
            case 'id':
                aValue = a.id;
                bValue = b.id;
                break;
            case 'candidate_name':
                aValue = a.candidate_name.toLowerCase();
                bValue = b.candidate_name.toLowerCase();
                break;
            case 'candidate_email':
                aValue = a.candidate_email.toLowerCase();
                bValue = b.candidate_email.toLowerCase();
                break;
            case 'exam_title':
                aValue = a.exam_title.toLowerCase();
                bValue = b.exam_title.toLowerCase();
                break;
            case 'score':
                // Parse score as percentage
                const [aCorrect, aTotal] = a.score.split('/').map(Number);
                const [bCorrect, bTotal] = b.score.split('/').map(Number);
                aValue = (aCorrect / aTotal) * 100;
                bValue = (bCorrect / bTotal) * 100;
                break;
            case 'total_time':
                aValue = a.total_time;
                bValue = b.total_time;
                break;
            case 'submitted_at':
                aValue = new Date(a.submitted_at);
                bValue = new Date(b.submitted_at);
                break;
            default:
                return 0;
        }
        
        if (sortDirection === 'asc') {
            return aValue > bValue ? 1 : aValue < bValue ? -1 : 0;
        } else {
            return aValue < bValue ? 1 : aValue > bValue ? -1 : 0;
        }
    });
}

function sortTable(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'desc';
    }
    
    displayResults();
}

function viewDetails(attemptId) {
    window.location.href = `admin-attempt-detail.html?attempt_id=${attemptId}`;
}

function refreshResults() {
    // Clear filters
    document.getElementById('searchInput').value = '';
    document.getElementById('examFilter').value = '';
    
    // Reload results
    loadResults();
}

function goToProfile() {
    window.location.href = 'profile.html';
}
