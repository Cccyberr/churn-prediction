"""Gemini-powered personalised retention email generator."""
from __future__ import annotations

import logging
from typing import Any

from app.config import config

log = logging.getLogger(__name__)

_RETENTION_PROMPT = """You are a senior customer success specialist at a telecom company.
Write a short (max 150 words), warm but professional retention email to a customer who
is predicted at high risk of churning. The email must:

1. Address them as "Valued Customer" (we don't have first names).
2. Acknowledge their loyalty without being patronising.
3. Reference the SPECIFIC retention offer below, not generic platitudes.
4. End with a clear call-to-action (reply or call back) and a single contact line.
5. Sound like a human wrote it, not a template.

Customer profile:
- Tenure: {tenure} months
- Contract: {contract}
- Monthly charges: ${monthly_charges}
- Internet service: {internet_service}
- Predicted churn probability: {probability:.0%}

Top churn drivers for this customer:
{top_factors}

Retention offer to feature in the email:
{offer_title}: {offer_detail}

Return ONLY the email body. No subject line, no markdown, no commentary.
"""


class GeminiClient:
    def __init__(self) -> None:
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        if not config.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        import google.generativeai as genai

        genai.configure(api_key=config.gemini_api_key)
        self._model = genai.GenerativeModel(config.gemini_model)

    def generate_retention_email(
        self,
        customer: dict[str, Any],
        prediction: dict[str, Any],
        offer: dict[str, Any],
    ) -> str:
        self._ensure_loaded()

        factors_lines = "\n".join(
            f"- {f.get('feature')}: {f.get('value')}"
            for f in (prediction.get("top_factors") or [])
        ) or "- (no factor data available)"

        prompt = _RETENTION_PROMPT.format(
            tenure=customer.get("tenure", "?"),
            contract=customer.get("Contract", "?"),
            monthly_charges=customer.get("MonthlyCharges", "?"),
            internet_service=customer.get("InternetService", "?"),
            probability=float(prediction.get("churn_probability", 0.0)),
            top_factors=factors_lines,
            offer_title=offer.get("title", "Retention offer"),
            offer_detail=offer.get("detail", ""),
        )

        try:
            response = self._model.generate_content(prompt)
            return (response.text or "").strip()
        except Exception:  # noqa: BLE001
            log.exception("Gemini call failed")
            raise


gemini = GeminiClient()
