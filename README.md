# AI-Powered Customer Churn Prediction & Retention Analytics Platform

**Course**: 23CSE363 Cloud Computing — Assignment / Mini-Project
**Institution**: Amrita School of Engineering, Amritapuri
**Team size**: 4 members
**SDGs addressed**: SDG 8 (Decent Work & Economic Growth), SDG 9 (Industry, Innovation & Infrastructure)

A production-grade, multi-service GCP platform that predicts customer churn,
explains why each customer is at risk, recommends retention actions, and
publishes executive analytics. Built end-to-end on Google Cloud free tier.

---

## Architecture

```
                 ┌──────────────────────────────────────────────┐
                 │              END USERS                       │
                 │   CSR · Manager · Analyst · API consumer     │
                 └────────────┬─────────────────────────────────┘
                              │ HTTPS
                              ▼
                 ┌──────────────────────────┐         ┌────────────────────┐
                 │  Cloud Run               │ ───────▶│ Vertex AI (opt.)   │
                 │  Flask + Gunicorn        │         │ Endpoint / Model   │
                 │  - Score UI              │         └────────────────────┘
                 │  - What-If simulator     │
                 │  - Batch upload          │ ◀───────┐
                 │  - Admin + Gemini email  │         │
                 │  - REST API + Swagger    │         │
                 └────────┬─────────────────┘         │
                          │                            │
                ┌─────────┼─────────┐                  │
                ▼         ▼         ▼                  │
        ┌────────────┐ ┌────────┐ ┌──────────┐   ┌─────┴─────────┐
        │ BigQuery   │ │  GCS   │ │ Gemini   │   │ Cloud Run Job │
        │ - customers│ │ models │ │ retention│   │ bulk scorer   │
        │ - preds    │ │ uploads│ │ emails   │   │ (nightly)     │
        │ - actions  │ └────────┘ └──────────┘   └─────┬─────────┘
        │ - metrics  │                                  │
        │ - registry │ ◀────────────────────────────────┘
        └─────┬──────┘                                  ▲
              │                                          │
              ▼                                  ┌───────┴────────┐
        ┌────────────────────┐                   │ Cloud Scheduler│
        │ Looker Studio      │                   │ 02:00 daily    │
        │ Executive Dashboard│                   └────────────────┘
        └────────────────────┘
```

**GCP services used**: Cloud Run · Cloud Run Jobs · BigQuery · Cloud Storage ·
Vertex AI · Gemini API · Cloud Scheduler · Cloud Build · Cloud Logging ·
Cloud Monitoring · Looker Studio.

---

## Project structure

```
churn-platform/
├── app/                    # Flask web app
│   ├── app.py              # Application factory + UI routes
│   ├── config.py           # Env-based config
│   ├── predictor.py        # ML inference + factor attribution
│   ├── retention.py        # Rule-based recommendation engine
│   ├── bigquery_client.py  # All BQ reads/writes
│   ├── gemini_client.py    # Personalised retention email generation
│   ├── auth.py             # Admin basic-auth gate
│   ├── api/routes.py       # REST API (Swagger documented)
│   ├── templates/          # Server-rendered HTML (Tailwind CDN)
│   └── static/             # CSS + JS
├── notebooks/
│   └── train_churn_model.ipynb   # Vertex AI Workbench training pipeline
├── jobs/
│   ├── bulk_score_job.py   # Cloud Run Job: nightly re-score all customers
│   └── Dockerfile.job
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_create_views.sql
│   └── 03_daily_aggregations.sql
├── deploy/
│   ├── deploy_app.sh
│   ├── deploy_job.sh
│   └── schedule_jobs.sh
├── monitoring/
│   └── alerts.yaml         # Cloud Monitoring policies
├── tests/
│   └── test_predictor.py   # pytest smoke tests
├── data/                   # Place IBM Telco CSV here (gitignored)
├── model_artifacts/        # model.joblib + features_meta.json (gitignored)
├── .env.example
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Setup — step by step

### Prerequisites
- A GCP account with $300 free trial credits
- Python 3.11+ locally
- `gcloud` CLI installed and authenticated (`gcloud auth login`)

### 1. Create GCP project + enable APIs

```bash
PROJECT_ID="churn-platform-$(whoami)-$(date +%s | tail -c 5)"
gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID

gcloud services enable \
    run.googleapis.com bigquery.googleapis.com storage.googleapis.com \
    aiplatform.googleapis.com cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com generativelanguage.googleapis.com \
    monitoring.googleapis.com logging.googleapis.com
```

Link your billing account in the Cloud Console.

### 2. Create dataset and buckets

```bash
bq --location=US mk -d --description "Telco churn data" telco_churn

gsutil mb -l US gs://${PROJECT_ID}-models
gsutil mb -l US gs://${PROJECT_ID}-uploads
```

### 3. Upload the IBM Telco Customer Churn dataset

Download `WA_Fn-UseC_-Telco-Customer-Churn.csv` from Kaggle
(https://www.kaggle.com/datasets/blastchar/telco-customer-churn) into `data/`.

Then load it into BigQuery (auto-detect schema):

```bash
bq load --autodetect --source_format=CSV \
    telco_churn.customers data/WA_Fn-UseC_-Telco-Customer-Churn.csv
```

### 4. Create tables and views

Open the BigQuery Console, paste and run:
1. `sql/01_create_tables.sql` (creates predictions, retention_actions, daily_metrics, model_registry)
2. `sql/02_create_views.sql` (creates the views Looker Studio reads from)
3. Schedule `sql/03_daily_aggregations.sql` via BigQuery → Scheduled Queries (daily 03:00)

### 5. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in: GCP_PROJECT_ID, GCS_MODEL_BUCKET, GEMINI_API_KEY,
# FLASK_SECRET_KEY, ADMIN_PASSWORD
```

Get a Gemini API key at https://aistudio.google.com/apikey.

### 6. Train the model

Open **Vertex AI Workbench** in the GCP Console → New Notebook → Python 3.
Upload `notebooks/train_churn_model.ipynb`, set the config in cell 1, and
"Run all". The notebook will:

- Load data from BigQuery
- Train XGBoost with SHAP explainability
- Save `model.joblib` and `features_meta.json`
- Upload them to GCS
- Register the model in the BigQuery `model_registry`

Download both artifacts to your local `model_artifacts/` folder.

### 7. Test locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest tests/                          # All 6 tests should pass
python -m app.app                      # http://localhost:8080
```

### 8. Deploy to Cloud Run

```bash
bash deploy/deploy_app.sh              # builds + deploys the web app
bash deploy/deploy_job.sh              # builds + registers the scheduled job
bash deploy/schedule_jobs.sh           # sets up nightly 02:00 IST schedule
```

### 9. Build the Looker Studio dashboard

1. Open https://lookerstudio.google.com → Create → Report
2. Add data source → BigQuery → `<project>.telco_churn.customers_with_predictions`
3. Add second data source: `segment_churn_rates`
4. Add third: `daily_metrics`
5. Build these tiles:
   - **Scorecards**: total customers, churn rate, revenue at risk, high-risk count
   - **Bar chart**: churn rate by Contract type (segment_churn_rates)
   - **Bar chart**: churn rate by InternetService
   - **Pie chart**: risk_tier distribution (customers_with_predictions)
   - **Table**: top 20 at-risk customers
   - **Geo map**: customers by state, colour = churn probability
   - **Time series**: daily_metrics over time
6. (Optional) Enable **Gemini in Looker Studio** for natural-language Q&A.

### 10. Configure monitoring

```bash
gcloud alpha monitoring policies create --policy-from-file=monitoring/alerts.yaml
```

---

## Team contribution split (4 members)

| Member | Role | Owns |
|---|---|---|
| **Member 1** | ML / Data Engineering | `notebooks/train_churn_model.ipynb`, `app/predictor.py`, BigQuery schema (`sql/`), model versioning |
| **Member 2** | Backend / API | `app/app.py`, `app/api/routes.py`, `app/bigquery_client.py`, `app/auth.py`, Swagger docs |
| **Member 3** | Frontend / UX | `app/templates/`, `app/static/`, `app/retention.py`, `app/gemini_client.py` |
| **Member 4** | Analytics / DevOps | Looker Studio dashboard, `deploy/`, `jobs/`, `monitoring/`, Cloud Scheduler, README |

---

## Cost estimate (free tier safe)

| Service | Approx. cost |
|---|---|
| Cloud Run web app (min 0 instances) | < $1 / month |
| BigQuery (< 1 TB queries) | $0 (free tier) |
| Cloud Storage (< 5 GB) | $0 (free tier) |
| Vertex AI Workbench (e2-standard-4) | ~$0.20 / hour while running |
| Gemini API (gemini-1.5-flash) | Free tier: 15 RPM, 1500 / day |
| Cloud Scheduler | $0 (free tier: 3 jobs) |
| **Vertex AI Endpoint (optional)** | **~$0.05 / hour while deployed** |

Recommendation: skip the Vertex Endpoint for the demo. Bundle the model
into the Cloud Run image (`USE_VERTEX_ENDPOINT=false`). Total cost for the
project demo runs comfortably under $5.

---

## API quick reference

Once deployed, see the full Swagger UI at `<service-url>/apidocs/`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET  | `/api/health` | Health check + model version |
| POST | `/api/predict` | Score a single customer |
| POST | `/api/batch-predict` | Upload CSV → bulk predictions |
| GET  | `/api/customers/<id>` | Profile + prediction history |
| GET  | `/api/insights/overall` | Overall stats |
| GET  | `/api/insights/segments` | Segment-level churn rates |
| GET  | `/api/insights/top-risk` | Top at-risk customers |
| POST | `/api/retention-action` | Log a retention action |
| POST | `/api/generate-email` | Gemini-powered retention email |
| POST | `/api/whatif` | Counterfactual simulation |

---

## Demo script (suggested 5-minute viva flow)

1. **Open Cloud Run URL** → home page
2. **Pick an existing customer** → click "Score Customer" → show gauge + factors + recommendations
3. **Click "Mark as taken"** → action logged to BigQuery (open BQ in another tab and `SELECT * FROM retention_actions LIMIT 5`)
4. **What-If**: change Contract from Month-to-month → Two year → show probability drop
5. **Batch**: upload a 100-row CSV → show table of predictions
6. **Admin** (basic-auth) → click "Generate retention email" → show Gemini output
7. **API Docs** (`/apidocs/`) → try the `/api/predict` endpoint live
8. **Looker Studio** dashboard → walk through revenue-at-risk, segment rates, geo map
9. **Cloud Scheduler** → show the nightly bulk-scorer job + its last execution log

---

## License

Built for educational use. Dataset © IBM Sample Datasets.
