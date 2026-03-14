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
import google.generativeai as genai
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
            status TEXT DEFAULT 'draft',
            scheduled_start TIMESTAMP,
            scheduled_end TIMESTAMP,
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
    
    # Create exam_attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            total_time INTEGER,
            score REAL,
            total_questions INTEGER,
            correct_answers INTEGER,
            status TEXT DEFAULT 'in_progress',
            tab_switches INTEGER DEFAULT 0,
            violation_reason TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Create question_answers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_answer TEXT,
            time_taken INTEGER,
            is_correct INTEGER DEFAULT 0,
            FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
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

def is_admin(user):
    return str(user.get('role', '')).lower() == 'admin'

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
def get_url_soup(url):
    """Fetch a URL and return a BeautifulSoup object."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'lxml')
    except Exception as e:
        print(f"Fetch error: {str(e)}")
        return None

def scrape_content(url, soup=None):
    """Scrape text content from a URL or pre-fetched soup object"""
    try:
        if not soup:
            soup = get_url_soup(url)
        if not soup:
            return None
        
        # Clone soup to avoid modifying original if needed elsewhere
        s = BeautifulSoup(str(soup), 'lxml')
        
        # Remove script and style elements
        for script in s(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text and clean it
        text = s.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        print(f"Scraping error: {str(e)}")
        return None

def normalize_text(value, max_len=None):
    """Normalize whitespace and optionally trim text length safely."""
    text = re.sub(r'\s+', ' ', (value or '')).strip()
    if max_len and len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0].strip() + '...'
    return text

def scrape_qa_pairs(url, soup=None):
    """Scrape structured question-answer pairs from a webpage when available."""
    try:
        if not soup:
            soup = get_url_soup(url)
        if not soup:
            return []

        # Remove non-content areas
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        pairs = []
        seen = set()

        def add_pair(question, answer):
            q = normalize_text(question, 220)
            a = normalize_text(answer, 240)

            if len(q) < 8 or len(a) < 20:
                return

            if not q.endswith('?'):
                # Keep prompts concise and question-like
                q = f"{q.rstrip('.:;')}?"

            key = (q.lower(), a.lower())
            if key in seen:
                return

            seen.add(key)
            pairs.append({'question': q, 'answer': a})

        # Strategy 1: explicit .question / .answer style blocks
        question_nodes = soup.select('.question, .faq-question, [class*="question"]')
        answer_nodes = soup.select('.answer, .faq-answer, [class*="answer"]')
        for q_node, a_node in zip(question_nodes, answer_nodes):
            add_pair(q_node.get_text(' ', strip=True), a_node.get_text(' ', strip=True))

        # Strategy 2: FAQ-like definition lists (dt/dd)
        for dt in soup.find_all('dt'):
            dd = dt.find_next_sibling('dd')
            if dd:
                add_pair(dt.get_text(' ', strip=True), dd.get_text(' ', strip=True))

        # Strategy 3: question paragraph followed by explanatory paragraph
        for p in soup.find_all('p'):
            question_text = normalize_text(p.get_text(' ', strip=True), 220)
            if not question_text.endswith('?'):
                continue

            next_p = p.find_next_sibling('p')
            if not next_p:
                continue

            answer_text = normalize_text(next_p.get_text(' ', strip=True), 240)
            add_pair(question_text, answer_text)

        return pairs
    except Exception as e:
        print(f"Q&A scraping error: {str(e)}")
        return []

def generate_mcq_from_qa_pairs(qa_pairs, topic, num_questions=5):
    """Generate MCQs from structured Q&A pairs with plausible distractors."""
    try:
        valid_pairs = []
        for qa in qa_pairs:
            q = normalize_text(qa.get('question'), 220)
            a = normalize_text(qa.get('answer'), 240)
            if len(q) >= 8 and len(a) >= 20:
                valid_pairs.append({'question': q, 'answer': a})

        if len(valid_pairs) < 4:
            return []

        answers_pool = list({qa['answer'] for qa in valid_pairs})
        questions = []

        random.shuffle(valid_pairs)
        for qa in valid_pairs:
            if len(questions) >= num_questions:
                break

            correct_answer = qa['answer']
            distractor_pool = [a for a in answers_pool if a.lower() != correct_answer.lower()]
            if len(distractor_pool) < 3:
                continue

            distractors = random.sample(distractor_pool, 3)
            options = [correct_answer] + distractors
            random.shuffle(options)

            questions.append({
                'question_text': qa['question'],
                'option_a': options[0],
                'option_b': options[1],
                'option_c': options[2],
                'option_d': options[3],
                'correct_answer': chr(65 + options.index(correct_answer)),
                'topic': topic
            })

        return questions
    except Exception as e:
        print(f"Q&A MCQ generation error: {str(e)}")
        return []

def generate_mcq_from_text(text, topic, num_questions=5):
    """Generate logical MCQs from text using concept-definition and usage relations only."""
    try:
        # Split and clean sentences
        raw_sentences = re.split(r'[.!?]+', text)
        sentences = [re.sub(r'\s+', ' ', s).strip() for s in raw_sentences]
        # Only keep sentences that look like they contain information (not too short, not too long)
        sentences = [s for s in sentences if 30 <= len(s) <= 400]

        if not sentences:
            return []

        # 1) Extract concept-definition facts
        definition_patterns = [
            r'^(?P<term>[A-Z][A-Za-z0-9\-\s]{2,70}?)\s+(?:is|are|refers to|means|is defined as|stands for)\s+(?P<definition>.+)$',
            r'^(?P<term>[A-Za-z][A-Za-z0-9\-\s]{2,70}?)\s+(?:consists of|includes|comprises)\s+(?P<definition>.+)$',
            r'^(?P<term>[A-Z][A-Za-z0-9\-\s]{2,70}?)\s*:\s*(?P<definition>.+)$',
            r'^(?P<term>[A-Z][A-Za-z0-9\-\s]{2,70}?)\s*-\s*(?P<definition>.+)$'
        ]

        facts = []
        seen_terms = set()
        for sentence in sentences:
            for pattern in definition_patterns:
                m = re.match(pattern, sentence, flags=re.IGNORECASE)
                if not m:
                    continue

                term = re.sub(r'\s+', ' ', m.group('term')).strip(' ,;:-')
                definition = re.sub(r'\s+', ' ', m.group('definition')).strip(' ,;:-')

                if len(term) < 3 or len(definition) < 20:
                    continue

                key = term.lower()
                if key in seen_terms:
                    continue

                seen_terms.add(key)
                facts.append({'term': term, 'definition': definition})
                break

        # 2) Extract usage relations: "X is used for A, B, and C"
        usage_facts = []
        usage_seen = set()
        usage_pattern = re.compile(
            r'^(?P<term>[A-Za-z][A-Za-z0-9\-\s]{2,70}?)\s+(?:is|are)\s+(?:used\s+for|useful\s+for|designed\s+to|provides|enables|allows)\s+(?P<uses>.+)$',
            flags=re.IGNORECASE
        )

        for sentence in sentences:
            m = usage_pattern.match(sentence)
            if not m:
                continue

            term = re.sub(r'\s+', ' ', m.group('term')).strip(' ,;:-')
            uses_text = m.group('uses')
            parts = re.split(r',|\band\b', uses_text, flags=re.IGNORECASE)
            uses = [re.sub(r'\s+', ' ', p).strip(' ,;:-') for p in parts]
            uses = [u for u in uses if len(u) >= 4]

            if len(uses) == 0:
                continue

            key = (term.lower(), tuple(sorted([u.lower() for u in uses])))
            if key in usage_seen:
                continue

            usage_seen.add(key)
            usage_facts.append({'term': term, 'uses': uses})

        questions = []

        # A) Definition-based MCQs
        if len(facts) >= 4:
            shuffled_facts = facts[:]
            random.shuffle(shuffled_facts)

            for fact in shuffled_facts:
                if len(questions) >= num_questions:
                    break

                other_defs = [f['definition'] for f in facts if f['term'].lower() != fact['term'].lower()]
                if len(other_defs) < 3:
                    continue

                distractors = random.sample(other_defs, 3)
                correct = fact['definition']
                options = [correct] + distractors
                random.shuffle(options)

                questions.append({
                    'question_text': f"What is the most accurate description of {fact['term']}?",
                    'option_a': options[0],
                    'option_b': options[1],
                    'option_c': options[2],
                    'option_d': options[3],
                    'correct_answer': chr(65 + options.index(correct)),
                    'topic': topic
                })

        # B) Usage-based MCQs
        if len(questions) < num_questions and len(usage_facts) >= 1:
            usage_pool = []
            for uf in usage_facts:
                usage_pool.extend(uf['uses'])
            usage_pool = list(dict.fromkeys([u for u in usage_pool if len(u) >= 4]))

            shuffled_usage = usage_facts[:]
            random.shuffle(shuffled_usage)

            for uf in shuffled_usage:
                if len(questions) >= num_questions:
                    break

                correct_use = random.choice(uf['uses'])
                distractor_pool = [u for u in usage_pool if u.lower() not in [x.lower() for x in uf['uses']]]
                if len(distractor_pool) < 3:
                    continue

                distractors = random.sample(distractor_pool, 3)
                options = [correct_use] + distractors
                random.shuffle(options)

                questions.append({
                    'question_text': f"Which of the following is a valid application of {uf['term']}?",
                    'option_a': options[0],
                    'option_b': options[1],
                    'option_c': options[2],
                    'option_d': options[3],
                    'correct_answer': chr(65 + options.index(correct_use)),
                    'topic': topic
                })

        # C) Statement-verification MCQs (logical; no blanks)
        if len(questions) < num_questions and len(facts) >= 4:
            shuffled_facts = facts[:]
            random.shuffle(shuffled_facts)

            for fact in shuffled_facts:
                if len(questions) >= num_questions:
                    break

                wrong_facts = [f for f in facts if f['term'].lower() != fact['term'].lower()]
                if len(wrong_facts) < 3:
                    continue

                wrong_samples = random.sample(wrong_facts, 3)
                correct_statement = f"{fact['term']} is {fact['definition']}"
                wrong_statements = [f"{fact['term']} is {wf['definition']}" for wf in wrong_samples]

                options = [correct_statement] + wrong_statements
                random.shuffle(options)

                questions.append({
                    'question_text': f"Which statement about {fact['term']} is correct?",
                    'option_a': options[0],
                    'option_b': options[1],
                    'option_c': options[2],
                    'option_d': options[3],
                    'correct_answer': chr(65 + options.index(correct_statement)),
                    'topic': topic
                })

        # Return only logical MCQs; no fill-in-the-blank fallback
        return questions[:num_questions]
    except Exception as e:
        print(f"Question generation error: {str(e)}")
        return []

def generate_mcq_with_ai(text, topic, num_questions=5):
    """Generate high-quality logical MCQs using Gemini AI."""
    if not GEMINI_API_KEY:
        return None

    try:
        # Use gemini-1.5-flash for much faster generation speed
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Act as an expert professor. Generate {num_questions} multiple choice questions (MCQs) based on the following text.
        The topic is: {topic}.
        
        Requirements:
        1. Each question must be logical and test understanding, not just rote memorization.
        2. Provide 4 options (A, B, C, D) for each question.
        3. Options must be plausible distractors related to the topic.
        4. Return the output ONLY as a valid JSON array of objects.
        5. Each object must have these exactly named keys: 
           "question_text", "option_a", "option_b", "option_c", "option_d", "correct_answer"
        6. "correct_answer" must be a single letter: "A", "B", "C", or "D".
        
        Text to analyze:
        {text[:4000]} 
        """
        
        response = model.generate_content(prompt)
        content = response.text.strip()
        
        # Clean up possible markdown code blocks in the response
        if content.startswith("```"):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1]) if lines[0].startswith("```") and lines[-1].startswith("```") else content
        
        # Parse JSON
        questions = json.loads(content)
        
        # Add topic to each question
        for q in questions:
            q['topic'] = topic
            
        return questions[:num_questions]
        
    except Exception as e:
        print(f"Gemini AI error: {str(e)}")
        return None

# Admin MCQ Management Routes
@app.route('/api/admin/generate-questions', methods=['POST'])
@token_required
def generate_questions(current_user):
    """Generate MCQ questions from a URL or text"""
    try:
        # Check if user is admin
        if not is_admin(current_user):
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        data = request.get_json()
        
        if 'url' not in data and 'text' not in data:
            return jsonify({'message': 'URL or text content is required'}), 400
        
        topic = data.get('topic', 'General')
        num_questions = int(data.get('num_questions', 5))
        
        qa_pairs = []

        # Get content either from URL or direct text
        if 'url' in data:
            url = data['url']
            soup = get_url_soup(url)
            if not soup:
                return jsonify({'message': 'Failed to reach website URL'}), 400
            
            content = scrape_content(url, soup=soup)
            qa_pairs = scrape_qa_pairs(url, soup=soup)
            source_url = url
        else:
            content = data['text']
            source_url = None
        
        # Generate questions using Gemini AI first, fallback to rule-based if needed
        questions = []
        
        # Try AI generation first
        questions = generate_mcq_with_ai(content, topic, num_questions)
        
        # Fallback to local structured Q&A scraping if AI fails or isn't configured
        if not questions and qa_pairs:
            questions = generate_mcq_from_qa_pairs(qa_pairs, topic, num_questions)

        # Final fallback to local pattern-based generation
        if not questions:
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

@app.route('/api/admin/questions', methods=['GET', 'POST', 'DELETE'])
@token_required
def manage_questions(current_user):
    """Get all questions or create a new question"""
    try:
        # Check if user is admin
        if not is_admin(current_user):
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

        elif request.method == 'DELETE':
            # Delete all questions
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM questions')
            conn.commit()
            conn.close()
            
            return jsonify({'message': 'All questions deleted successfully'}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/questions/<int:question_id>', methods=['PUT', 'DELETE'])
@token_required
def update_delete_question(current_user, question_id):
    """Update or delete a specific question"""
    try:
        # Check if user is admin
        if not is_admin(current_user):
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

@app.route('/api/admin/questions/upload', methods=['POST'])
@token_required
def upload_questions(current_user):
    """Bulk upload questions (Admin only)"""
    try:
        if not is_admin(current_user):
            return jsonify({'message': 'Access denied. Admin only.'}), 403

        data = request.get_json()
        questions = data.get('questions', []) if data else []

        if not isinstance(questions, list) or len(questions) == 0:
            return jsonify({'message': 'questions array is required'}), 400

        conn = get_db()
        cursor = conn.cursor()

        created_count = 0
        failed_count = 0
        errors = []

        for index, q in enumerate(questions, start=1):
            question_text = (q.get('question_text') or '').strip()
            option_a = (q.get('option_a') or '').strip()
            option_b = (q.get('option_b') or '').strip()
            option_c = (q.get('option_c') or '').strip()
            option_d = (q.get('option_d') or '').strip()
            correct_answer = (q.get('correct_answer') or '').strip().upper()
            topic = (q.get('topic') or 'General').strip()

            if not all([question_text, option_a, option_b, option_c, option_d]):
                failed_count += 1
                errors.append(f'Row {index}: Missing required fields')
                continue

            if correct_answer not in ['A', 'B', 'C', 'D']:
                failed_count += 1
                errors.append(f'Row {index}: correct_answer must be A, B, C, or D')
                continue

            cursor.execute('''
                INSERT INTO questions (question_text, option_a, option_b, option_c, option_d,
                                     correct_answer, topic, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (question_text, option_a, option_b, option_c, option_d,
                  correct_answer, topic, current_user['id']))
            created_count += 1

        conn.commit()
        conn.close()

        return jsonify({
            'message': 'Bulk upload completed',
            'created_count': created_count,
            'failed_count': failed_count,
            'errors': errors[:20]
        }), 200

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
        if not is_admin(current_user):
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
            print(f"DEBUG: Creating exam with data: {data}")
            
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
            status = data.get('status', 'draft')
            scheduled_start = data.get('scheduled_start')
            scheduled_end = data.get('scheduled_end')
            
            cursor.execute('''
                INSERT INTO exams (title, description, duration, total_marks, created_by, status, scheduled_start, scheduled_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, description, duration, total_marks, current_user['id'], status, scheduled_start, scheduled_end))
            
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
        if not is_admin(current_user):
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
            
            fields = ['title', 'description', 'duration', 'total_marks', 'is_active', 'status', 'scheduled_start', 'scheduled_end']
            
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
        if not is_admin(current_user):
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
            SELECT e.id, e.title, e.description, e.duration, e.total_marks, e.status, e.scheduled_start, e.scheduled_end,
                   (SELECT COUNT(*) FROM exam_questions WHERE exam_id = e.id) as question_count
            FROM exams e
            WHERE e.is_active = 1
            ORDER BY e.created_at DESC
        ''')
        
        exams = []
        now = datetime.now()
        for row in cursor.fetchall():
            exam = dict(row)
            status = exam.get('status')
            
            if status == 'started':
                exams.append(exam)
            elif status == 'scheduled':
                try:
                    start_time = datetime.fromisoformat(exam.get('scheduled_start', '').replace('Z', '+00:00')) if exam.get('scheduled_start') else None
                    end_time = datetime.fromisoformat(exam.get('scheduled_end', '').replace('Z', '+00:00')) if exam.get('scheduled_end') else None
                    
                    if start_time and end_time:
                        # Normalize now for comparison
                        if start_time.tzinfo:
                            now_aware = datetime.now(start_time.tzinfo)
                            if start_time <= now_aware <= end_time:
                                exams.append(exam)
                        else:
                            if start_time <= now <= end_time:
                                exams.append(exam)
                except Exception as e:
                    print(f"Time parse error: {e}")
                    pass
        
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
            SELECT id, title, description, duration, total_marks, status, scheduled_start, scheduled_end
            FROM exams
            WHERE id = ? AND is_active = 1
        ''', (exam_id,))
        
        exam_row = cursor.fetchone()
        
        if not exam_row:
            conn.close()
            return jsonify({'message': 'Exam not found or not active'}), 404
        
        exam = dict(exam_row)
        
        # Determine if it can be taken
        status = exam.get('status')
        can_take = False
        if status == 'started':
            can_take = True
        elif status == 'scheduled':
            try:
                start_time = datetime.fromisoformat(exam.get('scheduled_start', '').replace('Z', '+00:00')) if exam.get('scheduled_start') else None
                end_time = datetime.fromisoformat(exam.get('scheduled_end', '').replace('Z', '+00:00')) if exam.get('scheduled_end') else None
                if start_time and end_time:
                    now = datetime.now()
                    if start_time.tzinfo:
                        now = datetime.now(start_time.tzinfo)
                    if start_time <= now <= end_time:
                        can_take = True
            except:
                pass
                
        if not can_take:
            conn.close()
            return jsonify({'message': 'Exam is not currently active for candidates'}), 403

        
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

# ============= EXAM ATTEMPT ROUTES =============

@app.route('/api/candidate/exams/<int:exam_id>/start', methods=['POST'])
@token_required
def start_exam_attempt(current_user, exam_id):
    """Start a new exam attempt for a candidate"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if exam exists and is active
        cursor.execute('SELECT * FROM exams WHERE id = ? AND is_active = 1', (exam_id,))
        exam = cursor.fetchone()
        
        if not exam:
            conn.close()
            return jsonify({'message': 'Exam not found or not active'}), 404
        
        # Create exam attempt
        cursor.execute('''
            INSERT INTO exam_attempts (exam_id, user_id, status)
            VALUES (?, ?, 'in_progress')
        ''', (exam_id, current_user['id']))
        
        conn.commit()
        attempt_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'message': 'Exam attempt started',
            'attempt_id': attempt_id
        }), 201
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/candidate/attempts/<int:attempt_id>/tab-switch', methods=['POST'])
@token_required
def record_tab_switch(current_user, attempt_id):
    """Record tab switch during exam"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify attempt belongs to current user
        cursor.execute('''
            SELECT * FROM exam_attempts 
            WHERE id = ? AND user_id = ?
        ''', (attempt_id, current_user['id']))
        
        attempt = cursor.fetchone()
        
        if not attempt:
            conn.close()
            return jsonify({'message': 'Exam attempt not found'}), 404
        
        if attempt['status'] != 'in_progress':
            conn.close()
            return jsonify({'message': 'Exam is not in progress'}), 400
        
        # Increment tab switches count
        new_count = attempt['tab_switches'] + 1
        
        cursor.execute('''
            UPDATE exam_attempts 
            SET tab_switches = ?
            WHERE id = ?
        ''', (new_count, attempt_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Tab switch recorded',
            'tab_switches': new_count
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/candidate/attempts/<int:attempt_id>/submit', methods=['POST'])
@token_required
def submit_exam_attempt(current_user, attempt_id):
    """Submit exam answers and calculate score"""
    try:
        data = request.get_json()
        answers = data.get('answers', [])  # [{question_id, selected_answer, time_taken}]
        is_violation = data.get('is_violation', False)
        violation_reason = data.get('violation_reason', None)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify attempt belongs to current user
        cursor.execute('''
            SELECT * FROM exam_attempts 
            WHERE id = ? AND user_id = ?
        ''', (attempt_id, current_user['id']))
        
        attempt = cursor.fetchone()
        
        if not attempt:
            conn.close()
            return jsonify({'message': 'Exam attempt not found'}), 404
        
        if attempt['status'] == 'completed':
            conn.close()
            return jsonify({'message': 'Exam already submitted'}), 400
        
        exam_id = attempt['exam_id']
        
        # Get all questions with correct answers
        cursor.execute('''
            SELECT q.id, q.correct_answer, eq.marks
            FROM questions q
            INNER JOIN exam_questions eq ON q.id = eq.question_id
            WHERE eq.exam_id = ?
        ''', (exam_id,))
        
        questions_map = {}
        for row in cursor.fetchall():
            questions_map[row['id']] = {
                'correct_answer': row['correct_answer'],
                'marks': row['marks']
            }
        
        # Process answers and calculate score
        total_score = 0
        correct_count = 0
        total_questions = len(questions_map)
        total_time = 0
        
        for answer in answers:
            question_id = answer['question_id']
            selected_answer = answer.get('selected_answer')
            time_taken = answer.get('time_taken', 0)
            total_time += time_taken
            
            is_correct = 0
            if question_id in questions_map:
                correct_answer = questions_map[question_id]['correct_answer']
                marks = questions_map[question_id]['marks']
                
                if selected_answer and selected_answer.upper() == correct_answer.upper():
                    is_correct = 1
                    correct_count += 1
                    total_score += marks
            
            # Save answer
            cursor.execute('''
                INSERT INTO question_answers 
                (attempt_id, question_id, selected_answer, time_taken, is_correct)
                VALUES (?, ?, ?, ?, ?)
            ''', (attempt_id, question_id, selected_answer, time_taken, is_correct))
        
        # Update exam attempt
        status = 'violated' if is_violation else 'completed'
        
        cursor.execute('''
            UPDATE exam_attempts 
            SET end_time = CURRENT_TIMESTAMP,
                total_time = ?,
                score = ?,
                total_questions = ?,
                correct_answers = ?,
                status = ?,
                violation_reason = ?
            WHERE id = ?
        ''', (total_time, total_score, total_questions, correct_count, status, violation_reason, attempt_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Exam submitted successfully',
            'score': total_score,
            'correct_answers': correct_count,
            'total_questions': total_questions,
            'total_time': total_time
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/candidate/attempts/<int:attempt_id>', methods=['GET'])
@token_required
def get_attempt_result(current_user, attempt_id):
    """Get exam attempt results for candidate"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get attempt details
        cursor.execute('''
            SELECT ea.*, e.title, e.total_marks, e.duration
            FROM exam_attempts ea
            INNER JOIN exams e ON ea.exam_id = e.id
            WHERE ea.id = ? AND ea.user_id = ?
        ''', (attempt_id, current_user['id']))
        
        attempt = cursor.fetchone()
        
        if not attempt:
            conn.close()
            return jsonify({'message': 'Exam attempt not found'}), 404
        
        result = dict(attempt)
        conn.close()
        
        return jsonify({'result': result}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/attempts', methods=['GET'])
@token_required
def get_all_attempts(current_user):
    """Get all exam attempts with candidate details (Admin only)"""
    try:
        # Check if user is admin
        if not is_admin(current_user):
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ea.*, 
                   u.fullname as candidate_name,
                   u.email as candidate_email,
                   e.title as exam_title,
                   e.total_marks
            FROM exam_attempts ea
            INNER JOIN users u ON ea.user_id = u.id
            INNER JOIN exams e ON ea.exam_id = e.id
            WHERE ea.status IN ('completed', 'violated')
            ORDER BY ea.end_time DESC
        ''')
        
        attempts = []
        for row in cursor.fetchall():
            attempts.append(dict(row))
        
        conn.close()
        return jsonify({'attempts': attempts}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/api/admin/attempts/<int:attempt_id>', methods=['GET'])
@token_required
def get_attempt_details(current_user, attempt_id):
    """Get detailed exam attempt with all answers (Admin only)"""
    try:
        # Check if user is admin
        if not is_admin(current_user):
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get attempt details
        cursor.execute('''
            SELECT ea.*, 
                   u.fullname as candidate_name,
                   u.email as candidate_email,
                   e.title as exam_title,
                   e.total_marks,
                   e.duration
            FROM exam_attempts ea
            INNER JOIN users u ON ea.user_id = u.id
            INNER JOIN exams e ON ea.exam_id = e.id
            WHERE ea.id = ?
        ''', (attempt_id,))
        
        attempt = cursor.fetchone()
        
        if not attempt:
            conn.close()
            return jsonify({'message': 'Exam attempt not found'}), 404
        
        result = dict(attempt)
        
        # Get all answers
        cursor.execute('''
            SELECT qa.*, q.question_text, q.correct_answer,
                   q.option_a, q.option_b, q.option_c, q.option_d
            FROM question_answers qa
            INNER JOIN questions q ON qa.question_id = q.id
            WHERE qa.attempt_id = ?
        ''', (attempt_id,))
        
        answers = []
        for row in cursor.fetchall():
            answers.append(dict(row))
        
        result['answers'] = answers
        
        conn.close()
        return jsonify({'result': result}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
