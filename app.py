from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import csv
import io
import datetime
import calendar

app = Flask(__name__)
app.secret_key = "pocketsaas_super_secret_key_change_in_production"

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # 1 Gmail = 1 Secure Unique Account
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL DEFAULT 'Other',
            is_split INTEGER DEFAULT 0,
            friend_name TEXT DEFAULT '',
            friend_owes REAL DEFAULT 0.0,
            is_settled INTEGER DEFAULT 0,
            date_recorded TEXT NOT NULL,
            month_year TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            monthly_budget REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bug_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            issue_type TEXT NOT NULL,
            description TEXT NOT NULL,
            auto_status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def get_user_budget(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT monthly_budget FROM settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO settings (user_id, monthly_budget) VALUES (?, 7000.0)", (user_id,))
        conn.commit()
        budget = 7000.0
    else:
        budget = row[0]
    conn.close()
    return budget

# --- 1. Hero Landing Page ---
@app.route("/")
def landing():
    return render_template("landing.html")

# --- 2. Main Dashboard Tab ---
@app.route("/dashboard")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    user_id = session["user_id"]
    username = session.get("username", "Student")
    selected_month = request.args.get("month", datetime.date.today().strftime("%b %Y"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT month_year FROM expenses WHERE user_id = ? ORDER BY id DESC", (user_id,))
    available_months = [row[0] for row in cursor.fetchall()]
    if selected_month not in available_months:
        available_months.insert(0, selected_month)

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND month_year = ?", (user_id, selected_month))
    total_val = cursor.fetchone()[0]
    total = total_val if total_val else 0.0

    cursor.execute("SELECT SUM(friend_owes) FROM expenses WHERE user_id = ? AND is_split = 1 AND is_settled = 0", (user_id,))
    unsettled_val = cursor.fetchone()[0]
    roommate_owes = unsettled_val if unsettled_val else 0.0

    cursor.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND month_year = ? GROUP BY category", (user_id, selected_month))
    category_summary = dict(cursor.fetchall())
    
    cursor.execute("SELECT title, amount, category, date_recorded FROM expenses WHERE user_id = ? AND month_year = ? ORDER BY id DESC LIMIT 5", (user_id, selected_month))
    recent_transactions = cursor.fetchall()
    conn.close()

    monthly_budget = get_user_budget(user_id)
    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = max(1, days_in_month - today.day + 1)
    
    remaining = monthly_budget - total
    daily_safe_spend = max(0.0, round(remaining / days_left, 1)) if remaining > 0 else 0.0
    budget_percent = round((total / monthly_budget) * 100, 1) if monthly_budget > 0 else 100.0

    return render_template(
        "dashboard.html",
        active_tab="dashboard",
        username=username,
        current_month=selected_month,
        available_months=available_months,
        total=f"{total:,.2f}",
        remaining=f"{remaining:,.2f}",
        remaining_raw=remaining,
        budget=f"{monthly_budget:,.2f}",
        budget_percent=budget_percent,
        roommate_owes=f"{roommate_owes:,.2f}",
        days_left=days_left,
        daily_safe_spend=f"{daily_safe_spend:,.2f}",
        recent_transactions=recent_transactions,
        chart_labels=json.dumps(list(category_summary.keys())),
        chart_values=json.dumps(list(category_summary.values()))
    )

# --- 3. Expenses & Ledger Tab ---
@app.route("/expenses")
def expenses_page():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    user_id = session["user_id"]
    selected_month = request.args.get("month", datetime.date.today().strftime("%b %Y"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT month_year FROM expenses WHERE user_id = ? ORDER BY id DESC", (user_id,))
    available_months = [row[0] for row in cursor.fetchall()]
    if selected_month not in available_months:
        available_months.insert(0, selected_month)

    cursor.execute("""
        SELECT id, title, amount, category, date_recorded 
        FROM expenses WHERE user_id = ? AND month_year = ? 
        ORDER BY id DESC
    """, (user_id, selected_month))
    expenses = cursor.fetchall()
    conn.close()

    return render_template(
        "expenses.html",
        active_tab="expenses",
        username=session.get("username"),
        current_month=selected_month,
        available_months=available_months,
        expenses=expenses
    )

# --- 4. Split & GST Tab ---
@app.route("/split")
def split_page():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    user_id = session["user_id"]
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, amount, friend_name, friend_owes, is_settled, date_recorded 
        FROM expenses 
        WHERE user_id = ? AND is_split = 1 
        ORDER BY is_settled ASC, id DESC
    """, (user_id,))
    split_items = cursor.fetchall()
    
    cursor.execute("SELECT SUM(friend_owes) FROM expenses WHERE user_id = ? AND is_split = 1 AND is_settled = 0", (user_id,))
    pending_total = cursor.fetchone()[0] or 0.0
    conn.close()

    return render_template(
        "split.html",
        active_tab="split",
        username=session.get("username"),
        split_items=split_items,
        pending_total=f"{pending_total:,.2f}"
    )

# --- 5. Auto-Assistant Tab ---
@app.route("/help")
def help_page():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    user_id = session["user_id"]
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT issue_type, description, auto_status, created_at FROM bug_reports WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    history = cursor.fetchall()
    conn.close()

    return render_template("help.html", active_tab="help", username=session.get("username"), history=history)

# --- Add Expense Route ---
@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    title = request.form["title"].strip()
    try:
        amount = float(request.form["amount"])
    except ValueError:
        amount = 0.0
        
    if amount <= 0 or amount > 10000000:
        return redirect(request.referrer or url_for("home"))
        
    category = request.form.get("category", "Other")
    is_split = 1 if request.form.get("is_split") else 0
    friend_name = request.form.get("friend_name", "").strip() if is_split else ""
    
    friend_owes_input = request.form.get("friend_owes", "")
    if is_split:
        if friend_owes_input and float(friend_owes_input) > 0:
            friend_owes = round(float(friend_owes_input), 2)
        else:
            friend_owes = round(amount / 2.0, 2)
    else:
        friend_owes = 0.0
    
    today = datetime.date.today()
    date_str = today.strftime("%d %b")
    month_year = today.strftime("%b %Y")

    if title:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (user_id, title, amount, category, is_split, friend_name, friend_owes, is_settled, date_recorded, month_year) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (session["user_id"], title, amount, category, is_split, friend_name, friend_owes, date_str, month_year))
        conn.commit()
        conn.close()

    return redirect(request.referrer or url_for("home"))

@app.route("/settle/<int:expense_id>")
def settle(expense_id):
    if "user_id" not in session:
        return redirect(url_for("auth"))
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE expenses SET is_settled = 1 WHERE id = ? AND user_id = ?", (expense_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("split_page"))

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    if "user_id" not in session:
        return redirect(url_for("auth"))
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("expenses_page"))

@app.route("/reset_data", methods=["POST"])
def reset_data():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE user_id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/set_budget", methods=["POST"])
def set_budget():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    try:
        new_budget = float(request.form.get("budget", 7000.0))
        if 0 < new_budget <= 10000000:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET monthly_budget = ? WHERE user_id = ?", (new_budget, session["user_id"]))
            conn.commit()
            conn.close()
    except ValueError:
        pass
    return redirect(request.referrer or url_for("home"))

@app.route("/auto_diagnose", methods=["POST"])
def auto_diagnose():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    issue_type = request.form.get("issue_type", "General")
    user_id = session["user_id"]
    actions_taken = []
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ? AND (amount > 10000000 OR amount < 0)", (user_id,))
    overflow_count = cursor.fetchone()[0]
    if overflow_count > 0:
        cursor.execute("DELETE FROM expenses WHERE user_id = ? AND (amount > 10000000 OR amount < 0)", (user_id,))
        actions_taken.append(f"Auto-fixed {overflow_count} abnormal numbers.")
    
    cursor.execute("SELECT monthly_budget FROM settings WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (user_id, monthly_budget) VALUES (?, 7000.0)", (user_id,))
        actions_taken.append("Reset default budget allowance to ₹7,000.")

    report_msg = " | ".join(actions_taken) if actions_taken else "Zero data corruption detected."
    cursor.execute("""
        INSERT INTO bug_reports (user_id, issue_type, description, auto_status) 
        VALUES (?, ?, ?, ?)
    """, (user_id, issue_type, "Diagnostic Scan Completed", report_msg))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("help_page"))

@app.route("/export")
def export_csv():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, category, amount, is_split, friend_name, friend_owes, is_settled, date_recorded, month_year 
        FROM expenses WHERE user_id = ? ORDER BY id DESC
    """, (session["user_id"],))
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Category", "Total Bill", "Split", "Friend Name", "Friend Share", "Status", "Date", "Month"])
    for row in rows:
        split_label = "Yes" if row[4] == 1 else "No"
        settled_label = "Settled" if row[7] == 1 else "Pending"
        writer.writerow([row[0], row[1], row[2], row[3], split_label, row[5], row[6], settled_label, row[8], row[9]])
        
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={session['username']}_Expense_Ledger.csv"}
    )

# --- 6. AUTHENTICATION & PASSWORD RESET ---
@app.route("/auth")
def auth():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("auth.html")

@app.route("/signup", methods=["POST"])
def signup():
    username = request.form["username"].strip()
    email = request.form["email"].strip().lower()
    password = request.form["password"].strip()
    
    if len(username) < 2 or "@" not in email or len(password) < 4:
        return render_template("auth.html", error="Valid Gmail and password required (min 4 chars).")
    
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_pw))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO settings (user_id, monthly_budget) VALUES (?, 7000.0)", (user_id,))
        conn.commit()
        conn.close()
        
        session["user_id"] = user_id
        session["username"] = username
        session["email"] = email
        return redirect(url_for("home"))
    except sqlite3.IntegrityError:
        return render_template("auth.html", error="Yeh Gmail address pehle se registered hai! Login karein.")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"].strip().lower()
    password = request.form["password"].strip()
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user[2], password):
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["email"] = email
        return redirect(url_for("home"))
    return render_template("auth.html", error="Galat Gmail ya Password!")

@app.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = request.form["email"].strip().lower()
    new_password = request.form["new_password"].strip()
    
    if len(new_password) < 4:
        return render_template("auth.html", error="Naya password kam se kam 4 characters ka hona chahiye.")
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return render_template("auth.html", error="Yeh Gmail database mein nahi mila!")
        
    hashed_pw = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_pw, email))
    conn.commit()
    conn.close()
    
    return render_template("auth.html", success="Password reset ho gaya! Ab naye password se login karein.")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

if __name__ == "__main__":
    app.run(debug=False, port=5000)