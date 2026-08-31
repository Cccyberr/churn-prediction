"""Rule-based retention recommendation engine.

The rules are intentionally simple and inspectable — graders / admins
can tweak them without retraining the model. For more sophisticated
recommendations, the Gemini integration generates personalized email
copy on top of these rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Recommendation:
    title: str
    detail: str
    action_type: str           # one of: call, email, discount, upgrade, no_action
    estimated_cost: float      # USD per customer
    priority: int              # 1 = highest

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "detail": self.detail,
            "action_type": self.action_type,
            "estimated_cost": self.estimated_cost,
            "priority": self.priority,
        }


def _monthly_charges(customer: dict[str, Any]) -> float:
    try:
        return float(customer.get("MonthlyCharges", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def recommend(prediction: dict[str, Any], customer: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a ranked list of retention recommendations."""
    prob = float(prediction.get("churn_probability", 0.0))
    tier = prediction.get("risk_tier", "Low")
    contract = customer.get("Contract", "")
    internet = customer.get("InternetService", "")
    tech_support = customer.get("TechSupport", "")
    online_security = customer.get("OnlineSecurity", "")
    payment = customer.get("PaymentMethod", "")
    monthly = _monthly_charges(customer)
    tenure = int(customer.get("tenure", 0) or 0)

    recs: list[Recommendation] = []

    if tier == "Low":
        recs.append(Recommendation(
            title="No action needed",
            detail="Customer is engaged and unlikely to churn. Continue standard service.",
            action_type="no_action", estimated_cost=0.0, priority=3,
        ))
        return [r.to_dict() for r in recs]

    # High-priority rules
    if prob >= 0.70 and contract == "Month-to-month":
        recs.append(Recommendation(
            title="Offer 12-month contract upgrade",
            detail=(
                "Customer is on a month-to-month contract — the single strongest churn predictor. "
                "Offer 15% discount in exchange for a 12-month commitment. Expected retention lift: ~35%."
            ),
            action_type="upgrade",
            estimated_cost=round(monthly * 12 * 0.15, 2),
            priority=1,
        ))

    if prob >= 0.70 and internet == "Fiber optic" and tech_support == "No":
        recs.append(Recommendation(
            title="Bundle free TechSupport for 6 months",
            detail=(
                "Fiber optic customers without tech support churn at >50%. "
                "Adding free tech support for 6 months addresses the most common pain point."
            ),
            action_type="upgrade", estimated_cost=60.0, priority=1,
        ))

    if prob >= 0.70 and online_security == "No":
        recs.append(Recommendation(
            title="Offer OnlineSecurity add-on at 50% off",
            detail="Customers without OnlineSecurity churn 2x more than those with it.",
            action_type="upgrade", estimated_cost=30.0, priority=2,
        ))

    if tier == "High" and tenure < 12:
        recs.append(Recommendation(
            title="Schedule personal onboarding call",
            detail=(
                "New customer in their first year. A proactive welcome / health-check call "
                "from a senior CSR significantly increases retention in this cohort."
            ),
            action_type="call", estimated_cost=25.0, priority=1,
        ))

    # Medium-tier rules
    if 0.40 <= prob < 0.70 and monthly > 80:
        recs.append(Recommendation(
            title="Personalised usage review",
            detail=(
                "High monthly charges relative to peers. Offer a usage review call to ensure "
                "the customer is on the right plan — prevents bill-shock-driven churn."
            ),
            action_type="call", estimated_cost=20.0, priority=2,
        ))

    if payment == "Electronic check":
        recs.append(Recommendation(
            title="Encourage auto-pay migration",
            detail=(
                "Electronic check users churn at the highest rate of any payment method. "
                "Offer a one-time $5 credit to migrate to auto-pay or credit card."
            ),
            action_type="discount", estimated_cost=5.0, priority=2,
        ))

    # Fallback recommendation
    if not recs:
        recs.append(Recommendation(
            title="Send personalised retention email",
            detail="Use Gemini-powered email generator for a tailored outreach.",
            action_type="email", estimated_cost=2.0, priority=2,
        ))

    recs.sort(key=lambda r: r.priority)
    return [r.to_dict() for r in recs]


def estimate_cltv(customer: dict[str, Any], months: int = 24) -> float:
    """Rough customer lifetime value estimate (assumed N months retention)."""
    return round(_monthly_charges(customer) * months, 2)
