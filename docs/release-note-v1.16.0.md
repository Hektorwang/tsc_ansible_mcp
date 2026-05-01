# Release Note v1.16.0

2026-05-01

## Summary

This release focuses on code quality, LLM behavior control, and maintainability improvements. No new features or breaking changes.

---

## Changes

### 1. Bug Fix: ansible_shell Returns Incorrect Results (rc: -1, status: failed)

**Problem**: When `ansible_shell` executed successfully on all target hosts, the MCP client received a response showing all hosts failed with `rc: -1` and `status: "failed"`. The task log correctly recorded `Status: success`, but the saved result JSON and the response returned to the caller contained all hosts as failed with empty stdout/stderr.

**Root Cause**: Two related issues:
- `ansible_shell` returned a result structure missing `success_hosts`, `failed_hosts`, and `summary` fields. `run_playbook` correctly builds these fields via `_build_summary_result`, but `ansible_shell` bypassed that method.
- `_parse_result` initializes each host with `{"rc": -1, ...}` as a default value, relying on `runner_on_ok` events to overwrite. When events were not matched, the defaults were preserved as the final result.

**Fix**:
- `ansible_shell` now uses `_build_summary_result` to build the complete result structure, consistent with `run_playbook`.
- Added `result.stats` fallback: when `_parse_result` cannot match `runner_on_ok` events (host `rc` remains `-1`), the method checks `ansible_runner`'s `stats.ok` dict. If the host has ok records, `rc` is corrected to `0`.
- Added `elapsed` field to per-host results.

**Files changed**: `lib/executor.py`

---

### 2. Bug Fix: Debug Playbook Cache Shows Unsubstituted Variables

**Problem**: `logs/debug/{task_id}/playbook.yml` showed `api_url: "http://localhost:8500/..."` instead of the actual injected value (e.g., `http://192.168.3.252:8500/...`). The debug file cached the raw playbook file content before `extravars` injection.

**Fix**: When caching the playbook file in debug mode, `extravars` values are now substituted into the content before writing. Both `{{ var_name }}` and `{{var_name}}` formats are replaced.

**Files changed**: `lib/executor.py` (`_run_ansible`)

---

### 3. Improvement: Tool Description and Instruction Externalized to Markdown Files

**Problem**: All MCP tool `description` strings and `MCP_INSTRUCTIONS` were hardcoded as Python string literals inside source files. This made them difficult to read, edit, and review.

**Change**: Extracted all tool descriptions and global instructions to standalone Markdown files:

```
etc/
  instructions.md                    # Global MCP instructions (MCP_INSTRUCTIONS)
  tool_descriptions/
    _polling_rules.md                # Shared polling rules fragment ({{POLLING_RULES}} placeholder)
    _playbook_prerequisites.md       # Shared playbook prerequisites block
    ansible_shell.md
    ansible_copy.md
    ansible_fetch.md
    check_host_status.md
    get_result.md
    get_host_detail.md
    change_ssh_password.md
    change_ssh_port.md
```

A new `lib/tool_description_loader.py` module handles loading and `{{POLLING_RULES}}` placeholder substitution at startup. Files are read once and cached in memory.

**Files changed**:
- `lib/tool_description_loader.py` (new)
- `etc/instructions.md` (new)
- `etc/tool_descriptions/*.md` (new)
- `lib/mcp_tools/ansible_shell.py`
- `lib/mcp_tools/ansible_copy.py`
- `lib/mcp_tools/ansible_fetch.py`
- `lib/mcp_tools/check_host_status.py`
- `lib/mcp_tools/task_results.py`
- `lib/mcp_tools/change_ssh_password.py`
- `lib/mcp_tools/change_ssh_port.py`
- `lib/server.py`

---

### 4. Improvement: Strict LLM Polling Behavior Rules

**Problem**: When a task returned `status: "running"`, the LLM would sometimes report the running status to the user and wait for instructions, rather than automatically polling until completion.

**Change**: All tools that can return `status: "running"` now include explicit MUST/MUST NOT rules in their descriptions:

- MUST: Call `get_result(task_id)` every 60 seconds until status is no longer "running".
- MUST: Present the final result to the user only after status is no longer "running".
- MUST NOT: Analyze or speculate on the cause of the delay.
- MUST NOT: Ask the user for instructions or suggest manual intervention.
- MUST NOT: Change the polling interval.
- MUST NOT: Report partial or intermediate results to the user.
- MUST NOT: Proceed to any next step until the final result is received.
- MUST NOT: Stop polling because status has not changed across multiple polls.

The same rules are added to `MCP_INSTRUCTIONS` as global behavior rules with highest priority.

**Files changed**: `etc/instructions.md`, `etc/tool_descriptions/_polling_rules.md`, `etc/tool_descriptions/get_result.md`, `lib/execution_service.py`

---

### 5. Improvement: Startup Warning for Missing ansible-playbook in PATH

**Problem**: When the server was started without sourcing `tsc_profile`, `ansible_runner` could not find `ansible-playbook` via subprocess (rc=127), with no clear error message at startup.

**Fix**: Added a startup check in `bin/server.py`. If `ansible-playbook` is not found in PATH, a warning is printed to stderr immediately at startup.

**Files changed**: `bin/server.py`
