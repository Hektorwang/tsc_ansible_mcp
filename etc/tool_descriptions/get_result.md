Retrieve execution results for a task with three query modes.

## Query Modes

### Mode 1: Task Summary (status omitted)
Returns high-level statistics without host details.
Example: {"task_id": "xxx"}
Response: {
  "task_id": "xxx",
  "status": "completed",
  "total_hosts": 10,
  "success_count": 8,
  "failed_count": 2,
  "message": "Use get_result(task_id, status='failed') to see failed hosts"
}

### Mode 2: Failed Hosts List (status="failed")
Returns all failed hosts with details.
Example: {"task_id": "xxx", "status": "failed"}
Response: {
  "task_id": "xxx",
  "status": "completed",
  "failed_hosts": {"host_ip": {"rc": 1, "stdout": "", "stderr": "error"}},
  "total_failed": 2,
  "message": "Use get_host_detail(task_id, host_ip) for specific host investigation"
}

### Mode 3: Success Hosts List (status="success")
Returns all successful hosts with details.
Example: {"task_id": "xxx", "status": "success"}
Response: {
  "task_id": "xxx",
  "status": "completed",
  "success_hosts": {"host_ip": {"rc": 0, "stdout": "output", "stderr": ""}},
  "total_success": 8
}

## Parameters
- task_id (required): Task ID to query results for.
- status (optional): Status filter. Valid values: 'failed' or 'success'. If omitted, returns task summary.

## Polling Guidance
If status is "running":
- MUST: Call get_result(task_id) again after exactly 60 seconds.
- MUST NOT: Analyze or speculate on the cause of the delay.
- MUST NOT: Ask the user for instructions or suggest manual intervention.
- MUST NOT: Change the polling interval.
- MUST NOT: Proceed to any next step until the final result is received.
