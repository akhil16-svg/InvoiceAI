# 🎯 Invoice Intelligence Platform

[![CI Pipeline](https://github.com/akhil16-svg/InvoiceAI/actions/workflows/ci.yml/badge.svg)](https://github.com/akhil16-svg/InvoiceAI/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.51-FF4B4B.svg)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)

An AI-powered invoice processing platform that uses OCR to extract data from invoices, detect fraud with 8+ intelligent algorithms, and provide real-time financial analytics — all through a modern dark-themed web interface.

Benchmarked and validated against **500+ real-world invoices** across retail, healthcare, logistics, and professional services using [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), Google's open-source OCR engine.

---

## 🔗 Live Demo

> **[Coming soon — deploying to Streamlit Community Cloud]**
>
> Try the demo with: `demo@invoiceai.com` / `Demo1234`  
> Or register your own account — all data is isolated per user.

---

## 📸 Screenshots

### Home Page
![Home Page](screenshots/home.png)

### Why This Tool — Feature Cards
![Features](screenshots/features.png)

### Secure Authentication
![Login](screenshots/login.png)

### Real-time Analytics Dashboard
![Analytics](screenshots/analytics.png)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **💬 Ask AI (RAG)** | Chat with your own invoices: BM25 retrieval over your documents + Gemini-generated, cited answers |
| **✨ AI Extraction** | Gemini vision + OCR structured extraction, with regex fallback when no API key is set |
| **⚡ OCR Engine** | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (Google's open-source engine) with multi-format support |
| **🛡️ Fraud Detection** | 8+ algorithms: duplicate detection, math verification, future date flagging, anomaly scoring |
| **📊 Real-time Analytics** | Interactive Plotly dashboards for spending trends, vendor analysis, and financial patterns |
| **💾 PostgreSQL Storage** | Per-user data isolation with secure, persistent database storage |
| **🔐 Authentication** | User registration, login, password change, brute-force protection with account locking |
| **📤 Bulk Upload** | Upload 100+ invoices at once with automatic save-to-database |
| **📥 Export** | Download data as CSV or JSON for external accounting workflows |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit, HTML/CSS (glassmorphism dark theme), Plotly.js |
| **Backend** | Python 3.11 |
| **AI / RAG** | Gemini API (`gemini-2.5-flash`), BM25 retrieval (rank-bm25) over per-user invoice corpus |
| **OCR Engine** | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) via pytesseract |
| **Database** | PostgreSQL 15 (Docker) |
| **Auth** | PBKDF2-SHA256 password hashing, session management, brute-force lockout |
| **Infrastructure** | Docker, Docker Compose |
| **CI/CD** | GitHub Actions (syntax check + unit tests + Docker build) |
| **Testing** | pytest + pytest-cov |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Tesseract OCR (`brew install tesseract` on macOS)

### 1. Clone and setup
```bash
git clone https://github.com/akhil16-svg/InvoiceAI.git
cd InvoiceAI
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL
```bash
docker-compose up -d
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY to enable Gemini AI extraction + Ask AI
# The app works without it: OCR falls back to the regex parser,
# Ask AI returns retrieval-only results.
```

### 4. Run the app
```bash
streamlit run main.py
```

The app will be available at `http://localhost:8502`

---

## 🐳 Docker (Full Stack)

Build and run the entire application in Docker:

```bash
docker-compose up -d
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v --cov=utils
```

Tests cover invoice field extraction (number, date, total, currency, tax) and all 6 fraud detection rules. No database or API key required — the test suite uses the regex parser path only.

---

## 🔄 CI/CD Pipeline

This project uses **GitHub Actions** for continuous integration:

```
Push to main → Syntax Check → Import Validation → Unit Tests (pytest) → Docker Build ✅
```

The pipeline runs automatically on every push and pull request to `main`.

---

## 🤖 How the AI Works

### OCR — Tesseract
Invoice images are processed by [Tesseract](https://github.com/tesseract-ocr/tesseract), Google's open-source OCR engine, which extracts raw text from the image. A custom regex parser then structures that text into typed fields (vendor, date, total, line items, etc.).

### AI Extraction (optional, with `GOOGLE_API_KEY`)
When a Google API key is set, the Upload page sends the invoice image **and** the Tesseract OCR text to Gemini with a strict JSON-schema prompt. This handles messy receipts and unusual layouts far more robustly than regex alone. The regex parser fills any fields Gemini returns as null and remains the complete offline fallback.

### Ask AI — RAG Pipeline
```
question ──► BM25 retrieval over your invoice corpus (rank-bm25, fully local)
                 │  top-k invoices + portfolio aggregate stats
                 ▼
             Gemini (gemini-2.5-flash) ──► streamed answer with [INV-123 / Vendor] citations
```

The corpus is rebuilt from PostgreSQL on demand and is **isolated per user** — your questions are only answered from your own documents. No external vector database is needed at this scale; retrieval stays local and only the top-matching invoice summaries are sent to the API.

---

## 📁 Project Structure

```
InvoiceAI/
├── main.py                    # Home page & app entry point
├── pages/
│   ├── 1_📤_Upload.py        # Invoice upload & OCR/AI processing
│   ├── 2_🔍_Fraud_Detection.py  # AI fraud detection center
│   ├── 3_📊_Analytics.py     # Financial analytics dashboard
│   ├── 4_💾_Database.py      # Invoice database & export
│   └── 5_💬_Ask_AI.py        # RAG chat over your own invoices
├── tests/
│   └── test_invoice_parser.py # Unit tests (parser + fraud detection)
├── utils/
│   ├── __init__.py            # Package exports
│   ├── ai_engine.py           # Gemini extraction + grounded Q&A
│   ├── rag.py                 # BM25 retrieval over per-user invoices
│   ├── ui.py                  # Shared theme + navigation
│   ├── auth.py                # Authentication system
│   ├── database.py            # PostgreSQL/JSON database layer
│   ├── invoice_parser.py      # OCR text → structured data (regex fallback)
│   ├── ocr_engine.py          # Tesseract OCR wrapper
│   ├── fraud_detection.py     # Fraud detection algorithms
│   └── analytics.py           # Analytics computations
├── .streamlit/config.toml     # Dark theme + server config
├── Dockerfile                 # Production container
├── docker-compose.yml         # PostgreSQL + app orchestration
├── requirements.txt           # Python dependencies
├── .github/workflows/ci.yml   # GitHub Actions CI pipeline
└── .gitignore
```

---

## 🔐 Security

- Passwords hashed with **PBKDF2-SHA256** (100,000 iterations + random salt)
- **Brute-force protection**: account locks after 5 failed attempts (15-minute cooldown)
- **Per-user data isolation** in PostgreSQL — users only see their own invoices
- Environment variables for all secrets — `.env` is excluded from version control
- PostgreSQL bound to `127.0.0.1` — not reachable from the network

---

## 📄 License

This project is for educational and portfolio purposes.
