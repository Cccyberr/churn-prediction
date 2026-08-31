-- ================================================================
-- 02_create_views.sql
-- Reusable views that Looker Studio connects to.
-- Run AFTER 01_create_tables.sql and AFTER the customers CSV is loaded.
-- ================================================================

-- ----------------------------------------------------------------
-- customers_clean: clean view with TotalCharges as numeric,
-- Churn as 0/1, and a synthetic state column for the geo heatmap.
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW `churn_analytics.telco_customers_clean` AS
SELECT
  customerID,
  gender,
  SeniorCitizen,
  Partner,
  Dependents,
  tenure,
  CASE
    WHEN tenure < 12 THEN '0-12 months'
    WHEN tenure < 24 THEN '12-24 months'
    WHEN tenure < 48 THEN '24-48 months'
    ELSE '48+ months'
  END AS tenure_bucket,
  PhoneService,
  MultipleLines,
  InternetService,
  OnlineSecurity,
  OnlineBackup,
  DeviceProtection,
  TechSupport,
  StreamingTV,
  StreamingMovies,
  Contract,
  PaperlessBilling,
  PaymentMethod,
  MonthlyCharges,
  SAFE_CAST(NULLIF(TRIM(TotalCharges), '') AS FLOAT64) AS TotalCharges,
  Churn,
  IF(Churn = TRUE, 1, 0) AS churn_flag,
  -- Synthetic state for geo heatmap (deterministic from customerID hash)
  ['California','Texas','Florida','New York','Illinois',
   'Pennsylvania','Ohio','Georgia','North Carolina','Michigan']
    [OFFSET(MOD(ABS(FARM_FINGERPRINT(customerID)), 10))] AS state
FROM `churn_analytics.telco_customers`;

-- ----------------------------------------------------------------
-- latest_predictions: most recent prediction per customer
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW `churn_analytics.latest_predictions` AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY predicted_at DESC) AS rn
  FROM `churn_analytics.predictions`
)
SELECT
  prediction_id,
  customer_id,
  churn_probability,
  prediction,
  risk_tier,
  top_factors,
  model_version,
  source,
  predicted_at
FROM ranked
WHERE rn = 1;

-- ----------------------------------------------------------------
-- customers_with_predictions: customers joined with their latest score
-- Primary view used by Looker Studio.
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW `churn_analytics.telco_customers_with_predictions` AS
SELECT
  c.*,
  p.churn_probability,
  p.risk_tier,
  p.top_factors,
  p.predicted_at,
  c.MonthlyCharges * 12 AS annual_revenue,
  CASE WHEN p.risk_tier = 'High' THEN c.MonthlyCharges * 12 ELSE 0 END AS revenue_at_risk
FROM `churn_analytics.telco_customers_clean` c
LEFT JOIN `churn_analytics.latest_predictions` p
  ON c.customerID = p.customer_id;

-- ----------------------------------------------------------------
-- segment_churn_rates: churn by segment for dashboard tiles
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW `churn_analytics.segment_churn_rates` AS
SELECT
  'Contract' AS segment_type, Contract AS segment_value,
  COUNT(*) AS total_customers,
  SUM(churn_flag) AS churned,
  SAFE_DIVIDE(SUM(churn_flag), COUNT(*)) AS churn_rate,
  SUM(MonthlyCharges * 12) AS annual_revenue
FROM `churn_analytics.telco_customers_clean`
GROUP BY Contract
UNION ALL
SELECT
  'InternetService', InternetService,
  COUNT(*), SUM(churn_flag), SAFE_DIVIDE(SUM(churn_flag), COUNT(*)),
  SUM(MonthlyCharges * 12)
FROM `churn_analytics.telco_customers_clean`
GROUP BY InternetService
UNION ALL
SELECT
  'PaymentMethod', PaymentMethod,
  COUNT(*), SUM(churn_flag), SAFE_DIVIDE(SUM(churn_flag), COUNT(*)),
  SUM(MonthlyCharges * 12)
FROM `churn_analytics.telco_customers_clean`
GROUP BY PaymentMethod
UNION ALL
SELECT
  'TenureBucket', tenure_bucket,
  COUNT(*), SUM(churn_flag), SAFE_DIVIDE(SUM(churn_flag), COUNT(*)),
  SUM(MonthlyCharges * 12)
FROM `churn_analytics.telco_customers_clean`
GROUP BY tenure_bucket;

-- ----------------------------------------------------------------
-- retention_funnel: at-risk -> contacted -> retained
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW `churn_analytics.retention_funnel` AS
WITH at_risk AS (
  SELECT customer_id FROM `churn_analytics.latest_predictions`
  WHERE risk_tier = 'High'
),
contacted AS (
  SELECT DISTINCT customer_id FROM `churn_analytics.retention_actions`
  WHERE action_type IN ('call', 'email', 'discount', 'upgrade')
),
retained AS (
  SELECT DISTINCT customer_id FROM `churn_analytics.retention_actions`
  WHERE outcome = 'retained'
)
SELECT
  (SELECT COUNT(*) FROM at_risk)   AS at_risk_count,
  (SELECT COUNT(*) FROM contacted) AS contacted_count,
  (SELECT COUNT(*) FROM retained)  AS retained_count;
