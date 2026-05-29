# Claude Code Hook Guide

Zero-code integration for Claude Code CLI users. Installs a hook that enforces contracts on every tool use.

---

## Install

```bash
pip install agentassert-typec-claude-code
```

---

## Quick Install

```bash
agentassert-claude-code install --contract safety-minimal.yaml
```

This drops `00-agentassert-typec.py` into `~/.claude-hooks/`. The `00-` prefix ensures it runs before any other hooks.

---

## Check Status

```bash
agentassert-claude-code status
```

Output:
```
✅ Hook installed: /Users/you/.claude-hooks/00-agentassert-typec.py
   AGENTASSERT_CONTRACT=/Users/you/safety-minimal.yaml
```

---

## Remove

```bash
agentassert-claude-code uninstall
```

---

## CLI Reference

### `agentassert-claude-code install`

```bash
agentassert-claude-code install --contract partner-mode.yaml
agentassert-claude-code install -c full-governance.yaml --force
```

| Flag | Description |
|---|---|
| `--contract`, `-c` | Path to contract YAML (required) |
| `--force`, `-f` | Overwrite existing hook if already installed |

### `agentassert-claude-code uninstall`

Removes the hook file from `~/.claude-hooks/`.

### `agentassert-claude-code status`

Shows whether hook is installed and which contract is active.

---

## Contract Templates

Three templates ship with the package. Install with:

```bash
agentassert-claude-code install --contract safety-minimal.yaml
```

### safety-minimal.yaml

Blocklist only. Blocks destructive commands (`rm -rf /*`, `curl|bash`, `--no-verify`). Zero false positives. Use this if you just want a safety net.

```yaml
invariants:
  process:
    - tool_blocklist:
        tools:
          - "rm -rf /*"
          - "rm --no-preserve-root"
          - "curl|bash"
          - "wget|bash"
          - "*--no-verify"
        scope: session
```

### partner-mode.yaml

All 6 operators (minus allowlist). Designed to compress `CLAUDE.md` by encoding process rules as formal contracts:

- `must_precede`: Challenge before recommendation
- `must_state`: State cost before paid API calls
- `tool_blocklist`: Destructive tools blocked
- `context_budget`: 60K tokens per turn cap
- `process_drift`: JSD drift at 0.30 threshold
- `judge_predicate`: L99 conviction check (20% sample rate)

### full-governance.yaml

All 7 operators + ABC hard/soft constraints + drift/reliability config. Use for production-grade governance.

---

## How It Works

The hook intercepts Claude Code's event stream:

| Claude Code Event | Type-C Event | Action |
|---|---|---|
| `PreToolUse` | `PreAction` | Evaluate → ALLOW / BLOCK / MODIFY |
| `PostToolUse` | `PostAction` | Update drift + Θ |
| `UserPromptSubmit` | `TurnStart` | Mark turn begin |
| `Stop` | `TurnEnd` | Evaluate soft constraints |
| `SessionStart` | `SessionStart` | Load contract, compile AST |
| `SessionEnd` | `SessionEnd` | Final Θ score + drift report |

**Fail-safe:** If the hook encounters any internal error (missing contract env, broken YAML), it returns `allow` — never blocks on internal failure.

---

## Hook Interaction with Existing Hooks

- The `00-` prefix ensures AgentAssert runs first
- Existing hooks continue to work — AgentAssert doesn't replace them
- Use `AGENTASSERT_CONTRACT` env var to point to your contract

---

## Environment Variable

```bash
export AGENTASSERT_CONTRACT=/path/to/contract.yaml
```

Set before starting Claude Code. The hook reads this env var to find the contract.

---

## Case Study

See [Case Study](case-study.md) for real measurements:
- **CLAUDE.md reduced by 47.8%** (49,636 → 25,920 bytes)
- **Process rules compressed by 96%** (31,322 → 1,203 bytes)
- All behavioral rules moved from prompt to formal contract
