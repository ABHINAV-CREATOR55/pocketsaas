from flask import Flask, render_template, request, redirect, url_for, Response
import sqlite3
import json
import csv
import io
import datetime
import calendar

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL DEFAULT 'Other',
            is_split INTEGER DEFAULT 0,
            date_recorded TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value REAL NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('monthly_budget', 7000.0)")
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # 1. Fetch expenses
    cursor.execute("SELECT id, title, amount, category, is_split, date_recorded FROM expenses ORDER BY id DESC")
    expenses = cursor.fetchall()
    
    # 2. Total calculation
    cursor.execute("SELECT SUM(amount) FROM expenses")
    total_val = cursor.fetchone()[0]
    total = total_val if total_val else 0.0
    
    # 3. Roommate Split calculation (50% share)
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE is_split = 1")
    split_val = cursor.fetchone()[0]
    roommate_owes = (split_val / 2.0) if split_val else 0.0

    # 4. Budget setting
    cursor.execute("SELECT value FROM settings WHERE key = 'monthly_budget'")
    budget_row = cursor.fetchone()
    monthly_budget = budget_row[0] if budget_row else 7000.0

    # 5. Category breakdown for Chart
    cursor.execute("SELECT category, SUM(amount) FROM expenses GROUP BY category")
    cat_rows = cursor.fetchall()
    category_summary = dict(cat_rows)
    
    conn.close()

    # Smart Daily Safe Spend calculation
    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = max(1, days_in_month - today.day + 1)
    
    remaining = monthly_budget - total
    daily_safe_spend = max(0.0, round(remaining / days_left, 1)) if remaining > 0 else 0.0
    budget_percent = min(100, round((total / monthly_budget) * 100)) if monthly_budget > 0 else 100
    
    chart_labels = list(category_summary.keys())
    chart_values = list(category_summary.values())

    return render_template(
        "index.html",
        expenses=expenses,
        total=round(total, 2),
        remaining=round(remaining, 2),
        budget=round(monthly_budget, 2),
        budget_percent=budget_percent,
        roommate_owes=round(roommate_owes, 2),
        days_left=days_left,
        daily_safe_spend=daily_safe_spend,
        chart_labels=json.dumps(chart_labels),
        chart_values=json.dumps(chart_values)
    )

@app.route("/set_budget", methods=["POST"])
def set_budget():
    try:
        new_budget = float(request.form.get("budget", 7000.0))
        if new_budget > 0:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'monthly_budget'", (new_budget,))
            conn.commit()
            conn.close()
    except ValueError:
        pass
    return redirect(url_for("home"))

@app.route("/add", methods=["POST"])
def add():
    title = request.form["title"].strip()
    try:
        amount = float(request.form["amount"])
    except ValueError:
        amount = 0.0
    category = request.form.get("category", "Other")
    is_split = 1 if request.form.get("is_split") else 0
    today_str = datetime.date.today().strftime("%d %b")

    if title and amount > 0:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO expenses (title, amount, category, is_split, date_recorded) VALUES (?, ?, ?, ?, ?)", 
                       (title, amount, category, is_split, today_str))
        conn.commit()
        conn.close()

    return redirect(url_for("home"))

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/export")
def export_csv():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category, amount, is_split, date_recorded FROM expenses ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Expense Title", "Category", "Amount (INR)", "Roommate Split (50%)", "Date Logged"])
    for row in rows:
        split_label = "Yes (Split)" if row[4] == 1 else "Personal"
        writer.writerow([row[0], row[1], row[2], row[3], split_label, row[5]])
        
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=PocketSaaS_Expense_Ledger.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)