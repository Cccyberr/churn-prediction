CREATE OR REPLACE VIEW `churn_analytics.telco_customers_clean` AS
SELECT
  customerID, gender, SeniorCitizen, Partner, Dependents, tenure,
  CASE
    WHEN tenure < 12 THEN '0-12 months'
    WHEN tenure < 24 THEN '12-24 months'
    WHEN tenure < 48 THEN '24-48 months'
    ELSE '48+ months'
  END AS tenure_bucket,
  PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup,
  DeviceProtection, TechSupport, StreamingTV, StreamingMovies, Contract,
  PaperlessBilling, PaymentMethod, MonthlyCharges,
  SAFE_CAST(NULLIF(TRIM(TotalCharges), '') AS FLOAT64) AS TotalCharges,
  Churn,
  IF(Churn = 'Yes', 1, 0) AS churn_flag,
  ['California','Texas','Florida','New York','Illinois',
   'Pennsylvania','Ohio','Georgia','North Carolina','Michigan']
    [OFFSET(MOD(ABS(FARM_FINGERPRINT(customerID)), 10))] AS state
FROM `churn_analytics.customers`
