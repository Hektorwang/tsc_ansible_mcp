# Playbook: bootstrap_tsc_environment

## Description
Bootstrap TSC environment including tsc_tools and tsc_python. Use this tool if check_host_status reports that tsc_tools or tsc_python are not installed.

## Parameters
- api_url (string, optional): API endpoint for package download (default: http://localhost:8500/api/v1/packages/download).

## Use Cases
- Install tsc_tools and tsc_python on target hosts
- Bootstrap TSC environment on new servers
- Automate package installation via API
- Detect system distro and arch automatically

## Example
```json
{
  "targets": ["192.168.1.10"]
}
```

## Notes
- Does not require Python on target hosts (uses raw/shell modules)
- Automatically detects system distro and architecture
- Checks existing installation status before proceeding
- Retries up to 3 times if download fails
- Supports HTTPS with -k flag
