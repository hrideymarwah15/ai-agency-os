"""ROI calculator for opportunity detection.

Computes monthly ROI using the formula:
    (time_saved_hours_monthly * hourly_cost * frequency_monthly) - impl_cost_estimate

Hourly cost is looked up from a static bucket table based on business industry
and employee count size. The implementation cost can be overridden via the
opportunity's ``roi_params``; otherwise a fallback template is used.
"""

from __future__ import annotations

from backend.database import Business, WebsiteAudit

# Sample hourly cost buckets – in a real system these would be in config.
HOURLY_COST_BUCKETS = {
    "Restaurant": {"Micro": 500, "Small": 800, "Medium": 1200, "Large": 2000, "Enterprise": 3000},
    "Technology": {"Micro": 1000, "Small": 1500, "Medium": 2500, "Large": 4000, "Enterprise": 6000},
    # Default bucket for unknown industries.
    "default": {"Micro": 1000, "Small": 1200, "Medium": 1500, "Large": 2000, "Enterprise": 3000},
}

# Fallback implementation cost templates per rule name.
IMPL_COST_TEMPLATES = {
    "booking_automation": 15000,
    "customer_support_bot": 35000,
    "faq_assistant": 20000,
}


class ROICalculator:
    def __init__(self, hourly_buckets: dict | None = None, impl_templates: dict | None = None):
        self.hourly_buckets = hourly_buckets or HOURLY_COST_BUCKETS
        self.impl_templates = impl_templates or IMPL_COST_TEMPLATES

    def _size_bucket(self, employee_count: int | None) -> str:
        if not employee_count:
            return "Micro"
        if employee_count <= 10:
            return "Micro"
        if employee_count <= 50:
            return "Small"
        if employee_count <= 200:
            return "Medium"
        if employee_count <= 1000:
            return "Large"
        return "Enterprise"

    def _hourly_cost(self, industry: str | None, size_bucket: str) -> int:
        if not industry:
            industry = "default"
        return self.hourly_buckets.get(industry, self.hourly_buckets["default"]).get(
            size_bucket, 1000
        )

    def calc_roi(self, opp: dict, business: Business, audit: WebsiteAudit | None) -> float:
        """Calculate monthly ROI for a single opportunity.

        ``opp`` is the dict produced by the rule engine and must contain an
        ``roi_params`` mapping with ``time_saved_hours_monthly``,
        ``frequency_monthly`` and optional ``impl_cost_estimate``.
        """
        params = opp.get("roi_params", {})
        time_saved = params.get("time_saved_hours_monthly", 0)
        freq = params.get("frequency_monthly", 1)
        impl_cost = params.get("impl_cost_estimate")
        if impl_cost is None:
            impl_cost = self.impl_templates.get(str(opp.get("name")), 0)
        industry = business.industry
        size_bucket = self._size_bucket(business.employee_count)
        hourly = self._hourly_cost(industry, size_bucket)
        return float((time_saved * hourly * freq) - impl_cost)
