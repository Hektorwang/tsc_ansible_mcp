## Prerequisites
- Target hosts must be configured in inventory.yml first.
- REQUIRED: Call check_host_status before this tool to verify:
  1. Host is reachable via SSH.
  2. Python is installed (required for playbook execution).
  If Python is not installed, run playbook_bootstrap_tsc_environment first.

{{POLLING_RULES}}
