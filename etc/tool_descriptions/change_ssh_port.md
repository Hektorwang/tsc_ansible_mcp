Change SSH port on target hosts with atomic inventory updates.

## Prerequisites
- Target hosts must be configured in inventory database first.
- User must be root on target hosts.
- Target hosts must use systemd as init system.

## Input Format
```json
{
  "hosts": ["host1", "host2"],
  "new_port": 2222
}
```

## Workflow
1. Validate input parameters (host count <= 50, port = 22 or 1024-65535)
2. Step 1: Run check_host_status on all hosts to get current ports
3. Step 2: Call external playbook change_ssh_port.yml (backup, modify config, test, reload, rollback on failure)
4. Step 3: Update inventory for successful hosts

## Return Value
Returns execution results for each host, including success/failure status and details.
