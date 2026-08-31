# AI-Powered Customer Churn Prediction & Retention Analytics Platform

> A cloud-native platform that predicts customer churn, explains customer risk, recommends retention actions, and provides executive analytics.

**Course:** 23CSE363 — Cloud Computing
**Institution:** Amrita School of Engineering, Amritapuri
**Team Size:** 4 Members
**SDGs Addressed:** SDG 8 (Decent Work & Economic Growth), SDG 9 (Industry, Innovation & Infrastructure)

---

## Project Overview

The **AI-Powered Customer Churn Prediction & Retention Analytics Platform** is a multi-service cloud application designed to help organizations identify customers who are likely to churn.

The platform provides:

* Customer churn prediction
* Risk-factor attribution and explainability
* Personalized retention recommendations
* What-If simulation for customer scenarios
* Batch customer scoring
* AI-generated retention emails
* Executive analytics dashboards
* REST API with Swagger documentation
* Automated deployment and scheduled bulk scoring

The project is built using Google Cloud Platform services and is designed to run efficiently within free-tier or low-cost limits.

---

# Architecture

```text
                 ┌──────────────────────────────────────────────┐
                 │              END USERS                       │
                 │   CSR · Manager · Analyst · API Consumer     │
                 └────────────┬─────────────────────────────────┘
                              │ HTTPS
                              ▼
                 ┌──────────────────────────┐         ┌────────────────────┐
                 │       Cloud Run          │ ───────▶│  Vertex AI (Opt.)  │
                 │   Flask + Gunicorn       │         │ Endpoint / Model   │
                 │                          │         └────────────────────┘
                 │  • Score UI              │
                 │  • What-If Simulator     │
                 │  • Batch Upload          │
                 │  • Admin + Gemini Email  │
                 │  • REST API + Swagger    │
                 └────────┬─────────────────┘
                          │
                ┌─────────┼─────────┐
                ▼         ▼         ▼
        ┌────────────┐ ┌────────┐ ┌──────────┐
        │ BigQuery   │ │  GCS   │ │ Gemini   │
        │            │ │        │ │   API    │
        │ Customers  │ │ Models │ │Retention │
        │ Predictions│ │Uploads │ │ Emails   │
        │ Actions    │ └────────┘ └──────────┘
        │ Metrics    │
        │ Registry   │
        └─────┬──────┘
              │
              ▼
        ┌────────────────────┐
        │   Looker Studio    │
        │ Executive Dashboard│
        └────────────────────┘


        ┌────────────────────┐
        │  Cloud Scheduler   │
        │   Daily Schedule   │
        └─────────┬──────────┘
                  │
                  ▼
        ┌────────────────────┐
        │   Cloud Run Job    │
        │   Bulk Scoring     │
        └─────────┬──────────┘
                  │
                  └──────────────▶ BigQuery
```

---

## GCP Services Used

* Cloud Run
* Cloud Run Jobs
* BigQuery
* Cloud Storage
* Vertex AI
* Gemini API
* Cloud Scheduler
* Cloud Build
* Cloud Logging
* Cloud Monitoring
* Looker Studio

---

# Key Features

### Churn Prediction

Predicts the probability of a customer leaving the service using a machine learning model.

### Explainable AI

Identifies the major factors contributing to a customer's churn risk.

### Retention Recommendations

Provides rule-based recommendations to help retain high-risk customers.

### What-If Simulator

Allows users to modify customer attributes and observe how churn probability changes.

### Batch Prediction

Upload a CSV file to generate churn predictions for multiple customers.

### AI-Powered Retention Emails

Uses Gemini to generate personalized customer retention emails.

### Executive Analytics

Provides business insights through Looker Studio dashboards.

### REST API

Offers programmatic access to prediction and analytics features with Swagger documentation.

### Automated Bulk Scoring

Cloud Scheduler triggers a Cloud Run Job for scheduled customer re-scoring.

---

# Project Structure

```text
churn-platform/
│
├── app/
│   ├── app.py
│   ├── config.py
│   ├── predictor.py
│   ├── retention.py
│   ├── bigquery_client.py
│   ├── gemini_client.py
│   ├── auth.py
│   │
│   ├── api/
│   │   └── routes.py
│   │
│   ├── templates/
│   └── static/
│
├── notebooks/
│   └── train_churn_model.ipynb
│
├── jobs/
│   ├── bulk_score_job.py
│   └── Dockerfile.job
│
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_create_views.sql
│   └── 03_daily_aggregations.sql
│
├── deploy/
│   ├── deploy_app.sh
│   ├── deploy_job.sh
│   └── schedule_jobs.sh
│
├── monitoring/
│   └── alerts.yaml
│
├── tests/
│   └── test_predictor.py
│
├── data/
├── model_artifacts/
│
├── .env.example
├── Dockerfile
├── requirements.txt
└── README.md
```

---

# Setup Guide

## Prerequisites

Before starting, ensure you have:

* A Google Cloud Platform account
* Python 3.11+
* Google Cloud CLI installed
* Authenticated GCP account

```bash
gcloud auth login
```

---

## 1. Create GCP Project and Enable APIs

```bash
PROJECT_ID="churn-platform-$(whoami)-$(date +%s | tail -c 5)"

gcloud projects create $PROJECT_ID

gcloud config set project $PROJECT_ID
```

Enable the required APIs:

```bash
gcloud services enable \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com \
    generativelanguage.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com
```

Link your billing account through the Google Cloud Console.

---

## 2. Create BigQuery Dataset and Cloud Storage Buckets

Create the BigQuery dataset:

```bash
bq --location=US mk -d \
--description "Telco churn data" \
telco_churn
```

Create Cloud Storage buckets:

```bash
gsutil mb -l US gs://${PROJECT_ID}-models
gsutil mb -l US gs://${PROJECT_ID}-uploads
```

---

## 3. Upload the Dataset

Download the IBM Telco Customer Churn dataset and place it inside the `data/` directory.

Dataset: Kaggle IBM Telco Customer Churn Dataset

Expected file:

```text
WA_Fn-UseC_-Telco-Customer-Churn.csv
```

Load the dataset into BigQuery:

```bash
bq load \
--autodetect \
--source_format=CSV \
telco_churn.customers \
data/WA_Fn-UseC_-Telco-Customer-Churn.csv
```

---

## 4. Create Tables and Views

Run the SQL files in the following order:

```text
sql/01_create_tables.sql
```

Creates:

* `predictions`
* `retention_actions`
* `daily_metrics`
* `model_registry`

Then run:

```text
sql/02_create_views.sql
```

These views are used by Looker Studio.

Schedule the following using BigQuery Scheduled Queries:

```text
sql/03_daily_aggregations.sql
```

Recommended schedule:

```text
Daily at 03:00
```

---

# Environment Configuration

Create your environment file:

```bash
cp .env.example .env
```

Configure the following variables:

```text
GCP_PROJECT_ID=
GCS_MODEL_BUCKET=
GEMINI_API_KEY=
FLASK_SECRET_KEY=
ADMIN_PASSWORD=
```

---

## Gemini API Key

Generate a Gemini API key using Google AI Studio and add it to your `.env` file.

---

# Train the Machine Learning Model

Open Vertex AI Workbench and create a Python notebook environment.

Upload:

```text
notebooks/train_churn_model.ipynb
```

Configure the required values in the first cell and run all cells.

The training pipeline will:

1. Load customer data from BigQuery
2. Train an XGBoost model
3. Generate explainability information
4. Save the trained model
5. Upload model artifacts to Cloud Storage
6. Register the model in BigQuery

Generated artifacts:

```text
model.joblib
features_meta.json
```

These artifacts are stored in:

```text
model_artifacts/
```

---

# Run Locally

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest tests/
```

Start the application:

```bash
python -m app.app
```

The application will be available at:

```text
http://localhost:8080
```

---

# Deploy to Cloud Run

Deploy the web application:

```bash
bash deploy/deploy_app.sh
```

Deploy the bulk scoring job:

```bash
bash deploy/deploy_job.sh
```

Configure scheduled execution:

```bash
bash deploy/schedule_jobs.sh
```

---

# Looker Studio Dashboard

Add the following BigQuery data sources:

```text
<project>.telco_churn.customers_with_predictions
```

```text
segment_churn_rates
```

```text
daily_metrics
```

Recommended dashboard components:

### Scorecards

* Total Customers
* Churn Rate
* Revenue at Risk
* High-Risk Customer Count

### Charts

* Churn Rate by Contract Type
* Churn Rate by Internet Service
* Risk Tier Distribution
* Top At-Risk Customers
* Customer Geographic Distribution
* Daily Churn Metrics

---

# Monitoring

Create monitoring policies using:

```bash
gcloud alpha monitoring policies create \
--policy-from-file=monitoring/alerts.yaml
```

---

# Team Contribution

| Member   | Role                  | Primary Responsibilities                                              |
| -------- | --------------------- | --------------------------------------------------------------------- |
| Member 1 | ML / Data Engineering | Model training, predictor, BigQuery schema, model versioning          |
| Member 2 | Backend / API         | Flask application, REST API, BigQuery client, authentication, Swagger |
| Member 3 | Frontend / UX         | UI templates, static assets, retention engine, Gemini integration     |
| Member 4 | Analytics / DevOps    | Dashboard, deployment, Cloud Run Jobs, monitoring, scheduling, README |

---

# Estimated Cost

| Service             | Estimated Cost                         |
| ------------------- | -------------------------------------- |
| Cloud Run Web App   | < $1 / month                           |
| BigQuery            | Free tier for eligible usage           |
| Cloud Storage       | Free tier for small storage usage      |
| Vertex AI Workbench | Charged while running                  |
| Gemini API          | Subject to applicable free-tier limits |
| Cloud Scheduler     | Free tier available for limited jobs   |
| Vertex AI Endpoint  | Additional cost while deployed         |

**Recommendation:** For demonstrations, bundle the model directly into the Cloud Run application instead of keeping a Vertex AI Endpoint continuously deployed.

---

# API Reference

After deployment, access the Swagger documentation at:

```text
<service-url>/apidocs/
```

## Available Endpoints

| Method | Endpoint                 | Description                             |
| ------ | ------------------------ | --------------------------------------- |
| `GET`  | `/api/health`            | Health check and model version          |
| `POST` | `/api/predict`           | Predict churn for a single customer     |
| `POST` | `/api/batch-predict`     | Upload CSV for batch predictions        |
| `GET`  | `/api/customers/<id>`    | Customer profile and prediction history |
| `GET`  | `/api/insights/overall`  | Overall churn statistics                |
| `GET`  | `/api/insights/segments` | Segment-level churn rates               |
| `GET`  | `/api/insights/top-risk` | Top at-risk customers                   |
| `POST` | `/api/retention-action`  | Log a retention action                  |
| `POST` | `/api/generate-email`    | Generate a retention email              |
| `POST` | `/api/whatif`            | Run counterfactual simulation           |

---

# Suggested Demo Flow

1. Open the deployed Cloud Run application.
2. Select an existing customer and score the customer.
3. Demonstrate churn probability, risk factors, and recommendations.
4. Log a retention action and verify it in BigQuery.
5. Perform a What-If analysis by changing the customer's contract.
6. Upload a CSV file for batch prediction.
7. Generate a personalized retention email using Gemini.
8. Demonstrate the REST API through Swagger.
9. Walk through the Looker Studio dashboard.
10. Show the Cloud Scheduler configuration and Cloud Run Job execution logs.

---

# Technology Stack

### Backend

* Python
* Flask
* Gunicorn

### Machine Learning

* XGBoost
* SHAP

### Cloud Platform

* Google Cloud Platform

### Data and Storage

* BigQuery
* Google Cloud Storage

### AI

* Vertex AI
* Gemini API

### Deployment

* Cloud Run
* Cloud Run Jobs
* Cloud Build

### Analytics

* Looker Studio

### Monitoring

* Cloud Logging
* Cloud Monitoring

---

# SDG Contribution

## SDG 8 — Decent Work and Economic Growth

The platform helps businesses improve customer retention, reduce revenue loss, and support sustainable business growth through data-driven decision-making.

## SDG 9 — Industry, Innovation and Infrastructure

The project demonstrates the use of cloud infrastructure, machine learning, AI, and analytics to build scalable and innovative digital solutions.

---

# Future Improvements

* Real-time streaming predictions
* Advanced customer segmentation
* Automated retention campaign execution
* Additional machine learning models
* Role-based authentication
* Advanced model monitoring
* Automated model retraining
* CRM platform integration

---

# License

This project was developed as an academic mini-project for the **23CSE363 Cloud Computing** course.
