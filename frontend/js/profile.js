const API_URL = 'http://localhost:5001/api';

// Check if user is logged in
const user = JSON.parse(localStorage.getItem('user'));
const token = localStorage.getItem('token');

if (!user || !token) {
    window.location.href = 'login.html';
}

// Load user data on page load
window.addEventListener('DOMContentLoaded', () => {
    loadUserData();
});

function loadUserData() {
    // Display user role
    document.getElementById('userRole').textContent = user.role;
    
    // Populate form fields
    document.getElementById('fullname').value = user.fullname || '';
    document.getElementById('email').value = user.email || '';
    document.getElementById('role').value = user.role || '';
    document.getElementById('phone').value = user.phone || '';
    document.getElementById('address').value = user.address || '';
}

// Handle profile update
document.getElementById('profileForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fullname = document.getElementById('fullname').value;
    const phone = document.getElementById('phone').value;
    const address = document.getElementById('address').value;
    
    try {
        const response = await fetch(`${API_URL}/auth/update-profile`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                fullname,
                phone,
                address
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Update localStorage with new data
            const updatedUser = { ...user, fullname, phone, address };
            localStorage.setItem('user', JSON.stringify(updatedUser));
            
            showMessage('Profile updated successfully!', 'success');
            
            // Reload user data
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showMessage(data.message || 'Failed to update profile.', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage('Network error. Please check your connection.', 'error');
    }
});

// Handle password change
document.getElementById('passwordForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmNewPassword = document.getElementById('confirmNewPassword').value;
    
    // Validation
    if (newPassword !== confirmNewPassword) {
        showPasswordMessage('New passwords do not match!', 'error');
        return;
    }
    
    if (newPassword.length < 6) {
        showPasswordMessage('Password must be at least 6 characters long!', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/auth/change-password`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                currentPassword,
                newPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showPasswordMessage('Password changed successfully!', 'success');
            document.getElementById('passwordForm').reset();
        } else {
            showPasswordMessage(data.message || 'Failed to change password.', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showPasswordMessage('Network error. Please check your connection.', 'error');
    }
});

function resetForm() {
    loadUserData();
    showMessage('Changes cancelled.', 'error');
    setTimeout(() => {
        document.getElementById('message').style.display = 'none';
    }, 2000);
}

function logout() {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    window.location.href = 'login.html';
}

function showMessage(message, type) {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = message;
    messageDiv.className = `message ${type}`;
    
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

function showPasswordMessage(message, type) {
    const messageDiv = document.getElementById('passwordMessage');
    messageDiv.textContent = message;
    messageDiv.className = `message ${type}`;
    
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}
