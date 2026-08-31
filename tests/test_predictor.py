"""Smoke tests for the predictor + retention engine.

Run with:
    pytest tests/

These tests skip the actual model-loading if no artifact is present, so they
work even before the notebook has been run.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.predictor import _normalise_row, _risk_tier
from app.retention import estimate_cltv, recommend


def test_risk_tier_thresholds():
    assert _risk_tier(0.05) == "Low"
    assert _risk_tier(0.39) == "Low"
    assert _risk_tier(0.40) == "Medium"
    assert _risk_tier(0.69) == "Medium"
    assert _risk_tier(0.70) == "High"
    assert _risk_tier(0.99) == "High"


def test_normalise_row_fills_defaults():
    row = _normalise_row({"gender": "Male"})
    assert row["gender"] == "Male"
    assert row["MonthlyCharges"] == 0.0
    assert "tenure" in row and row["tenure"] == 0.0


def test_normalise_row_handles_whitespace_numbers():
    row = _normalise_row({"TotalCharges": " "})
    assert row["TotalCharges"] == 0.0


def test_recommend_low_risk_returns_no_action():
    pred = {"churn_probability": 0.1, "risk_tier": "Low"}
    cust = {"Contract": "Two year", "MonthlyCharges": 50}
    recs = recommend(pred, cust)
    assert len(recs) == 1
    assert recs[0]["action_type"] == "no_action"


def test_recommend_high_risk_month_to_month():
    pred = {"churn_probability": 0.85, "risk_tier": "High"}
    cust = {
        "Contract": "Month-to-month",
        "MonthlyCharges": 90.0,
        "InternetService": "Fiber optic",
        "TechSupport": "No",
        "OnlineSecurity": "No",
        "PaymentMethod": "Electronic check",
        "tenure": 6,
    }
    recs = recommend(pred, cust)
    assert recs, "should return at least one recommendation"
    assert recs[0]["priority"] == 1
    titles = " ".join(r["title"] for r in recs)
    assert "12-month contract" in titles or "TechSupport" in titles


def test_estimate_cltv():
    assert estimate_cltv({"MonthlyCharges": 50}, months=24) == 1200.0
    assert estimate_cltv({"MonthlyCharges": None}) == 0.0
