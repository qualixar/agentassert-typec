from __future__ import annotations

from dataclasses import dataclass, field

from agentassert_typec_core.models.contract import ContractSpecExtended


@dataclass
class ValidationError:
    level: str
    path: str
    message: str
    code: str


@dataclass
class ParseResult:
    contract: ContractSpecExtended | None = None
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.contract is not None
