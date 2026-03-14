// Shared Admin Navigation Functions
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('user');
    window.location.href = 'login.html';
}

document.addEventListener('DOMContentLoaded', () => {
    // Highlight the active link
    const currentPath = window.location.pathname.split('/').pop();
    const navLinks = document.querySelectorAll('.admin-nav-link');
    
    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href');
        if (currentPath === linkPath || (currentPath === '' && linkPath === 'admin-results.html')) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Populate role badge securely
    const role = localStorage.getItem('role') || 'Admin';
    const roleBadge = document.querySelector('.admin-role-badge');
    if (roleBadge) {
        roleBadge.textContent = role;
    }
});
