-- ================================================================
-- 03_daily_aggregations.sql
-- Schedule this MERGE statement as a daily BigQuery Scheduled Query.
-- Console: BigQuery -> Scheduled Queries -> New scheduled query.
-- ================================================================

MERGE `churn_analytics.daily_metrics` T
USING (
  SELECT
    CURRENT_DATE() AS metric_date,
    (SELECT COUNT(*) FROM `churn_analytics.telco_customers_clean`) AS total_customers,
    (SELECT SUM(churn_flag) FROM `churn_analytics.telco_customers_clean`) AS churned_customers,
    (SELECT SAFE_DIVIDE(SUM(churn_flag), COUNT(*)) FROM `churn_analytics.telco_customers_clean`) AS churn_rate,
    (SELECT SUM(revenue_at_risk) FROM `churn_analytics.telco_customers_with_predictions`) AS revenue_at_risk,
    (SELECT COUNTIF(risk_tier = 'High') FROM `churn_analytics.latest_predictions`) AS high_risk_count,
    (SELECT COUNTIF(risk_tier = 'Medium') FROM `churn_analytics.latest_predictions`) AS medium_risk_count,
    (SELECT COUNTIF(risk_tier = 'Low') FROM `churn_analytics.latest_predictions`) AS low_risk_count,
    (SELECT COUNT(*) FROM `churn_analytics.retention_actions`
       WHERE DATE(created_at) = CURRENT_DATE()) AS actions_taken,
    (SELECT COUNTIF(outcome = 'retained') FROM `churn_analytics.retention_actions`
       WHERE DATE(outcome_at) = CURRENT_DATE()) AS retained_count
) S
ON T.metric_date = S.metric_date
WHEN MATCHED THEN UPDATE SET
  total_customers   = S.total_customers,
  churned_customers = S.churned_customers,
  churn_rate        = S.churn_rate,
  revenue_at_risk   = S.revenue_at_risk,
  high_risk_count   = S.high_risk_count,
  medium_risk_count = S.medium_risk_count,
  low_risk_count    = S.low_risk_count,
  actions_taken     = S.actions_taken,
  retained_count    = S.retained_count
WHEN NOT MATCHED THEN INSERT ROW;
