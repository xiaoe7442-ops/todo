from flask import Flask, request, jsonify, session
from flask_cors import CORS
from datetime import datetime
import sqlite3
from functools import wraps

DB_NAME = "todo.db"
app = Flask(__name__)
app.secret_key = "your-very-secret-key-change-this"

# ---------------------- CORS SETTINGS ----------------------
# 允许跨域请求，并允许携带凭证(Cookie)
# supports_credentials=True 对登录态维持至关重要
CORS(app, supports_credentials=True) 

# ---------------------- Database Init ----------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created TEXT,
            done INTEGER DEFAULT 0,
            user_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_NAME)

# ---------------------- Auth Decorator ----------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized', 'code': 401}), 401
        return f(*args, **kwargs)
    return wrapper

# ---------------------- Auth APIs ----------------------
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    pwd = data.get('password', '').strip()

    if not username or not pwd:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    conn = get_db(); c = conn.cursor()
    try:
        c.execute("INSERT INTO users(username, password) VALUES(?, ?)", (username, pwd))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': '用户名已存在'}), 400
    
    conn.close()
    return jsonify({'status': 'ok', 'message': '注册成功'})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    pwd = data.get('password')

    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, pwd))
    row = c.fetchone()
    conn.close()

    if row:
        session.permanent = True
        session['user_id'] = row[0]
        session['username'] = username
        return jsonify({'status': 'ok', 'username': username})
    
    return jsonify({'error': '用户名或密码有错误！'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'ok'})

# ---------------------- Task APIs ----------------------
@app.route('/tasks', methods=['GET'])
def get_tasks():
    # 结合了 login_required 的逻辑，但为了前端好判断，这里手动处理
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session.get('user_id')
    username = session.get('username')
    
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC", (user_id,))
    tasks = c.fetchall()
    conn.close()
    
    # 返回任务和当前用户名
    return jsonify({'tasks': tasks, 'username': username})

@app.route('/tasks', methods=['POST'])
@login_required
def add_task():
    data = request.get_json()
    title = data.get('title', '').strip()

    if not title:
        return jsonify({'error': 'Title required'}), 400

    uid = session['user_id']
    conn = get_db(); c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title, created, user_id) VALUES (?, ?, ?)",
        (title, datetime.now().isoformat(), uid)
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/tasks/<int:task_id>/toggle', methods=['PUT'])
@login_required
def toggle_task(task_id):
    uid = session['user_id']
    conn = get_db(); c = conn.cursor()
    
    # 验证任务是否属于当前用户
    c.execute("SELECT done FROM tasks WHERE id=? AND user_id=?", (task_id, uid))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    new_status = 0 if row[0] else 1
    c.execute("UPDATE tasks SET done=? WHERE id=? AND user_id=?", (new_status, task_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok', 'new_status': new_status})

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    uid = session['user_id']
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

# ---------------------- MAIN ----------------------
if __name__ == '__main__':
    init_db()
    # 开启 debug 模式，并在 8000 端口运行
    app.run(host='0.0.0.0', port=8000, debug=True)
