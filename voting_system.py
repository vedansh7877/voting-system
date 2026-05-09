from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import hashlib
import sqlite3
import os
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = 'super-secret-voting-key-2024-change-this!'

# Database path - use /tmp for Render (ephemeral storage)
DB_PATH = os.environ.get('DATABASE_PATH', 'voting.db')

# HTML Templates (embedded)
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🗳️ Online Voting System</title>
    <meta name="viewport" content="width=device-width">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; margin-bottom: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
        .header h1 { color: #333; text-align: center; margin-bottom: 10px; }
        .user-info { text-align: right; color: #666; }
        .flash { padding: 15px; margin: 20px 0; border-radius: 10px; text-align: center; font-weight: bold; }
        .flash.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .candidate-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .candidate { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 20px; padding: 25px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); transition: transform 0.3s, box-shadow 0.3s; }
        .candidate:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(0,0,0,0.2); }
        .candidate h3 { color: #333; margin-bottom: 10px; }
        .candidate .position { color: #667eea; font-weight: bold; margin-bottom: 10px; }
        .candidate .desc { color: #666; margin-bottom: 20px; line-height: 1.5; }
        .vote-btn { background: linear-gradient(45deg, #667eea, #764ba2); color: white; border: none; padding: 12px 24px; border-radius: 25px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
        .vote-btn:hover { transform: scale(1.05); box-shadow: 0 10px 20px rgba(102,126,234,0.4); }
        .vote-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .votes { background: #f8f9ff; padding: 10px; border-radius: 10px; text-align: center; font-weight: bold; color: #667eea; margin-top: 10px; }
        .login-form, .admin-panel { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); max-width: 500px; margin: 50px auto; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 5px; color: #333; font-weight: bold; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 12px; border: 2px solid #e1e5e9; border-radius: 10px; font-size: 16px; transition: border-color 0.3s; }
        .form-group input:focus, .form-group textarea:focus { outline: none; border-color: #667eea; }
        .btn { background: linear-gradient(45deg, #667eea, #764ba2); color: white; border: none; padding: 12px 24px; border-radius: 25px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102,126,234,0.4); }
        .btn-danger { background: linear-gradient(45deg, #ff6b6b, #ee5a52); }
        .results-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .result-card { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
        .progress { height: 30px; background: #f0f0f0; border-radius: 15px; overflow: hidden; margin: 15px 0; }
        .progress-bar { height: 100%; background: linear-gradient(90deg, #4ecdc4, #44a08d); display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; }
        .logout { position: absolute; top: 20px; right: 20px; }
        @media (max-width: 768px) { .container { padding: 10px; } .candidate-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash {{category}}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% if session.user_id %}
        <div class="header">
            <div class="user-info">
                👋 Welcome, {{ session.username }}! 
                {% if session.is_admin %}<span style="color: #ff6b6b;">🔧 Admin</span>{% endif %}
                <a href="/logout" class="btn btn-danger" style="margin-left: 15px; padding: 8px 16px; font-size: 14px;">🚪 Logout</a>
            </div>
            <h1>🗳️ Vote for Your Candidate</h1>
            <p style="text-align: center; color: #666;">Total Votes Cast: <strong id="total-votes">{{ total_votes }}</strong></p>
        </div>
        {% endif %}

        {% if not session.user_id %}
            <div class="login-form">
                <h2>🔐 Please Login to Vote</h2>
                <form method="POST" action="/login">
                    <div class="form-group">
                        <label>👤 Username</label>
                        <input type="text" name="username" required>
                    </div>
                    <div class="form-group">
                        <label>🔑 Password</label>
                        <input type="password" name="password" required>
                    </div>
                    <button type="submit" class="btn">🚀 Login & Vote</button>
                </form>
                <p style="text-align: center; margin-top: 20px;">
                    💡 Demo: <strong>admin</strong> / <strong>admin123</strong>
                </p>
                <p style="text-align: center;">
                    <a href="/register" class="btn" style="margin-top: 10px; padding: 10px;">📝 New Voter?</a>
                </p>
            </div>
        {% else %}
            <div class="candidate-grid">
                {% for candidate in candidates %}
                <div class="candidate">
                    <h3>{{ candidate.name }}</h3>
                    <div class="position">{{ candidate.position }}</div>
                    {% if candidate.description %}
                    <div class="desc">{{ candidate.description }}</div>
                    {% endif %}
                    {% if not user_has_voted %}
                    <a href="/vote/{{ candidate.id }}" class="vote-btn" 
                       onclick="return confirm('✅ Confirm vote for {{ candidate.name }}?')">🗳️ Vote Now</a>
                    {% else %}
                    <button class="vote-btn" disabled>✅ Already Voted</button>
                    {% endif %}
                    <div class="votes">{{ candidate.votes }} votes</div>
                </div>
                {% endfor %}
            </div>

            {% if session.is_admin %}
            <div style="margin-top: 40px;">
                <h2 style="text-align: center;">🔧 Admin Panel</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
                    <div class="login-form">
                        <h3>➕ Add Candidate</h3>
                        <form method="POST" action="/admin">
                            <input type="hidden" name="action" value="add">
                            <div class="form-group"><label>Name</label><input name="name" required></div>
                            <div class="form-group"><label>Position</label><input name="position" required></div>
                            <div class="form-group"><label>Description</label><textarea name="description" rows="3"></textarea></div>
                            <button type="submit" class="btn">➕ Add</button>
                        </form>
                    </div>
                    <div class="login-form">
                        <h3>📊 View Results</h3>
                        <a href="/results" class="btn" style="width: 100%; text-align: center;">📈 See Results</a>
                    </div>
                </div>
            </div>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
'''

RESULTS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>📊 Voting Results</title>
    <meta name="viewport" content="width=device-width">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .back-btn { background: rgba(255,255,255,0.2); backdrop-filter: blur(10px); color: white; padding: 15px 25px; border-radius: 50px; text-decoration: none; font-weight: bold; display: inline-block; margin-bottom: 20px; transition: all 0.3s; }
        .back-btn:hover { background: rgba(255,255,255,0.3); transform: translateY(-2px); }
        .header { text-align: center; color: white; margin-bottom: 40px; }
        .total-votes { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; margin-bottom: 40px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
        .results-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 25px; }
        .result-card { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 25px; padding: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
        .candidate-name { font-size: 28px; font-weight: bold; color: #333; margin-bottom: 10px; }
        .candidate-position { color: #667eea; font-size: 18px; margin-bottom: 15px; }
        .vote-count { font-size: 48px; font-weight: bold; color: #4ecdc4; margin: 20px 0; }
        .percentage { font-size: 24px; color: #666; margin-bottom: 20px; }
        @media (max-width: 768px) { .results-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-btn">🏠 Back to Voting</a>
        
        <div class="header">
            <h1>📊 Election Results</h1>
            <div class="total-votes">
                <h2>Total Votes: <span style="color: #4ecdc4; font-size: 48px;">{{ total_votes }}</span></h2>
            </div>
        </div>

        <div class="results-grid">
            {% for candidate in candidates %}
            <div class="result-card">
                <div class="candidate-name">{{ candidate.name }}</div>
                <div class="candidate-position">{{ candidate.position }}</div>
                <div class="vote-count">{{ candidate.votes }} votes</div>
                {% if total_votes > 0 %}
                <div class="percentage">
                    {{ "%.1f"|format((candidate.votes/total_votes)*100) }}% 
                    <span style="font-size: 16px;">({{ candidate.votes }}/{{ total_votes }})</span>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
'''

REGISTER_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>📝 Voter Registration</title>
    <meta name="viewport" content="width=device-width">
    <style>
        body { font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .form-container { background: rgba(255,255,255,0.95); backdrop-filter: blur(20px); border-radius: 25px; padding: 40px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); max-width: 400px; width: 100%; }
        h2 { text-align: center; color: #333; margin-bottom: 30px; }
        .form-group { margin-bottom: 25px; }
        .form-group label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; }
        .form-group input { width: 100%; padding: 15px; border: 2px solid #e1e5e9; border-radius: 12px; font-size: 16px; transition: all 0.3s; }
        .form-group input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.1); }
        .btn { width: 100%; background: linear-gradient(45deg, #4ecdc4, #44a08d); color: white; border: none; padding: 15px; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(78,205,196,0.4); }
        .back-link { text-align: center; margin-top: 20px; }
        .back-link a { color: #667eea; text-decoration: none; font-weight: 600; }
    </style>
</head>
<body>
    <div class="form-container">
        <h2>📝 New Voter Registration</h2>
        <form method="POST">
            <div class="form-group">
                <label>👤 Username</label>
                <input type="text" name="username" required maxlength="50">
            </div>
            <div class="form-group">
                <label>🔑 Password</label>
                <input type="password" name="password" required minlength="6">
            </div>
            <button type="submit" class="btn">✅ Register & Vote</button>
        </form>
        <div class="back-link">
            <a href="/">← Back to Login</a>
        </div>
    </div>
</body>
</html>
'''

@contextmanager
def get_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise
    finally:
        try:
            conn.close()
        except:
            pass

def ensure_db_exists():
    """Initialize database on app startup"""
    try:
        with get_db() as db:
            # Check if tables exist
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'")
            if not cursor.fetchone():
                print("📝 Creating database tables...")
                
                db.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    has_voted INTEGER DEFAULT 0
                )''')
                
                db.execute('''CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    position TEXT NOT NULL,
                    description TEXT,
                    votes INTEGER DEFAULT 0
                )''')
                
                # Create admin user
                admin_hash = generate_password_hash('admin123')
                db.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, 1)", 
                          ('admin', admin_hash))
                
                # Add sample candidates
                db.execute("INSERT OR IGNORE INTO candidates (name, position, description) VALUES (?, ?, ?)",
                          ('Alice Johnson', 'President', 'Experienced leader with 10+ years in community service'))
                db.execute("INSERT OR IGNORE INTO candidates (name, position, description) VALUES (?, ?, ?)",
                          ('Bob Smith', 'President', 'Young innovator focused on technology and education'))
                db.execute("INSERT OR IGNORE INTO candidates (name, position, description) VALUES (?, ?, ?)",
                          ('Carol Davis', 'Vice President', 'Champion for environmental sustainability'))
                db.execute("INSERT OR IGNORE INTO candidates (name, position, description) VALUES (?, ?, ?)",
                          ('David Wilson', 'Vice President', 'Business expert with proven track record'))
                db.commit()
                print("✅ Database initialized successfully")
            else:
                print("✅ Database already exists")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise

@app.route('/', methods=['GET'])
def index():
    try:
        with get_db() as db:
            candidates = db.execute('SELECT * FROM candidates ORDER BY votes DESC').fetchall()
            total_votes = db.execute('SELECT SUM(votes) FROM candidates').fetchone()[0] or 0
            
            user_has_voted = False
            if 'user_id' in session:
                result = db.execute(
                    'SELECT has_voted FROM users WHERE id = ?', (session['user_id'],)
                ).fetchone()
                if result:
                    user_has_voted = result[0]
        
        return render_template_string(INDEX_HTML, 
                                    candidates=candidates, 
                                    total_votes=total_votes, 
                                    user_has_voted=user_has_voted,
                                    session=session)
    except Exception as e:
        print(f"❌ Error in index: {e}")
        return f"<h1>Error: {e}</h1>", 500

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form['username']
        password = request.form['password']
        
        with get_db() as db:
            user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = bool(user['is_admin'])
                flash('✅ Login successful! Ready to vote!', 'success')
            else:
                flash('❌ Invalid credentials!', 'error')
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"❌ Error in login: {e}")
        flash(f'❌ Error: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
            
            with get_db() as db:
                pw_hash = generate_password_hash(password)
                db.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                          (username, pw_hash))
                db.commit()
                flash('✅ Registration successful! Please login.', 'success')
                return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('❌ Username already exists!', 'error')
        except Exception as e:
            print(f"❌ Error in register: {e}")
            flash(f'❌ Error: {e}', 'error')
    
    return render_template_string(REGISTER_HTML)

@app.route('/vote/<int:candidate_id>')
def vote(candidate_id):
    try:
        if 'user_id' not in session:
            flash('❌ Please login first!', 'error')
            return redirect(url_for('index'))
        
        with get_db() as db:
            user = db.execute('SELECT has_voted FROM users WHERE id = ?', 
                             (session['user_id'],)).fetchone()
            
            if not user:
                flash('❌ User not found!', 'error')
                return redirect(url_for('index'))
            
            if user['has_voted']:
                flash('❌ You have already voted!', 'error')
                return redirect(url_for('index'))
            
            candidate = db.execute('SELECT * FROM candidates WHERE id = ?', 
                                  (candidate_id,)).fetchone()
            if not candidate:
                flash('❌ Candidate not found!', 'error')
                return redirect(url_for('index'))
            
            # Record vote
            db.execute('UPDATE users SET has_voted = 1 WHERE id = ?', (session['user_id'],))
            db.execute('UPDATE candidates SET votes = votes + 1 WHERE id = ?', (candidate_id,))
            db.commit()
            
            flash(f'✅ Thank you! Your vote for <strong>{candidate["name"]}</strong> has been recorded!', 'success')
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"❌ Error in vote: {e}")
        flash(f'❌ Error voting: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/admin', methods=['POST'])
def admin():
    try:
        if not session.get('is_admin'):
            flash('❌ Admin access required!', 'error')
            return redirect(url_for('index'))
        
        action = request.form.get('action')
        if action == 'add':
            name = request.form['name']
            position = request.form['position']
            description = request.form.get('description', '')
            
            with get_db() as db:
                db.execute('INSERT INTO candidates (name, position, description) VALUES (?, ?, ?)',
                          (name, position, description))
                db.commit()
                flash('✅ Candidate added successfully!', 'success')
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"❌ Error in admin: {e}")
        flash(f'❌ Error: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    try:
        with get_db() as db:
            candidates = db.execute('SELECT * FROM candidates ORDER BY votes DESC').fetchall()
            total_votes = db.execute('SELECT SUM(votes) FROM candidates').fetchone()[0] or 0
        
        return render_template_string(RESULTS_HTML, candidates=candidates, total_votes=total_votes)
    except Exception as e:
        print(f"❌ Error in results: {e}")
        return f"<h1>Error: {e}</h1>", 500

@app.route('/logout')
def logout():
    session.clear()
    flash('👋 Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    return f"<h1>Internal Server Error</h1><p>{str(error)}</p>", 500

# Initialize database when app starts
try:
    ensure_db_exists()
except Exception as e:
    print(f"❌ Failed to initialize database: {e}")

if __name__ == '__main__':
    ensure_db_exists()
    print("🚀 Voting System Ready!")
    print("🌐 Open: http://localhost:5000")
    print("👤 Admin: admin / admin123")
    print(f"💾 Database: {DB_PATH}")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
