# agentassert-typec-claude-code

**Claude Code hook adapter — contract enforcement directly in Claude Code.**

## Install

```bash
pip install agentassert-typec-claude-code
agentassert-claude-code install --contract partner-mode.yaml
export AGENTASSERT_CONTRACT=$(pwd)/partner-mode.yaml
```

## What Happens

1. A `00-agentassert-typec.py` hook is placed in `~/.claude-hooks/`
2. Every tool call in Claude Code is intercepted
3. Contract is evaluated in-process (sub-10ms)
4. On DENY: block with reason; on ALLOW: forward

## Available Contracts

```bash
# Minimal: just block destructive tools
agentassert-claude-code install --contract $(pip show agentassert-typec-claude-code | grep Location | cut -d' ' -f2)/contracts/templates/safety-minimal.yaml

# Partner mode: challenge-first, cost-before-paid, drift detection
agentassert-claude-code install --contract $(pip show agentassert-typec-claude-code | grep Location | cut -d' ' -f2)/contracts/templates/partner-mode.yaml

# Full governance: all 7 operators
agentassert-claude-code install --contract $(pip show agentassert-typec-claude-code | grep Location | cut -d' ' -f2)/contracts/templates/full-governance.yaml
```

## The Partner Mode Story

Varun's `~/.claude/CLAUDE.md` + `~/.claude/rules/*.md` contained ~14,000 tokens of process rules. After migrating to `partner-mode.yaml`:

- **47.8% token reduction** per turn (49,636 → ~25,920 bytes)
- **process rules:** 31,322 bytes → 1,203 bytes (96% compression of rules)
- **Replaced:** challenge-first, cost-before-paid-API, tool blocklist, destructive-command firewall, context budget
- **Preserved:** style/voice rules (cannot formalize), capability routing, reference docs

See `case_study/measurements.md` for the full analysis.

## Status

```bash
agentassert-claude-code status
```

## Uninstall

```bash
agentassert-claude-code uninstall
```

## License

MIT
