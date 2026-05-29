from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agentassert_typec_core.models.contract import ContractSpecExtended


@dataclass
class CompiledContract:
    spec: ContractSpecExtended

    tool_blocklist_patterns: list[re.Pattern[str]] = field(default_factory=list)
    tool_allowlist_patterns: list[tuple[str, list[re.Pattern[str]]]] = field(default_factory=list)
    must_precede_rules: list[dict[str, Any]] = field(default_factory=list)
    must_state_rules: list[dict[str, Any]] = field(default_factory=list)
    context_budget_limit: int | None = None
    context_budget_action: str = "warn"
    process_drift_config: Any | None = None
    judge_predicates: list[dict[str, Any]] = field(default_factory=list)

    hard_checks: list[Any] = field(default_factory=list)
    soft_checks: list[Any] = field(default_factory=list)

    @classmethod
    def from_spec(cls, spec: ContractSpecExtended) -> "CompiledContract":
        c = cls(spec=spec)
        c._compile_process_invariants()
        c._compile_abc_checks()
        return c

    def _compile_process_invariants(self) -> None:
        if not self.spec.invariants or not self.spec.invariants.process:
            return
        proc = self.spec.invariants.process

        for bl in proc.tool_blocklist:
            for pattern_str in bl.tools:
                parts = pattern_str.split("|")
                for part in parts:
                    rx = re.compile(
                        re.escape(part).replace(r"\*", ".*").replace(r"\?", "."),
                        re.IGNORECASE,
                    )
                    self.tool_blocklist_patterns.append(rx)

        for al in proc.tool_allowlist:
            compiled = [
                re.compile(re.escape(t).replace(r"\*", ".*"), re.IGNORECASE)
                for t in al.tools
            ]
            self.tool_allowlist_patterns.append((al.scope, compiled))

        if proc.context_budget:
            self.context_budget_limit = proc.context_budget.max_tokens_per_turn
            self.context_budget_action = proc.context_budget.action_on_breach

        for mp in proc.must_precede:
            self.must_precede_rules.append({
                "before": mp.before,
                "after": mp.after,
                "scope": mp.scope,
            })

        for ms in proc.must_state:
            parts = ms.before_tool_pattern.split("|")
            patterns = [
                re.compile(re.escape(p).replace(r"\*", ".*"), re.IGNORECASE)
                for p in parts
            ]
            self.must_state_rules.append({
                "field": ms.field,
                "patterns": patterns,
                "rationale": ms.rationale,
            })

        if proc.process_drift:
            self.process_drift_config = proc.process_drift

        for jp in proc.judge_predicate:
            self.judge_predicates.append({
                "rubric": jp.rubric,
                "sample_rate": jp.sample_rate,
                "model": jp.model,
                "action_on_fail": jp.action_on_fail,
                "cost_ceiling": jp.cost_ceiling_usd_per_session,
            })

    def _compile_abc_checks(self) -> None:
        if not self.spec.invariants:
            return
        for c in self.spec.invariants.hard:
            if c.check.expr:
                self.hard_checks.append(("expr", c.name, c.check.expr))
            else:
                self.hard_checks.append(("struct", c.name, c.check))
        for c in self.spec.invariants.soft:
            if c.check.expr:
                self.soft_checks.append(("expr", c.name, c.check.expr))
            else:
                self.soft_checks.append(("struct", c.name, c.check))
