Execute shell commands on target hosts using Ansible. Returns complete results (rc, stdout, stderr) for each host.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- REQUIRED: Call check_host_status before this tool to verify:
  1. Host is reachable via SSH.
  2. Python is installed (required for the shell module).
  If Python is not installed, run playbook_bootstrap_tsc_environment first.

## Command Formatting Rules
1. Wrap arguments in single quotes to avoid escaping issues. Example: `find /tmp -name '*.json'`
2. If double quotes are required, escape them using backslashes. Example: `find /tmp -name \"*.json\"`
3. Do not use complex nested quotes. Simplify the command logic instead.
4. If you see 'Blacklisted high-risk command' warning, stop immediately and report to user.

## Return Value
Returns execution results including rc, stdout, and stderr for each host.

{{POLLING_RULES}}

## Usage Example
```json
{
  "targets": ["web-server-01", "db-server-02"],
  "command": "ls -la /var/log"
}
```
