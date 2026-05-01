Change SSH password on target hosts with atomic inventory updates.

## Prerequisites
- Target hosts must be configured in inventory database first.
- User must be root on target hosts.
- Password must meet complexity requirements (8+ chars, digit, letter, special char).

## Input Format
```json
{
  "hosts": ["host1", "host2"],
  "new_password": "NewPass123!"
}
```

## Workflow
1. Validate input parameters (host count <= 50, password complexity)
2. Step 1: Run check_host_status on all hosts to get current environment
3. Step 2: Call external playbook change_ssh_password.yml (change password, local verification)
4. Step 3: Update inventory for successful hosts (playbook includes local verification)

## Return Value
Returns execution results for each host, including success/failure status and details.
