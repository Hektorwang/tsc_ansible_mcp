Check host architecture, distribution, tsc_tools and tsc_python installation status.

## Prerequisites
- Target hosts must be configured in inventory.yml first.

## Return Value
Returns detection results for each host including architecture, distribution, and installation status of tsc_tools and tsc_python.

{{POLLING_RULES}}

## Usage Example
```json
{
  "targets": ["web-server-01", "db-server-02"]
}
```

## Note
If tsc_tools or tsc_python are not installed, use the bootstrap_tsc_environment playbook to install them.
