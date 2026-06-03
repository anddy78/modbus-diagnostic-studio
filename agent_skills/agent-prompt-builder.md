# Skill: Agent Prompt Builder

Use this skill when creating prompts for Codex, DeepSeek, Roo, Gemini or other coding agents.

Prompt rules:
- One task per prompt.
- Give the recommended mode.
- Give the exact scope.
- Define files allowed to change.
- Define files not allowed to change.
- Include stop conditions.
- Ask for validation commands and results.
- Ask for diff summary.
- Avoid broad "improve everything" prompts.
- Prefer diagnosis before implementation for risky changes.

For this project:
- Commands must be PowerShell.
- The repo is new and independent.
- Do not modify `modbus_meter_bridge`.
- Do not implement code beyond requested scope.
- Do not build GUI before core modules and tests.
- Sniffer must never transmit.

Recommended modes:
- Architect: planning only.
- Auditor: read-only review, no commands.
- Debug: read-only commands allowed.
- Code: minimal implementation.
- Orchestrator: split large tasks into smaller prompts.
