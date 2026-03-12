from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os
import requests
from bs4 import BeautifulSoup
import re
import random

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
    
    # Create questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            topic TEXT,
            source_url TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Create exams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            duration INTEGER NOT NULL,
            total_marks INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Create exam_questions junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            marks INTEGER DEFAULT 1,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
            UNIQUE(exam_id, question_id)
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

# Helper functions for web scraping and question generation
def scrape_content(url):
    """Scrape text content from a URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text and clean it
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    except Exception as e:
        print(f"Scraping error: {str(e)}")
        return None

def generate_mcq_from_text(text, topic, num_questions=5):
    """Generate MCQ questions from text content"""
    try:
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 50]
        
        if len(sentences) < num_questions:
            num_questions = len(sentences)
        
        # Select random sentences to create questions from
        selected_sentences = random.sample(sentences, min(num_questions, len(sentences)))
        
        questions = []
        
        for sentence in selected_sentences:
            # Find important words (nouns, proper nouns, numbers, technical terms)
            words = sentence.split()
            
            # Look for capitalized words, numbers, or words in quotes
            important_words = []
            for i, word in enumerate(words):
                clean_word = re.sub(r'[^\w\s]', '', word)
                if (clean_word and 
                    (len(clean_word) > 4 and word[0].isupper() and i > 0) or
                    clean_word.isdigit() or
                    len(clean_word) > 8):
                    important_words.append((i, word, clean_word))
            
            if not important_words:
                continue
            
            # Pick a random important word to make the question
            idx, original_word, answer = random.choice(important_words)
            
            # Create the question by replacing the word with a blank
            question_words = words.copy()
            question_words[idx] = "______"
            question_text = " ".join(question_words) + "?"
            
            # Generate distractors (wrong answers)
            distractors = []
            
            # Simple distractor generation
            if answer.isdigit():
                num = int(answer)
                distractors = [str(num + random.randint(1, 10)), 
                             str(num - random.randint(1, 10)),
                             str(num * 2)]
            else:
                # Generate generic distractors
                distractor_options = [
                    f"{answer[:len(answer)//2]}",
                    f"{answer.upper()}",
                    f"{answer.lower()}",
                    f"Not {answer}",
                    f"{answer}s",
                    "None of the above",
                    "All of the above",
                    f"Similar to {answer}"
                ]
                distractors = random.sample([d for d in distractor_options if d != answer], 3)
            
            # Combine correct answer with distractors
            options = [answer] + distractors[:3]
            random.shuffle(options)
            
            # Determine which option is correct
            correct_index = options.index(answer)
            correct_answer = chr(65 + correct_index)  # A, B, C, or D
            
            questions.append({
                'question_text': question_text,
                'option_a': options[0],
                'option_b': options[1],
                'option_c': options[2],
                'option_d': options[3],
                'correct_answer': correct_answer,
                'topic': topic
            })
        
        return questions
    except Exception as e:
        print(f"Question generation error: {str(e)}")
        return []

# Admin MCQ Management Routes
@app.route('/api/admin/generate-questions', methods=['POST'])
@token_required
def generate_questions(current_user):
    """Generate MCQ questions from a URL or text"""
    try:
        # Check if user is admin
        if current_user['role'] != 'Admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        data = request.get_json()
        
        if 'url' not in data and 'text' not in data:
            return jsonify({'message': 'URL or text content is required'}), 400
        
        topic = data.get('topic', 'General')
        num_questions = int(data.get('num_questions', 5))
        
        # Get content either from URL or direct text
        if 'url' in data:
            content = scrape_content(data['url'])
            if not content:
                return jsonify({'message': 'Failed to scrape content from URL'}), 400
            source_url = data['url']
        else:
            content = data['text']
            source_url = None
        
        # Generate questions
        questions = generate_mcq_from_text(content, topic, num_questions)
        
        if not questions:
            return jsonify({'message': 'Failed to generate questions from content'}), 400
        
        # Save questions to database
        conn = get_db()
        cursor = conn.cursor()
        
        saved_questions = []
        for q in questions:
            cursor.execute('''
                INSERT INTO questions (question_text, option_a, option_b, option_c, option_d, 
                                     correct_answer, topic, source_url, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (q['question_text'], q['option_a'], q['option_b'], q['option_c'], 
                  q['option_d'], q['correct_answer'], q['topic'], source_url, current_user['id']))
            
            question_id = cursor.lastrowid
            saved_questions.append({
                'id': question_id,
                **q
            })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'{len(saved_questions)} questions generated successfully',
            'questions': saved_questions
        }), 201
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/questions', methods=['GET', 'POST'])
@token_required
def manage_questions(current_user):
    """Get all questions or create a new question"""
    try:
        # Check if user is admin
        if current_user['role'] != 'Admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        if request.method == 'GET':
            # Get all questions
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM questions ORDER BY created_at DESC')
            questions = cursor.fetchall()
            conn.close()
            
            questions_list = []
            for q in questions:
                questions_list.append({
                    'id': q['id'],
                    'question_text': q['question_text'],
                    'option_a': q['option_a'],
                    'option_b': q['option_b'],
                    'option_c': q['option_c'],
                    'option_d': q['option_d'],
                    'correct_answer': q['correct_answer'],
                    'topic': q['topic'],
                    'source_url': q['source_url'],
                    'created_at': q['created_at']
                })
            
            return jsonify({'questions': questions_list}), 200
        
        elif request.method == 'POST':
            # Create a new question manually
            data = request.get_json()
            
            required_fields = ['question_text', 'option_a', 'option_b', 'option_c', 
                             'option_d', 'correct_answer']
            for field in required_fields:
                if field not in data:
                    return jsonify({'message': f'{field} is required'}), 400
            
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO questions (question_text, option_a, option_b, option_c, option_d,
                                     correct_answer, topic, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['question_text'], data['option_a'], data['option_b'], data['option_c'],
                  data['option_d'], data['correct_answer'], data.get('topic', 'General'), 
                  current_user['id']))
            
            question_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return jsonify({
                'message': 'Question created successfully',
                'question_id': question_id
            }), 201
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/questions/<int:question_id>', methods=['PUT', 'DELETE'])
@token_required
def update_delete_question(current_user, question_id):
    """Update or delete a specific question"""
    try:
        # Check if user is admin
        if current_user['role'] != 'Admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        if request.method == 'PUT':
            # Update question
            data = request.get_json()
            
            updates = []
            params = []
            
            fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 
                     'correct_answer', 'topic']
            
            for field in fields:
                if field in data:
                    updates.append(f'{field} = ?')
                    params.append(data[field])
            
            if updates:
                params.append(question_id)
                query = f"UPDATE questions SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
            
            conn.close()
            return jsonify({'message': 'Question updated successfully'}), 200
        
        elif request.method == 'DELETE':
            # Delete question
            cursor.execute('DELETE FROM questions WHERE id = ?', (question_id,))
            conn.commit()
            conn.close()
            
            return jsonify({'message': 'Question deleted successfully'}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

# ============= EXAM MANAGEMENT ROUTES =============

@app.route('/api/admin/exams', methods=['GET', 'POST'])
@token_required
def manage_exams(current_user):
    """List all exams or create a new exam (Admin only)"""
    try:
        # Check if user is admin
        if current_user['role'] != 'Admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        if request.method == 'GET':
            # Get all exams
            cursor.execute('''
                SELECT e.*, u.fullname as creator_name,
                       (SELECT COUNT(*) FROM exam_questions WHERE exam_id = e.id) as question_count
                FROM exams e
                LEFT JOIN users u ON e.created_by = u.id
                ORDER BY e.created_at DESC
            ''')
            
            exams = []
            for row in cursor.fetchall():
                exams.append(dict(row))
            
            conn.close()
            return jsonify({'exams': exams}), 200
        
        elif request.method == 'POST':
            # Create new exam
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['title', 'duration', 'total_marks']
            for field in required_fields:
                if field not in data:
                    conn.close()
                    return jsonify({'message': f'{field} is required'}), 400
            
            title = data['title']
            description = data.get('description', '')
            duration = data['duration']  # in minutes
            total_marks = data['total_marks']
            
            cursor.execute('''
                INSERT INTO exams (title, description, duration, total_marks, created_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, description, duration, total_marks, current_user['id']))
            
            conn.commit()
            exam_id = cursor.lastrowid
            conn.close()
            
            return jsonify({
                'message': 'Exam created successfully',
                'exam_id': exam_id
            }), 201
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/exams/<int:exam_id>', methods=['GET', 'PUT', 'DELETE'])
@token_required
def manage_exam_detail(current_user, exam_id):
    """Get, update, or delete a specific exam (Admin only)"""
    try:
        # Check if user is admin
        if current_user['role'] != 'Admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        if request.method == 'GET':
            # Get exam details with questions
            cursor.execute('''
                SELECT e.*, u.fullname as creator_name
                FROM exams e
                LEFT JOIN users u ON e.created_by = u.id
                WHERE e.id = ?
            ''', (exam_id,))
            
            exam_row = cursor.fetchone()
            
            if not exam_row:
                conn.close()
                return jsonify({'message': 'Exam not found'}), 404
            
            exam = dict(exam_row)
            
            # Get questions for this exam
            cursor.execute('''
                SELECT q.*, eq.marks
                FROM questions q
                INNER JOIN exam_questions eq ON q.id = eq.question_id
                WHERE eq.exam_id = ?
                ORDER BY eq.id
            ''', (exam_id,))
            
            questions = []
            for row in cursor.fetchall():
                questions.append(dict(row))
            
            exam['questions'] = questions
            exam['question_count'] = len(questions)
            
            conn.close()
            return jsonify({'exam': exam}), 200
        
        elif request.method == 'PUT':
            # Update exam
            data = request.get_json()
            
            updates = []
            params = []
            
            fields = ['title', 'description', 'duration', 'total_marks', 'is_active']
            
            for field in fields:
                if field in data:
                    updates.append(f'{field} = ?')
                    params.append(data[field])
            
            if updates:
                params.append(exam_id)
                query = f"UPDATE exams SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
            
            conn.close()
            return jsonify({'message': 'Exam updated successfully'}), 200
        
        elif request.method == 'DELETE':
            # Delete exam (cascade will delete exam_questions)
            cursor.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
            conn.commit()
            conn.close()
            
            return jsonify({'message': 'Exam deleted successfully'}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/exams/<int:exam_id>/questions', methods=['POST', 'DELETE'])
@token_required
def manage_exam_questions(current_user, exam_id):
    """Add or remove questions from an exam (Admin only)"""
    try:
        # Check if user is admin
        if current_user['role'] != 'Admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        if request.method == 'POST':
            # Add questions to exam
            data = request.get_json()
            
            if 'question_ids' not in data:
                conn.close()
                return jsonify({'message': 'question_ids array is required'}), 400
            
            question_ids = data['question_ids']
            marks_per_question = data.get('marks', 1)
            
            # Add each question to exam
            added_count = 0
            for question_id in question_ids:
                try:
                    cursor.execute('''
                        INSERT INTO exam_questions (exam_id, question_id, marks)
                        VALUES (?, ?, ?)
                    ''', (exam_id, question_id, marks_per_question))
                    added_count += 1
                except sqlite3.IntegrityError:
                    # Question already in exam, skip
                    pass
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'message': f'{added_count} questions added to exam',
                'added_count': added_count
            }), 200
        
        elif request.method == 'DELETE':
            # Remove a question from exam
            data = request.get_json()
            
            if 'question_id' not in data:
                conn.close()
                return jsonify({'message': 'question_id is required'}), 400
            
            question_id = data['question_id']
            
            cursor.execute('''
                DELETE FROM exam_questions 
                WHERE exam_id = ? AND question_id = ?
            ''', (exam_id, question_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({'message': 'Question removed from exam'}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/candidate/exams', methods=['GET'])
@token_required
def get_available_exams(current_user):
    """Get list of active exams for candidates"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.id, e.title, e.description, e.duration, e.total_marks,
                   (SELECT COUNT(*) FROM exam_questions WHERE exam_id = e.id) as question_count
            FROM exams e
            WHERE e.is_active = 1
            ORDER BY e.created_at DESC
        ''')
        
        exams = []
        for row in cursor.fetchall():
            exams.append(dict(row))
        
        conn.close()
        return jsonify({'exams': exams}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/candidate/exams/<int:exam_id>', methods=['GET'])
@token_required
def get_exam_for_candidate(current_user, exam_id):
    """Get exam details with shuffled questions for a candidate"""
    try:
        import random
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get exam details
        cursor.execute('''
            SELECT id, title, description, duration, total_marks
            FROM exams
            WHERE id = ? AND is_active = 1
        ''', (exam_id,))
        
        exam_row = cursor.fetchone()
        
        if not exam_row:
            conn.close()
            return jsonify({'message': 'Exam not found or not active'}), 404
        
        exam = dict(exam_row)
        
        # Get questions for this exam (without correct answers for security)
        cursor.execute('''
            SELECT q.id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, 
                   q.topic, eq.marks
            FROM questions q
            INNER JOIN exam_questions eq ON q.id = eq.question_id
            WHERE eq.exam_id = ?
        ''', (exam_id,))
        
        questions = []
        for row in cursor.fetchall():
            question = dict(row)
            
            # Shuffle options for each question
            options = [
                {'key': 'A', 'text': question['option_a']},
                {'key': 'B', 'text': question['option_b']},
                {'key': 'C', 'text': question['option_c']},
                {'key': 'D', 'text': question['option_d']}
            ]
            random.shuffle(options)
            
            question['options'] = options
            # Remove individual option fields
            del question['option_a']
            del question['option_b']
            del question['option_c']
            del question['option_d']
            
            questions.append(question)
        
        # Shuffle questions order for each candidate
        random.shuffle(questions)
        
        exam['questions'] = questions
        exam['question_count'] = len(questions)
        
        conn.close()
        return jsonify({'exam': exam}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
