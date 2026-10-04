# 🚀 PocketSaaS — Smart Student Financial Engine

> A production-ready, multi-tenant personal finance management & shared ledger application designed specifically for college students and flatmates.

![Live Status](https://img.shields.io/badge/Status-Live%20on%20Render-emerald?style=for-the-badge)
![Tech Stack](https://img.shields.io/badge/Stack-Python%20%7C%20Flask%20%7C%20SQLite%20%7C%20TailwindCSS-indigo?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

🔗 **Live Deployment:** [https://pocketsaas.onrender.com](https://pocketsaas.onrender.com)

---

## 🌟 Key Features

- **🔐 Isolated Multi-User Authentication:** Secure user signup & login powered by `werkzeug.security` (salted PBKDF2 hashing) ensuring data privacy across accounts.
- **⚡ Proportional Unequal & GST Bill Splitter:** Built-in calculator to proportionally distribute restaurant bills, 5%–18% GST rates, and delivery charges between friends.
- **📊 Real-Time Budget Utilization & Health Meter:** Dynamic visual progress tracking with status alerts (Normal, Warning, Overspent) against monthly allowance limits.
- **⏳ Dynamic Daily Safe Spend Algorithm:** Calculates real-time daily safe limits based on remaining allowance and actual days left in the current calendar month.
- **🤝 Granular Flatmate/Roommate Ledger:** Tag specific friend names on shared expenses, track outstanding balances, and mark dues as settled with one click.
- **📅 Multi-Month Historical Filtering:** Seamlessly switch between current and past months to audit historical spending trends.
- **📈 Visual Analytics & CSV Export:** Category-wise donut charts (Chart.js) and one-click full-ledger data export in `.csv` format.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Backend Engine** | Python 3, Flask, Gunicorn (WSGI Server) |
| **Database** | SQLite3 (Parameterized queries preventing SQL Injection) |
| **Frontend & UI** | Tailwind CSS (CDN), Custom CSS 3D Animations, Chart.js |
| **Deployment** | Render Cloud Platform (Automated GitHub CI/CD Pipeline) |

---

## 💻 Local Setup & Installation

Clone and run the application locally on your machine:

```bash
# 1. Clone the repository
git clone [https://github.com/ABHINAV-CREATOR55/pocketsaas.git](https://github.com/ABHINAV-CREATOR55/pocketsaas.git)
cd pocketsaas

# 2. Create and activate a virtual environment (optional but recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the local development server
python app.py