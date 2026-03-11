const API_URL = 'http://localhost:5001/api';

document.getElementById('signupForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fullname = document.getElementById('fullname').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const role = document.getElementById('role').value;
    
    // Validation
    if (password !== confirmPassword) {
        showMessage('Passwords do not match!', 'error');
        return;
    }
    
    if (password.length < 6) {
        showMessage('Password must be at least 6 characters long!', 'error');
        return;
    }
    
    if (!role) {
        showMessage('Please select a role!', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/auth/signup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                fullname,
                email,
                password,
                role
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Show popup message
            alert('Account created successfully! Click OK to proceed to login.');
            showMessage('Account created successfully! Redirecting to login...', 'success');
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
        } else {
            showMessage(data.message || 'Signup failed. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage('Network error. Please check your connection.', 'error');
    }
});

function showMessage(message, type) {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = message;
    messageDiv.className = `message ${type}`;
    
    if (type === 'error') {
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}
