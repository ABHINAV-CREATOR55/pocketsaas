from flask import Flask, render_template, request, redirect, url_for, session, Response
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
    
    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Expenses Table
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
    
    # Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            monthly_budget REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    
    user_id = session["user_id"]
    username = session.get("username", "Student")
    
    selected_month = request.args.get("month", datetime.date.today().strftime("%b %Y"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Fetch distinct months
    cursor.execute("SELECT DISTINCT month_year FROM expenses WHERE user_id = ? ORDER BY id DESC", (user_id,))
    available_months = [row[0] for row in cursor.fetchall()]
    if selected_month not in available_months:
        available_months.insert(0, selected_month)

    # Fetch expenses for selected month
    cursor.execute("""
        SELECT id, title, amount, category, is_split, friend_name, friend_owes, is_settled, date_recorded 
        FROM expenses 
        WHERE user_id = ? AND month_year = ? 
        ORDER BY id DESC
    """, (user_id, selected_month))
    expenses = cursor.fetchall()
    
    # Total monthly spend
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND month_year = ?", (user_id, selected_month))
    total_val = cursor.fetchone()[0]
    total = total_val if total_val else 0.0
    
    # Total unsettled money friends owe to user
    cursor.execute("""
        SELECT SUM(friend_owes) FROM expenses 
        WHERE user_id = ? AND is_split = 1 AND is_settled = 0
    """, (user_id,))
    unsettled_val = cursor.fetchone()[0]
    roommate_owes = unsettled_val if unsettled_val else 0.0

    # User's budget setting
    cursor.execute("SELECT monthly_budget FROM settings WHERE user_id = ?", (user_id,))
    budget_row = cursor.fetchone()
    if not budget_row:
        cursor.execute("INSERT INTO settings (user_id, monthly_budget) VALUES (?, 7000.0)", (user_id,))
        conn.commit()
        monthly_budget = 7000.0
    else:
        monthly_budget = budget_row[0]

    # Category summary for Chart
    cursor.execute("""
        SELECT category, SUM(amount) 
        FROM expenses 
        WHERE user_id = ? AND month_year = ? 
        GROUP BY category
    """, (user_id, selected_month))
    category_summary = dict(cursor.fetchall())
    
    conn.close()

    # Budget & Safe Spend Calculation
    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = max(1, days_in_month - today.day + 1)
    
    remaining = monthly_budget - total
    daily_safe_spend = max(0.0, round(remaining / days_left, 1)) if remaining > 0 else 0.0
    
    # Budget Percentage
    budget_percent = round((total / monthly_budget) * 100, 1) if monthly_budget > 0 else 100.0

    return render_template(
        "index.html",
        username=username,
        current_month=selected_month,
        available_months=available_months,
        expenses=expenses,
        total=f"{total:,.2f}",
        remaining=f"{remaining:,.2f}",
        remaining_raw=remaining,
        budget=f"{monthly_budget:,.2f}",
        budget_raw=monthly_budget,
        budget_percent=budget_percent,
        roommate_owes=f"{roommate_owes:,.2f}",
        days_left=days_left,
        daily_safe_spend=f"{daily_safe_spend:,.2f}",
        chart_labels=json.dumps(list(category_summary.keys())),
        chart_values=json.dumps(list(category_summary.values()))
    )

# --- Authentication ---
@app.route("/auth")
def auth():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("auth.html")

@app.route("/signup", methods=["POST"])
def signup():
    username = request.form["username"].strip().lower()
    password = request.form["password"].strip()
    
    if len(username) < 3 or len(password) < 4:
        return render_template("auth.html", error="Username min 3 & Password min 4 chars.")
    
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO settings (user_id, monthly_budget) VALUES (?, 7000.0)", (user_id,))
        conn.commit()
        conn.close()
        
        session["user_id"] = user_id
        session["username"] = username
        return redirect(url_for("home"))
    except sqlite3.IntegrityError:
        return render_template("auth.html", error="Yeh Username pehle se registered hai!")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"].strip().lower()
    password = request.form["password"].strip()
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user[1], password):
        session["user_id"] = user[0]
        session["username"] = username
        return redirect(url_for("home"))
    return render_template("auth.html", error="Galat Username ya Password!")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth"))

# --- Expense Actions ---
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
        return redirect(url_for("home"))
        
    category = request.form.get("category", "Other")
    is_split = 1 if request.form.get("is_split") else 0
    friend_name = request.form.get("friend_name", "").strip() if is_split else ""
    
    # Custom split / Friend share calculation
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

    return redirect(url_for("home"))

@app.route("/settle/<int:expense_id>")
def settle(expense_id):
    if "user_id" not in session:
        return redirect(url_for("auth"))
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE expenses SET is_settled = 1 WHERE id = ? AND user_id = ?", (expense_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    if "user_id" not in session:
        return redirect(url_for("auth"))
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

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
    return redirect(url_for("home"))

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
    writer.writerow(["ID", "Title", "Category", "Total Bill", "Split", "Friend Name", "Friend Share (Owes)", "Status", "Date", "Month"])
    for row in rows:
        split_label = "Yes" if row[4] == 1 else "No"
        settled_label = "Settled (Paid)" if row[7] == 1 else "Pending"
        writer.writerow([row[0], row[1], row[2], row[3], split_label, row[5], row[6], settled_label, row[8], row[9]])
        
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={session['username']}_Expense_Ledger.csv"}
    )

if __name__ == "__main__":
    app.run(debug=False, port=5000)