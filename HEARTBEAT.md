# HEARTBEAT.md

Check session health. Alert only on issues. Silent otherwise.

## Auto-Checks

1. Context usage — If >80%, auto-compact
2. Stuck sessions — If any >5min unresponsive
3. API errors

## Response

- **No issues**: Reply ONLY "HEARTBEAT_OK". Nothing else.
- **Issues found**: Report specific problem

## Frequency

Let OpenClaw handle timing (typically ~30 min).