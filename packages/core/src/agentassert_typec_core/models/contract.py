from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)


# --- ABC v0.3 Constraint Check (inherited for backward compat) ---

class ConstraintCheck(_FrozenModel):
    field: str
    equals: Any | None = None
    not_equals: Any | None = None
    gt: float | None = None
    gte: float | None = None
    lt: float | None = None
    lte: float | None = None
    in_: list[Any] | None = Field(None, alias="in")
    not_in: list[Any] | None = None
    contains: str | None = None
    not_contains: str | None = None
    matches: str | None = None
    exists: bool | None = None
    expr: str | None = None
    between: tuple[float, float] | None = None


class HardConstraint(_FrozenModel):
    name: str
    description: str = ""
    category: str = ""
    check: ConstraintCheck


class SoftConstraint(_FrozenModel):
    name: str
    description: str = ""
    category: str = ""
    check: ConstraintCheck
    recovery: str = ""
    recovery_window: int = Field(3, ge=1, le=1000)


class Invariants(_FrozenModel):
    hard: list[HardConstraint] = []
    soft: list[SoftConstraint] = []


class GovernanceConstraint(_FrozenModel):
    name: str
    description: str = ""
    category: str = ""
    check: ConstraintCheck
    recovery: str = ""
    recovery_window: int = Field(3, ge=1, le=1000)


class Governance(_FrozenModel):
    hard: list[HardConstraint] = []
    soft: list[GovernanceConstraint] = []


class RecoveryAction(_FrozenModel):
    name: str
    type: Literal[
        "inject_correction",
        "reduce_autonomy",
        "pause_and_escalate",
        "graceful_shutdown",
    ]
    actions: list[str] = []
    max_attempts: int = Field(1, ge=1, le=100)
    fallback: str | None = None


class RecoveryConfig(_FrozenModel):
    strategies: list[RecoveryAction] = []
    on_hard_violation: str = "raise"
    on_soft_violation: str = "log_and_continue"


class Precondition(_FrozenModel):
    name: str
    description: str = ""
    check: ConstraintCheck


class ContractMetadata(_FrozenModel):
    author: str = ""
    domain: str = ""
    created: str = ""
    tags: list[str] = []


class SatisfactionParams(_FrozenModel):
    p: float = Field(0.95, ge=0.0, le=1.0)
    delta: float = Field(0.1, gt=0.0, le=1.0)
    k: int = Field(3, ge=1, le=1000)


class DriftWeights(_FrozenModel):
    compliance: float = Field(0.6, ge=0.0, le=1.0)
    distributional: float = Field(0.4, ge=0.0, le=1.0)


class DriftThresholds(_FrozenModel):
    warning: float = Field(0.3, ge=0.0, le=1.0)
    critical: float = Field(0.6, ge=0.0, le=1.0)


class DriftConfig(_FrozenModel):
    weights: DriftWeights = DriftWeights()
    window: int = Field(50, ge=1, le=10000)
    thresholds: DriftThresholds = DriftThresholds()


class ReliabilityWeights(_FrozenModel):
    compliance: float = Field(0.35, ge=0.0, le=1.0)
    drift: float = Field(0.25, ge=0.0, le=1.0)
    event_freq: float = Field(0.20, ge=0.0, le=1.0, alias="stress")
    recovery_success: float = Field(0.20, ge=0.0, le=1.0, alias="recovery")


class ReliabilityConfig(_FrozenModel):
    weights: ReliabilityWeights = ReliabilityWeights()
    deployment_threshold: float = Field(0.90, ge=0.0, le=1.0)


# --- Process Contract Operators (7 total, v0.4) ---

class MustPrecede(_FrozenModel):
    before: str
    after: str
    scope: Literal["turn", "session"] = "turn"


class MustState(_FrozenModel):
    field: str
    before_tool_pattern: str
    rationale: str = ""


class ToolBlocklist(_FrozenModel):
    tools: list[str]
    scope: Literal["session", "turn"] = "session"


class ToolAllowlist(_FrozenModel):
    tools: list[str]
    scope: str = "session"


class ContextBudget(_FrozenModel):
    max_tokens_per_turn: int = Field(60_000, gt=0)
    action_on_breach: Literal["warn", "deny", "compress"] = "warn"


class ProcessDrift(_FrozenModel):
    window_size: int = Field(10, gt=0)
    jsd_threshold: float = Field(0.3, gt=0.0, le=1.0)
    action: Literal["log", "warn", "theta_penalty"] = "log"


class JudgePredicate(_FrozenModel):
    rubric: str
    sample_rate: float = Field(0.2, gt=0.0, le=1.0)
    model: str = "haiku"
    action_on_fail: Literal["log", "warn", "theta_penalty", "deny"] = "theta_penalty"
    cost_ceiling_usd_per_session: float = Field(0.10, ge=0.0)


# --- Phase 3: Content Operators ---

class PiiPatternGroup(str, Enum):
    email = "email"
    phone = "phone"
    ssn = "ssn"
    credit_card = "credit_card"
    api_key = "api_key"
    ip_address = "ip_address"


class CustomPiiPattern(_FrozenModel):
    name: str
    regex: str


class PiiFilter(_FrozenModel):
    patterns: list[PiiPatternGroup] = [PiiPatternGroup.email, PiiPatternGroup.phone]
    action: Literal["log", "warn", "redact", "block"] = "log"
    streaming_action: Literal["log", "warn"] = "log"
    custom_patterns: list[CustomPiiPattern] = []


class ProviderPriceEntry(_FrozenModel):
    input: float = Field(gt=0.0)   # USD per million tokens
    output: float = Field(gt=0.0)


class CostCeiling(_FrozenModel):
    max_usd_per_session: float = Field(gt=0.0)
    action_on_breach: Literal["deny", "warn", "log"] = "warn"
    price_per_million_input: float | None = None
    price_per_million_output: float | None = None
    provider_price_map: dict[str, ProviderPriceEntry] = {}


class RepetitionGuard(_FrozenModel):
    window_size: int = Field(5, ge=2, le=50)
    max_repeats: int = Field(3, ge=2, le=100)
    action: Literal["deny", "warn", "log"] = "deny"
    ignore_tools: list[str] = []


# --- Process Invariants container ---

class ProcessInvariants(_FrozenModel):
    must_precede: list[MustPrecede] = []
    must_state: list[MustState] = []
    tool_blocklist: list[ToolBlocklist] = []
    tool_allowlist: list[ToolAllowlist] = []
    context_budget: ContextBudget | None = None
    process_drift: ProcessDrift | None = None
    judge_predicate: list[JudgePredicate] = []
    # Phase 3: content operators (all optional, None = disabled)
    pii_filter: PiiFilter | None = None
    cost_ceiling: CostCeiling | None = None
    repetition_guard: RepetitionGuard | None = None


# --- Extended Invariants (adds process to ABC) ---

class InvariantsExtended(_FrozenModel):
    hard: list[HardConstraint] = []
    soft: list[SoftConstraint] = []
    process: ProcessInvariants | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_process_from_list(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        process_raw = data.get("process")
        if isinstance(process_raw, list):
            data["process"] = _list_to_process_invariants(process_raw)
        return data


def _list_to_process_invariants(ops: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "must_precede": [],
        "must_state": [],
        "tool_blocklist": [],
        "tool_allowlist": [],
        "judge_predicate": [],
    }
    for op in ops:
        if not isinstance(op, dict):
            continue
        if "must_precede" in op:
            result["must_precede"].append(op["must_precede"])
        if "must_state" in op:
            result["must_state"].append(op["must_state"])
        if "tool_blocklist" in op:
            result["tool_blocklist"].append(op["tool_blocklist"])
        if "tool_allowlist" in op:
            result["tool_allowlist"].append(op["tool_allowlist"])
        if "judge_predicate" in op:
            result["judge_predicate"].append(op["judge_predicate"])
        if "context_budget" in op:
            result["context_budget"] = op["context_budget"]
        if "process_drift" in op:
            result["process_drift"] = op["process_drift"]
        # Phase 3: content operators (singular — last one wins)
        if "pii_filter" in op:
            result["pii_filter"] = op["pii_filter"]
        if "cost_ceiling" in op:
            result["cost_ceiling"] = op["cost_ceiling"]
        if "repetition_guard" in op:
            result["repetition_guard"] = op["repetition_guard"]
    return result


# --- Upstream Provider URL Overrides (v0.5) ---

class UpstreamConfig(_FrozenModel):
    """Override the default LLM provider URLs the proxy forwards to.

    Use this when your LLM client is configured to talk to a non-standard
    endpoint (e.g., DeepSeek's Anthropic-compatible API, a local LLM, or
    any OpenAI-compatible backend).

    Priority: contract upstream > TYPEC_UPSTREAM_* env var > ANTHROPIC_BASE_URL/OPENAI_BASE_URL > built-in default.
    """
    anthropic: str | None = None  # e.g. https://api.deepseek.com/anthropic
    openai: str | None = None     # e.g. https://api.deepseek.com/v1
    gemini: str | None = None     # e.g. https://generativelanguage.googleapis.com
    openrouter: str | None = None # e.g. https://openrouter.ai/api


# --- Root ContractSpecExtended ---

class ContractSpecExtended(_FrozenModel):
    dsl_version: str = "0.3"
    contractspec: str
    kind: Literal["agent", "pipeline"]
    name: str
    description: str
    version: str
    metadata: ContractMetadata | None = None
    preconditions: list[Precondition] = []
    invariants: InvariantsExtended | None = None
    governance: Governance | None = None
    recovery: RecoveryConfig | None = None
    satisfaction: SatisfactionParams | None = None
    drift: DriftConfig | None = None
    reliability: ReliabilityConfig | None = None
    upstream: UpstreamConfig | None = None
