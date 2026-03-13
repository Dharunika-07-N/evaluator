const API_URL = 'http://localhost:5001/api';

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email,
                password
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const normalizedRole = (data.user.role || '').toLowerCase();

            // Store user data in localStorage
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('token', data.token);
            localStorage.setItem('role', normalizedRole);
            
            // Show success message and redirect
            showMessage('Login successful! Redirecting...', 'success');
            setTimeout(() => {
                if (normalizedRole === 'admin') {
                    window.location.href = 'admin-results.html';
                } else {
                    window.location.href = 'profile.html';
                }
            }, 1000);
        } else {
            showMessage(data.message || 'Login failed. Please check your credentials.', 'error');
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
