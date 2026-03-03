# SirHENRY

A local-first financial platform for HENRYs (High Earners, Not Rich Yet). Connects to your bank accounts via Plaid, imports historical data from CSVs, and uses AI to help with budgeting, wealth planning, tax optimization, and financial decision-making. All data stays local — your finances, your control.

## Architecture

```
data/imports/       ← Drop CSV and PDF files here
     ↓
pipeline/           ← Python ingestion + AI analysis (pdfplumber, pandas, anthropic)
     ↓
data/db/financials.db  ← SQLite (local, secure)
     ↓
api/                ← FastAPI REST backend (port 8000)
     ↓
frontend/           ← Next.js TypeScript dashboard (port 3000)
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Node.js 20+
- An [Anthropic API key](https://console.anthropic.com/)

### 2. Python Environment

```powershell
cd "c:\ServerData\SirHENRY"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure Environment

```powershell
Copy-Item .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 4. Initialize Database

```powershell
python -m pipeline.db.schema
```

### 5. Start the API

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Start the Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Importing Data

### Credit Card Statements (CSV)

Drop CSV files into `data/imports/credit-cards/`. Supported formats:
- Chase, Amex, Capital One, Citi, Bank of America (auto-detected by column headers)

Via the Import page in the dashboard, or CLI:
```powershell
python -m pipeline.importers.credit_card --file "data/imports/credit-cards/chase_2025_01.csv"
```

### Tax Documents (PDF)

Drop W-2, 1099-NEC, 1099-DIV, 1099-B PDFs into `data/imports/tax-documents/`:
```powershell
python -m pipeline.importers.tax_doc --file "data/imports/tax-documents/w2_accenture_2025.pdf"
```

### Investment Statements (PDF/CSV)

Drop brokerage statements into `data/imports/investments/`:
```powershell
python -m pipeline.importers.investment --file "data/imports/investments/fidelity_2025_q4.pdf"
```

---

## Income Sources Tracked

| Source | Form | Notes |
|--------|------|-------|
| Accenture salary | W-2 (multi-state) | State day-tracking for credit claims |
| Wife's board income | 1099-NEC | S-Corp election analysis, Schedule C expenses |
| Investment income | 1099-DIV, 1099-B, 1099-INT | Long/short-term capital gains, NIIT monitoring |

## Tax Strategies Tracked

- Multi-state W-2 income allocation and credit optimization
- S-Corp election opportunity for board income (SE tax savings)
- Retirement contribution headroom (401k, backdoor Roth, HSA)
- Capital gains harvesting / tax-loss harvesting
- SALT deduction tracking
- QBI deduction (Section 199A)
- Net Investment Income Tax (NIIT) threshold monitoring
- Additional Medicare Tax (0.9%) threshold monitoring
- Business expense categorization (Schedule C)

---

## Project Structure

```
├── data/
│   ├── imports/
│   │   ├── credit-cards/
│   │   ├── tax-documents/
│   │   └── investments/
│   ├── db/
│   │   └── financials.db
│   └── processed/
├── pipeline/
│   ├── db/             schema.py, models.py
│   ├── parsers/        csv_parser.py, pdf_parser.py
│   ├── importers/      credit_card.py, tax_doc.py, investment.py
│   └── ai/             categorizer.py, tax_analyzer.py, report_gen.py
├── api/
│   ├── main.py
│   ├── database.py
│   ├── models/         schemas.py
│   └── routes/         transactions, documents, reports, tax, import
├── frontend/
│   └── src/app/
│       ├── page.tsx            Dashboard
│       ├── transactions/
│       ├── statements/
│       ├── tax/
│       └── import/
├── .env                        (gitignored)
├── .env.example
└── requirements.txt
```

## Security Notes

- `.env` is never committed. It contains your Anthropic API key.
- All data stays local — SQLite file in `data/db/`.
- The API only binds to `127.0.0.1` by default (not accessible from network).
- The frontend communicates only with the local API.
