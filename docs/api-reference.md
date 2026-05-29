# API Reference

Python API for `agentassert-typec-core` — the shared kernel that powers all integration paths.

---

## Core Exports

```python
from agentassert_typec_core import (
    __version__,           # "0.4.0"
    ContractSpec,          # ContractSpecExtended (Pydantic model)
    SessionMonitor,        # Main session class
    TypeCDecision,         # Enum: ALLOW, MODIFY, DENY
    DecisionResult,        # Result of evaluating an event
    PreAction,             # TypeCEvent: before tool invocation
    PostAction,            # TypeCEvent: after tool returns
    TurnStart,             # TypeCEvent: user turn begins
    TurnEnd,               # TypeCEvent: assistant turn completes
    SessionStart,          # TypeCEvent: session boots
    SessionEnd,            # TypeCEvent: session closes
    ContextWindow,         # TypeCEvent: context measurement
    ContractBreachError,   # Exception: contract violation
    ContractLoadError,     # Exception: contract YAML invalid
)
```

---

## ContractSpec

Pydantic model representing a parsed contract. Frozen (immutable) and validated at construction.

```python
from agentassert_typec_core import ContractSpec

# Load from YAML
from agentassert_typec_core.dsl.parser import parse_contract

result = parse_contract("safety-minimal.yaml")
spec: ContractSpec = result.contract  # ContractSpecExtended

# Access contract properties
print(spec.name)                  # "safety-minimal"
print(spec.description)           # "Block destructive tool calls only."
print(spec.dsl_version)           # "0.4"
print(spec.kind)                  # "agent"

# Access process invariants
proc = spec.invariants.process
for bl in proc.tool_blocklist:
    print(bl.tools)               # ["rm -rf /*", "curl|bash"]

# Recovery config
print(spec.recovery.on_hard_violation)   # "raise"
print(spec.recovery.on_soft_violation)   # "log_and_continue"

# Satisfaction params
print(spec.satisfaction.p)        # 0.95
print(spec.satisfaction.delta)    # 0.10
print(spec.satisfaction.k)        # 3
```

### Loading without parsing

```python
from agentassert_typec_core import ContractSpec

spec = ContractSpec(
    contractspec="1.0",
    kind="agent",
    name="my-contract",
    description="...",
    version="0.1",
    invariants=InvariantsExtended(
        process=ProcessInvariants(
            tool_blocklist=[ToolBlocklist(tools=["rm -rf /*"], scope="session")]
        )
    ),
    recovery=RecoveryConfig(on_hard_violation="raise"),
)
```

---

## SessionMonitor

Main class for running a contract-enforced session. All integration paths (`proxy`, `sdk`, `claude-code`) use this internally.

```python
from agentassert_typec_core import SessionMonitor

monitor = SessionMonitor.from_yaml("contract.yaml")

# Or from a ContractSpec
monitor = SessionMonitor(spec)
```

### Methods

#### `evaluate(event: TypeCEvent) -> DecisionResult`

Evaluate a canonical event against the contract. Thread-safe (RLock-protected).

```python
from agentassert_typec_core import PreAction, SessionMonitor

monitor = SessionMonitor.from_yaml("safety-minimal.yaml")

event = PreAction(
    session_id="sess-1",
    contract_id="safety-minimal",
    tool="Bash",
    args={"command": "rm -rf /"},
)

result = monitor.evaluate(event)
print(result.decision)         # TypeCDecision.DENY
print(result.reason)           # "Tool 'Bash' matches blocklisted pattern 'rm -rf /*'"
print(result.violation_name)   # "tool_blocklist"
print(result.is_deny())        # True
```

#### `close() -> SessionEnd`

End the session and get the final Θ score and drift report.

```python
session_end = monitor.close()
print(session_end.theta)            # 0.94
print(session_end.drift_report)     # DriftReport with JSD summary
```

#### `schedule_judge_evaluation(turn_output, session_id)`

Schedule async judge predicate evaluation for a turn's output.

```python
monitor.schedule_judge_evaluation(
    turn_output="The answer depends on context, either approach works.",
    session_id="sess-1",
)
```

### Properties

| Property | Type | Description |
|---|---|---|
| `turn_count` | `int` | Number of completed turns |
| `deny_count` | `int` | Number of DENIED requests |

---

## Events (TypeCEvent)

All 7 canonical events inherit from the frozen `TypeCEvent` dataclass. All fields are keyword-only (`kw_only=True`).

### PreAction

```python
PreAction(
    session_id: str,
    contract_id: str,
    timestamp: float,          # auto: time.monotonic()
    tool: str,                 # e.g. "Bash", "anthropic.messages.create"
    args: dict[str, Any],      # tool arguments
    context: SessionContext | None,  # optional session context
)
```

### PostAction

```python
PostAction(
    session_id: str,
    contract_id: str,
    timestamp: float,
    tool: str,
    args: dict[str, Any],
    result: Any,               # tool result / API response
    state: dict[str, Any],     # extracted state for drift
)
```

### TurnStart

```python
TurnStart(
    session_id: str,
    contract_id: str,
    timestamp: float,
    user_input: str,           # user's prompt
    history_summary: HistoryDigest | None,
)
```

### TurnEnd

```python
TurnEnd(
    session_id: str,
    contract_id: str,
    timestamp: float,
    assistant_output: str,     # model's response
    state_delta: dict[str, Any],
)
```

### SessionStart

```python
SessionStart(
    session_id: str,
    contract_id: str,
    timestamp: float,
    workdir: str,              # working directory
    model: str,                # e.g. "claude-sonnet-4-6"
    config: dict[str, Any],
)
```

### SessionEnd

```python
SessionEnd(
    session_id: str,
    contract_id: str,
    timestamp: float,
    theta: float,              # final reliability score
    drift_report: DriftReport | None,
)
```

### ContextWindow

```python
ContextWindow(
    session_id: str,
    contract_id: str,
    timestamp: float,
    token_count: int,          # tokens in current context
    prefix_hash: str,          # hash of context prefix
)
```

---

## DecisionResult

```python
from agentassert_typec_core import DecisionResult, TypeCDecision

result = DecisionResult(
    decision=TypeCDecision.ALLOW,
    reason="",
    violation_name="",
    theta_penalty=0.0,
)

result.is_deny()       # bool — True if DENY
result.is_modify()     # bool — True if MODIFY
```

| Field | Type | Description |
|---|---|---|
| `decision` | `TypeCDecision` | ALLOW, MODIFY, or DENY |
| `reason` | `str` | Human-readable reason for the decision |
| `modified_args` | `dict \| None` | Modified arguments (when MODIFY) |
| `violation_name` | `str` | Name of violated constraint |
| `theta_penalty` | `float` | Θ penalty applied (0.0 if none) |

---

## TypeCDecision Enum

```python
from agentassert_typec_core import TypeCDecision

TypeCDecision.ALLOW    # Forward unchanged
TypeCDecision.MODIFY   # Forward with modified payload
TypeCDecision.DENY     # Block with error
```

---

## Exceptions

### ContractBreachError

Raised when a hard constraint is violated (tool_blocklist, tool_allowlist, must_state with DENY).

```python
from agentassert_typec_core import ContractBreachError

try:
    monitor.evaluate(event)
except ContractBreachError as e:
    print(e.violation_name)   # "tool_blocklist"
    print(e.reason)           # "Tool 'Bash' matches..."
    print(e.tool)             # "Bash"
    print(e.session_id)       # "safety-minimal"
    print(e.contract_id)      # "safety-minimal"

    # Serialization
    d = e.to_dict()           # dict with all fields
    j = e.to_json()           # JSON string
    http = e.to_http_body()   # HTTP error response format
    # {"error": "ContractBreachError", "violation": "...", ...}
```

### ContractLoadError

Raised when contract YAML is missing or invalid.

```python
from agentassert_typec_core import ContractLoadError

try:
    monitor = SessionMonitor.from_yaml("nonexistent.yaml")
except ContractLoadError as e:
    print(str(e))  # "Invalid contract: ..."
```

---

## DSL Parser

Direct access to the YAML parser (usually called via `SessionMonitor.from_yaml()`).

```python
from agentassert_typec_core.dsl.parser import parse_contract

result = parse_contract("contract.yaml")

print(result.is_valid)         # bool
print(result.contract)         # ContractSpecExtended | None
print(result.errors)           # list[ValidationError]
print(result.warnings)         # list[str] (dsl_version compat notes)
```

### DSL Version Compatibility

- `dsl_version: "0.3"` — loads as ABC v0.3 mode (process section ignored)
- `dsl_version: "0.4"` — full process operators supported
- Unknown version → validation error

---

## Compiled Contract

AST-compiled contract for fast evaluation. Compiled once at `SessionStart`, cached for the session.

```python
from agentassert_typec_core.dsl.ast_compiler import CompiledContract

compiled = CompiledContract.from_spec(spec)

# Compiled object contains:
# - Pre-compiled regex patterns for tool_blocklist
# - Pre-compiled regex patterns for must_state.before_tool_pattern
# - All operator configs in evaluation-ready form
```

---

## SessionMonitor (Full Usage Pattern)

```python
from agentassert_typec_core import (
    SessionMonitor, SessionStart, SessionEnd,
    PreAction, PostAction, TurnStart, TurnEnd, ContextWindow,
    ContractBreachError,
)

# Initialize
monitor = SessionMonitor.from_yaml("full-governance.yaml")

# Session start
monitor.evaluate(SessionStart(
    session_id="sess-1",
    contract_id="full-governance",
    workdir="/Users/me/code",
    model="claude-sonnet-4-6",
    config={},
))

# Context check
monitor.evaluate(ContextWindow(
    session_id="sess-1",
    contract_id="full-governance",
    token_count=45000,
    prefix_hash="abc123",
))

# User turn
monitor.evaluate(TurnStart(
    session_id="sess-1",
    contract_id="full-governance",
    user_input="Write a function to delete all files.",
))

# Pre-action check
try:
    result = monitor.evaluate(PreAction(
        session_id="sess-1",
        contract_id="full-governance",
        tool="Bash",
        args={"command": "rm -rf /"},
    ))
    if result.is_deny():
        raise ContractBreachError(
            violation_name=result.violation_name,
            reason=result.reason,
            tool="Bash",
            session_id="sess-1",
            contract_id="full-governance",
        )
except ContractBreachError as e:
    print(f"Blocked: {e.to_json()}")

# Post-action (if ALLOWed)
monitor.evaluate(PostAction(
    session_id="sess-1",
    contract_id="full-governance",
    tool="Write",
    args={"file": "delete.py"},
    result={"status": "ok"},
    state={},
))

# Turn end
monitor.evaluate(TurnEnd(
    session_id="sess-1",
    contract_id="full-governance",
    assistant_output="I've written the function.",
    state_delta={},
))

# Judge predicate (async)
monitor.schedule_judge_evaluation(
    turn_output="I've written the function.",
    session_id="sess-1",
)

# Session end
session_end = monitor.close()
print(f"Theta: {session_end.theta:.3f}")
print(f"Drift: {session_end.drift_report}")
```
