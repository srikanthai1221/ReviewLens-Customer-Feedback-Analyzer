# 🔎 ReviewLens: Customer Feedback Analyzer

Turn hundreds of raw, multilingual customer reviews into tagged, prioritised insights and a weekly report a manager can act on in five minutes.

**Live demo:** https://reviewlens.socialeagle.sbs (password-protected; access on request)

---

## The problem

A restaurant chain or online store receives 200–500 reviews a week from Google, Zomato, Swiggy, Amazon and FoodPanda, in English, Tamil, Tanglish, Hindi, Hinglish and more. Managers read them by hand, urgent complaints (food safety, wrong orders, refunds) get missed for days, and nobody can say with numbers what customers complain about most.

## What it does

- **Upload** a CSV of reviews (`review_id, date, platform, rating, review_text`)
- **Validate:** checks required columns, drops empty and duplicate rows
- **Classify every review** with a LangChain chain that returns a fixed structure:
  `sentiment`, `category`, `urgency`, `language`, `summary`, `suggested_reply`
- **Handle mixed languages:** Tamil, Tanglish, Hindi, Hinglish, Telugu, Kannada, Malayalam, Spanish, German and French reviews are all summarised in English
- **Weekly insights report:** a second chain writes top complaints, top praises and 3 action items
- **Dashboard:** sentiment split, category chart, KPI row, and a **HIGH urgency** filter
- **Export:** enriched table as an Excel-friendly CSV (UTF-8 with BOM, so non-English text displays correctly)

## How it works

```
01 Upload → 02 Validate → 03 Classify (batch) → 04 Aggregate → 05 Report → 06 Show + Export
```

| Stage | Implementation |
|---|---|
| Classify (map) | `ChatPromptTemplate │ ChatOpenAI.with_structured_output(ReviewAnalysis)` |
| Batching | `chain.batch(..., config={"max_concurrency": N}, return_exceptions=True)` |
| Validation & retry | Pydantic `Literal` types enforce allowed values; failed reviews are retried automatically (up to 3 attempts) before being marked `needs_review` |
| Aggregate | pandas computes every count and percentage, so report numbers always match the table |
| Report (reduce) | Second LCEL chain → `WeeklyInsights` Pydantic model (headlines, details, action items). The LLM writes the words; pandas supplies the numbers |

## Output fields

| Field | Allowed values | Why it matters |
|---|---|---|
| `sentiment` | positive, neutral, negative | Overall customer mood at a glance |
| `category` | food_quality, delivery, price, staff, packaging, app | Tells the manager which team should act |
| `urgency` | low, medium, high | High = reply today (health, refund, abuse, wrong order) |
| `language` | Detected, e.g. Tamil, Tanglish, Hinglish | Shows the language mix |
| `summary` | One English sentence | Read 200 lines instead of 200 paragraphs |
| `suggested_reply` | Polite, ready-to-post response | Support team reviews and posts |

### Sample analysed review

```json
{
  "review_id": "R-1002",
  "sentiment": "negative",
  "category": "app",
  "urgency": "high",
  "language": "Tamil",
  "summary": "Customer was promised a refund but has not received it yet.",
  "suggested_reply": "We're sorry your refund hasn't reached you yet. Please DM us your order ID so we can resolve this right away."
}
```

## Tech stack

- **LangChain** (LCEL, `ChatPromptTemplate`, `with_structured_output`, `batch`)
- **Pydantic v2** (typed schemas, `Literal` enums, field validators)
- **OpenAI** (model configurable via `.env`)
- **Streamlit** + **pandas** + **Plotly**
- **Deployment:** Ubuntu VPS, systemd, Nginx reverse proxy (basic auth), Let's Encrypt SSL

## Project structure

```
├── app.py            # Streamlit UI: upload, dashboard, report, filters, export
├── pipeline.py       # validate → batch classify with retry → aggregate → report → export
├── chains.py         # prompts + LCEL chains (classify and report)
├── schemas.py        # Pydantic models: ReviewAnalysis, WeeklyInsights
├── config.py         # settings loaded from .env
├── test_chain.py     # 5-review smoke test
├── requirements.txt
└── data/
    └── food_portal_reviews_multilingual.csv   # 210 sample reviews, 10+ languages
```

## Run locally

```bash
git clone https://github.com/srikanthai1221/ReviewLens-Customer-Feedback-Analyzer.git
cd ReviewLens-Customer-Feedback-Analyzer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
MAX_CONCURRENCY=5
```

Smoke test, then launch:

```bash
python test_chain.py
python -m streamlit run app.py
```

## Acceptance checklist

- [x] Processes a 200+ row CSV (210 reviews) without crashing or timing out
- [x] Every review has all 6 fields; every value is from the allowed list
- [x] Tamil and Tanglish reviews get a correct English summary
- [x] Report counts and percentages are calculated in pandas and match the table exactly
- [x] HIGH urgency filter works; enriched CSV opens correctly in Excel
- [x] API key loaded from `.env`, never hard-coded or committed

## Screenshots

| Dashboard | Weekly report |
|---|---|
| ![Dashboard](screenshots/dashboard.png) | ![Report](screenshots/report.png) |

| HIGH urgency filter | Export in Excel |
|---|---|
| ![High urgency](screenshots/high_urgency.png) | ![Excel](screenshots/excel_export.png) |

## Roadmap (stretch goals)

- [ ] Week-over-week comparison with trend arrows
- [ ] Replies in the same language as the review
- [ ] Automatic weekly report email every Monday

---

Built by **Srikanth Jayaram** as part of the Social Eagle AI Academy Gen AI program (Track 1: LangChain).