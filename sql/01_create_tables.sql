-- ================================================================
-- 01_create_tables.sql
-- Run this in BigQuery Console (replace PROJECT_ID and dataset name
-- if you used different ones) AFTER you've created the dataset.
--
-- Create dataset first via console or:
--   bq --location=US mk -d --description "Telco churn data" churn_analytics
-- ================================================================

-- ----------------------------------------------------------------
-- customers
-- This table is created by the CSV upload (auto-detect schema).
-- The DDL below is only for reference / re-creation. Do NOT run
-- this if you've already uploaded the CSV.
-- ----------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS `churn_analytics.customers` (
--   customerID        STRING,
--   gender            STRING,
--   SeniorCitizen     INT64,
--   Partner           STRING,
--   Dependents        STRING,
--   tenure            INT64,
--   PhoneService      STRING,
--   MultipleLines     STRING,
--   InternetService   STRING,
--   OnlineSecurity    STRING,
--   OnlineBackup      STRING,
--   DeviceProtection  STRING,
--   TechSupport       STRING,
--   StreamingTV       STRING,
--   StreamingMovies   STRING,
--   Contract          STRING,
--   PaperlessBilling  STRING,
--   PaymentMethod     STRING,
--   MonthlyCharges    FLOAT64,
--   TotalCharges      STRING,        -- contains whitespace strings; convert downstream
--   Churn             STRING         -- "Yes" / "No"
-- );

-- ----------------------------------------------------------------
-- predictions: every churn score the app produces is logged here
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `churn_analytics.predictions` (
  prediction_id      STRING        NOT NULL,
  customer_id        STRING        NOT NULL,
  churn_probability  FLOAT64       NOT NULL,
  prediction         STRING        NOT NULL,        -- "Yes" / "No"
  risk_tier          STRING        NOT NULL,        -- "High" / "Medium" / "Low"
  top_factors        STRING,                        -- JSON array as string
  model_version      STRING,
  source             STRING,                        -- "ui" / "api" / "batch" / "scheduled"
  predicted_at       TIMESTAMP     NOT NULL
)
PARTITION BY DATE(predicted_at)
CLUSTER BY customer_id, risk_tier;

-- ----------------------------------------------------------------
-- retention_actions: logged when a CSR takes action on a prediction
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `churn_analytics.retention_actions` (
  action_id        STRING       NOT NULL,
  customer_id      STRING       NOT NULL,
  prediction_id    STRING,
  action_type      STRING       NOT NULL,           -- "call" / "email" / "discount" / "upgrade" / "no_action"
  action_detail    STRING,
  csr_id           STRING,
  outcome          STRING,                          -- "retained" / "churned" / "pending"
  cost_estimate    FLOAT64,
  created_at       TIMESTAMP    NOT NULL,
  outcome_at       TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY customer_id, action_type;

-- ----------------------------------------------------------------
-- daily_metrics: pre-aggregated daily KPIs for fast Looker loads
-- Populated by scheduled query (see 03_daily_aggregations.sql)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `churn_analytics.daily_metrics` (
  metric_date        DATE         NOT NULL,
  total_customers    INT64,
  churned_customers  INT64,
  churn_rate         FLOAT64,
  revenue_at_risk    FLOAT64,
  high_risk_count    INT64,
  medium_risk_count  INT64,
  low_risk_count     INT64,
  actions_taken      INT64,
  retained_count     INT64
)
PARTITION BY metric_date;

-- ----------------------------------------------------------------
-- model_registry: tracks models trained outside Vertex Model Registry
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `churn_analytics.model_registry` (
  model_version    STRING      NOT NULL,
  algorithm        STRING,
  training_date    TIMESTAMP   NOT NULL,
  accuracy         FLOAT64,
  roc_auc          FLOAT64,
  precision_score  FLOAT64,
  recall_score     FLOAT64,
  f1_score         FLOAT64,
  gcs_uri          STRING,
  is_active        BOOL        DEFAULT FALSE,
  notes            STRING
);
