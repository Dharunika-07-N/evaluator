from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
CORS(app)

# Secret key for JWT
SECRET_KEY = 'your-secret-key-change-in-production'

# SQLite database setup
DATABASE = os.path.join(os.path.dirname(__file__), 'exam_system.db')

def get_db():
    """Create a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def init_db():
    """Initialize the database with tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password BLOB NOT NULL,
            role TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")

# Initialize database on startup
init_db()

# JWT Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (data['user_id'],))
            user_row = cursor.fetchone()
            conn.close()
            
            if not user_row:
                return jsonify({'message': 'User not found'}), 401
            
            # Convert row to dictionary
            current_user = dict(user_row)
                
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/')
def home():
    return jsonify({'message': 'Online Exam System API', 'status': 'running'})

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['fullname', 'email', 'password', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'{field} is required'}), 400
        
        fullname = data['fullname']
        email = data['email']
        password = data['password']
        role = data['role']
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            return jsonify({'message': 'Email already registered'}), 409
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert into database
        cursor.execute('''
            INSERT INTO users (fullname, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', (fullname, email, hashed_password, role))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': user_id
        }), 201
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'message': 'Email and password are required'}), 400
        
        email = data['email']
        password = data['password']
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Find user by email
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_row = cursor.fetchone()
        conn.close()
        
        if not user_row:
            return jsonify({'message': 'Invalid email or password'}), 401
        
        user = dict(user_row)
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password']):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user['id'],
            'email': user['email'],
            'role': user['role'],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, SECRET_KEY, algorithm='HS256')
        
        # Prepare user data (remove password)
        user_data = {
            'id': user['id'],
            'fullname': user['fullname'],
            'email': user['email'],
            'role': user['role'],
            'phone': user.get('phone', ''),
            'address': user.get('address', '')
        }
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/auth/update-profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    try:
        data = request.get_json()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Prepare update data
        updates = []
        params = []
        
        if 'fullname' in data:
            updates.append('fullname = ?')
            params.append(data['fullname'])
        if 'phone' in data:
            updates.append('phone = ?')
            params.append(data['phone'])
        if 'address' in data:
            updates.append('address = ?')
            params.append(data['address'])
        
        if updates:
            params.append(current_user['id'])
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
        
        return jsonify({
            'message': 'Profile updated successfully'
        }), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/auth/change-password', methods=['PUT'])
@token_required
def change_password(current_user):
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'currentPassword' not in data or 'newPassword' not in data:
            return jsonify({'message': 'Current password and new password are required'}), 400
        
        current_password = data['currentPassword']
        new_password = data['newPassword']
        
        # Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), current_user['password']):
            return jsonify({'message': 'Current password is incorrect'}), 401
        
        # Hash new password
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update password in database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE id = ?', 
                      (hashed_new_password, current_user['id']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
