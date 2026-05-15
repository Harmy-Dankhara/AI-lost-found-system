import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_FILE = 'complaint.db'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- AI Category & Urgency Detection ---
def detect_category_and_urgency(complaint_text):
    complaint = complaint_text.lower()
    categories = {
        'Electricity': ['light', 'electricity', 'fan', 'bulb', 'power'],
        'Sanitation': ['water', 'leak', 'bathroom', 'toilet', 'drain', 'hot water'],
        'Internet': ['wifi', 'internet', 'network', 'router'],
        'Hostel': ['room', 'warden', 'hostel', 'mess'],
        'Security': ['security', 'fight', 'threat', 'stolen', 'theft']
    }

    category = 'Other'
    for cat, keywords in categories.items():
        if any(keyword in complaint for keyword in keywords):
            category = cat
            break

    if any(word in complaint for word in ['urgent', 'immediately', 'emergency', 'critical', 'danger']):
        urgency = 'High'
    elif any(word in complaint for word in ['soon', 'need', 'important']):
        urgency = 'Medium'
    else:
        urgency = 'Low'

    return category, urgency

# --- Email Notification ---
def send_notification(email, subject, body):
    try:
        sender_email = 'complaints908@gmail.com'
        sender_password = 'ylpdxxhatomwwyzn'

        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, message.as_string())
    except Exception as e:
        print("Email failed:", e)

# --- DB Initialization ---
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                complaint TEXT NOT NULL,
                category TEXT,
                urgency TEXT,
                status TEXT DEFAULT 'Pending',
                filename TEXT,
                seen INTEGER DEFAULT 0,
                reply TEXT,
                resolved_on TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ("hod", "harmy@2025"))
        conn.commit()
        conn.close()

init_db()

# --- Routes ---
@app.route('/')
def home():
    return render_template("home.html")

@app.route('/submit', methods=['POST'])
def submit_complaint():
    name = request.form['name']
    email = request.form['email']
    complaint = request.form['complaint']
    file = request.files.get('evidence')

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    category, urgency = detect_category_and_urgency(complaint)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO complaints (name, email, complaint, category, urgency, status, filename, seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    ''', (name, email, complaint, category, urgency, 'Pending', filename))
    conn.commit()
    conn.close()

    send_notification(email, "Complaint Received", f"Dear {name},\n\nYour complaint has been submitted successfully.\n\nThank you.\n- Smart Complaint System")

    return render_template("thankyou.html", name=name)

@app.route('/reply/<int:complaint_id>', methods=['POST'])
def reply_complaint(complaint_id):
    if not session.get('admin'):
        return redirect(url_for('login'))

    reply_msg = request.form['reply']
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT name, email FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()

    if row:
        name, email = row
        subject = "Response to Your Complaint"
        body = f"Dear {name},\n\nThis is a response to your complaint:\n{reply_msg}\n\nRegards,\nAdmin"
        send_notification(email, subject, body)

        cursor.execute("UPDATE complaints SET reply = ? WHERE id = ?", (reply_msg, complaint_id))
        conn.commit()

    conn.close()
    return redirect(url_for('view_complaints'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin'):
        return redirect(url_for('view_complaints'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session['admin'] = True
            return redirect(url_for('view_complaints'))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route('/admin')
def view_complaints():
    if not session.get('admin'):
        return redirect(url_for('login'))

    search = request.args.get('search', '').lower()
    category = request.args.get('category', '')
    urgency = request.args.get('urgency', '')
    status = request.args.get('status', '')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if search:
        query += " AND LOWER(complaint) LIKE ?"
        params.append(f"%{search}%")

    if category:
        query += " AND category = ?"
        params.append(category)

    if urgency:
        query += " AND urgency = ?"
        params.append(urgency)

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY id ASC"

    cursor.execute(query, params)
    complaints = cursor.fetchall()

    unseen_ids = [c[0] for c in complaints if c[8] == 0]
    if unseen_ids:
        cursor.executemany("UPDATE complaints SET seen = 1 WHERE id = ?", [(i,) for i in unseen_ids])
        conn.commit()

    conn.close()
    return render_template("view_complaints.html", complaints=complaints, request=request)

@app.route('/update_status/<int:complaint_id>', methods=['POST'])
def update_status(complaint_id):
    if not session.get('admin'):
        return redirect(url_for('login'))

    new_status = request.form['status']
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if new_status == 'Resolved':
        cursor.execute("UPDATE complaints SET status = ?, resolved_on = ? WHERE id = ?", (
            new_status, datetime.now().strftime('%Y-%m-%d'), complaint_id))
    else:
        cursor.execute("UPDATE complaints SET status = ?, resolved_on = NULL WHERE id = ?", (new_status, complaint_id))

    conn.commit()
    conn.close()
    return redirect(url_for('view_complaints'))

@app.route('/delete/<int:complaint_id>', methods=['POST'])
def delete_complaint(complaint_id):
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_complaints'))

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

@app.route('/export')
def export_complaints():
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM complaints", conn)
    conn.close()

    excel_file = "complaints_export.xlsx"
    df.to_excel(excel_file, index=False)
    return send_file(excel_file, as_attachment=True)

@app.route('/analytics')
def analytics():
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT category, urgency, status FROM complaints")
    data = cursor.fetchall()
    conn.close()

    category_counts = {}
    urgency_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    status_counts = {'Pending': 0, 'Resolved': 0}

    for cat, urg, stat in data:
        category_counts[cat] = category_counts.get(cat, 0) + 1
        urgency_counts[urg] += 1
        status_counts[stat] += 1

    return render_template("analytics.html",
                           category_counts=category_counts,
                           urgency_counts=urgency_counts,
                           status_counts=status_counts)

@app.route('/reset_complaints')
def reset_complaints():
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints;")
    conn.commit()
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='complaints';")
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM complaints;")
    count = cursor.fetchone()[0]
    conn.close()
    return f"✅ All complaints deleted. Current complaint count: {count}. ID counter reset to 1."

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

if __name__ == '__main__':
    app.run(debug=True)
