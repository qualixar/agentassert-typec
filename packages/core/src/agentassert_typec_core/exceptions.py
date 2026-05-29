from __future__ import annotations

import json
from dataclasses import dataclass, asdict


@dataclass
class ContractBreachError(Exception):
    violation_name: str
    reason: str
    tool: str
    session_id: str
    contract_id: str
    decision: str = "deny"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_http_body(self) -> dict:
        return {
            "error": "ContractBreachError",
            "violation": self.violation_name,
            "reason": self.reason,
            "tool": self.tool,
            "session_id": self.session_id,
            "contract_id": self.contract_id,
        }


class ContractLoadError(Exception):
    pass


class PredicateEvalError(Exception):
    pass
