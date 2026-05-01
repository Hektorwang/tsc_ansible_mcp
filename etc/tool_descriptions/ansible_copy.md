Copy files from local machine to target hosts. Returns complete results (rc, stdout, stderr) for each host.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- REQUIRED: Call check_host_status before this tool to verify:
  1. Host is reachable via SSH.
  2. Python is installed (required for the copy module).
  If Python is not installed, run playbook_bootstrap_tsc_environment first.

## Parameters
- targets (required): List of target hostnames or IPs.
- src (required): Local file path to copy from.
- dest (required): Remote file path to copy to.
- timeout (optional): Execution timeout in seconds.

## Return Value
Returns execution results including rc, stdout, and stderr for each host.

{{POLLING_RULES}}

## Usage Example
```json
{
  "targets": ["web-server-01"],
  "src": "/path/to/local/config.yml",
  "dest": "/etc/myapp/config.yml"
}
```
