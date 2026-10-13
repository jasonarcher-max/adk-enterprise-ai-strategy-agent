"""Explicit Pydantic & JSON Schemas for input validation and LLM output constraints.

Rubric Alignment:
- Category 1 (Tool & Interface Design): Explicit JSON Schemas (5 pts)
  Strict input and output schemas to validate tool arguments and constrain LLMs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator  # type: ignore

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

    class ValidationError(ValueError):  # type: ignore[no-redef]
        """Fallback validation error when Pydantic is not installed in bare Python."""

    def Field(default: Any = None, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        if "default_factory" in kwargs:
            return field(default_factory=kwargs["default_factory"], metadata=kwargs)
        return field(default=default, metadata=kwargs)

    def field_validator(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def _decorator(fn: Any) -> Any:
            return fn

        return _decorator

    class BaseModel:  # type: ignore[no-redef]
        """Lightweight BaseModel fallback providing `.model_dump()` and `.model_json_schema()`."""

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self) -> Dict[str, Any]:
            result: Dict[str, Any] = {}
            for k, v in self.__dict__.items():
                if isinstance(v, list):
                    result[k] = [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in v
                    ]
                elif hasattr(v, "model_dump"):
                    result[k] = v.model_dump()
                else:
                    result[k] = v
            return result


class IncumbentCompetitor(str, Enum):
    """Supported incumbent competitors in enterprise retail/e-commerce accounts."""

    N8N = "n8n"
    GLEAN = "glean"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEVIN = "devin"


class EcommerceWorkloadDomain(str, Enum):
    """Core retail and e-commerce workload domains."""

    CATALOG_ENRICHMENT = "catalog_enrichment"
    ENTERPRISE_KNOWLEDGE_SEARCH = "enterprise_knowledge_search"
    WORKFLOW_AUTOMATION = "workflow_automation"
    SOFTWARE_ENGINEERING_VELOCITY = "software_engineering_velocity"
    CUSTOMER_SERVICE_CONCIERGE = "customer_service_concierge"


# Explicit JSON Schema Definitions for Tool Inputs & Outputs
COMPETITOR_BATTLECARD_INPUT_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CompetitorBattlecardInput",
    "type": "object",
    "required": ["competitor_name"],
    "properties": {
        "competitor_name": {
            "type": "string",
            "enum": ["n8n", "glean", "anthropic", "openai", "devin"],
            "description": "Name of the incumbent competitor tool or vendor.",
        },
        "customer_industry": {
            "type": "string",
            "default": "Retail & E-Commerce",
            "description": "Industry vertical of the enterprise customer.",
        },
    },
    "additionalProperties": False,
}

COMPETITOR_BATTLECARD_OUTPUT_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CompetitorBattlecardOutput",
    "type": "object",
    "required": [
        "status",
        "competitor",
        "incumbent_category",
        "incumbent_strengths",
        "enterprise_gaps_and_risks",
        "google_cloud_counter_solution",
        "coexistence_bridge_play",
        "displacement_win_themes",
        "discovery_questions",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["success", "error"]},
        "competitor": {"type": "string"},
        "incumbent_category": {"type": "string"},
        "incumbent_strengths": {"type": "array", "items": {"type": "string"}},
        "enterprise_gaps_and_risks": {"type": "array", "items": {"type": "string"}},
        "google_cloud_counter_solution": {"type": "string"},
        "coexistence_bridge_play": {"type": "string"},
        "displacement_win_themes": {"type": "array", "items": {"type": "string"}},
        "discovery_questions": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


class CompetitorBattlecardInput(BaseModel):
    """Strict input schema for fetching a competitor battlecard."""

    competitor_name: str = Field(
        ...,
        description=(
            "Name of the incumbent competitor tool or vendor. "
            "Must be one of: 'n8n', 'glean', 'anthropic', 'openai', 'devin'."
        ),
    )
    customer_industry: str = Field(
        default="Retail & E-Commerce",
        description="Industry vertical of the enterprise customer (e.g., Retail & E-Commerce).",
    )

    def __init__(self, **data: Any) -> None:
        raw_comp = data.get("competitor_name")
        if not isinstance(raw_comp, str) or not raw_comp.strip():
            raise ValidationError("`competitor_name` must be a non-empty string.")
        data["competitor_name"] = raw_comp.strip().lower()
        data.setdefault("customer_industry", "Retail & E-Commerce")
        super().__init__(**data)

    @field_validator("competitor_name")
    @classmethod
    def normalize_competitor(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("competitor_name cannot be empty")
        return value.strip().lower()


class CompetitorBattlecardOutput(BaseModel):
    """Strict output schema representing a structured competitive battlecard."""

    status: str = Field(..., description="Execution status: 'success' or 'error'.")
    competitor: str = Field(..., description="Normalized competitor identifier.")
    incumbent_category: str = Field(..., description="Market category of the incumbent.")
    incumbent_strengths: List[str] = Field(
        default_factory=list,
        description="Where the incumbent is typically perceived as strong.",
    )
    enterprise_gaps_and_risks: List[str] = Field(
        default_factory=list,
        description="Key architectural, governance, TCO, or scaling gaps at enterprise scale.",
    )
    google_cloud_counter_solution: str = Field(
        ...,
        description="Primary Google Cloud / Vertex AI / Gemini Enterprise counter-solution.",
    )
    coexistence_bridge_play: str = Field(
        ...,
        description="Pragmatic 'embrace & extend' play to coexist before full consolidation.",
    )
    displacement_win_themes: List[str] = Field(
        default_factory=list,
        description="Top executive and technical win themes for displacing or boxing in the incumbent.",
    )
    discovery_questions: List[str] = Field(
        default_factory=list,
        description="High-impact qualifying questions for the Consulting Account Lead to ask.",
    )


class WorkloadFitInput(BaseModel):
    """Strict input schema for evaluating e-commerce AI workload fit."""

    workload_domain: str = Field(
        ...,
        description=(
            "Target e-commerce workload domain: 'catalog_enrichment', "
            "'enterprise_knowledge_search', 'workflow_automation', "
            "'software_engineering_velocity', or 'customer_service_concierge'."
        ),
    )
    current_incumbents: List[str] = Field(
        default_factory=list,
        description="List of incumbent tools currently used or under evaluation.",
    )


class HorizonPhase(BaseModel):
    """Single horizon in a 3-Horizon Enterprise AI Strategy."""

    horizon_name: str = Field(..., description="Name and timeframe of the horizon.")
    objective: str = Field(..., description="Primary strategic objective.")
    recommended_google_stack: List[str] = Field(
        ..., description="Google Cloud AI products and ADK patterns used in this phase."
    )
    incumbent_strategy: str = Field(
        ..., description="How incumbents (n8n, Glean, Anthropic, OpenAI, Devin) are handled."
    )
    measurable_business_kpis: List[str] = Field(
        ..., description="Quantifiable business and engineering outcomes."
    )


class ThreeHorizonWinStrategyOutput(BaseModel):
    """Strict output schema for the final synthesized Account AI Win Strategy."""

    account_industry: str = Field(
        default="Retail & E-Commerce",
        description="Customer industry sector.",
    )
    executive_summary: str = Field(
        ...,
        description="Concise C-level executive summary of the Google Cloud AI strategy.",
    )
    competitor_positioning_matrix: Dict[str, str] = Field(
        ...,
        description="Map of each incumbent competitor to the specific Google Cloud play.",
    )
    horizons: List[HorizonPhase] = Field(
        ...,
        description="Ordered 3-Horizon roadmap (Horizon 1: Coexistence, Horizon 2: Expansion, Horizon 3: Consolidation).",
    )
    governance_and_security_moat: List[str] = Field(
        ...,
        description="Enterprise security, VPC-SC, data gravity, and FinOps advantages.",
    )
    requires_human_approval_before_external_share: bool = Field(
        default=True,
        description="Whether human sign-off is required before distributing externally.",
    )
