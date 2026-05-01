Query execution details for a specific host.

## Purpose
Retrieve detailed execution results (rc, stdout, stderr, status) for a single host without loading all host results.

## Parameters
- task_id (required): Task ID to query.
- host (required): Host IP address to query.

## Return Value
Returns host execution details:
```json
{
  "task_id": "xxx",
  "host": "192.168.1.10",
  "rc": 1,
  "stdout": "",
  "stderr": "command not found",
  "status": "failed"
}
```

## Error Responses
- Task not found: {"task_id": "xxx", "status": "not_found", "message": "Task xxx not found"}
- Host not found: {"task_id": "xxx", "host": "1.1.1.1", "status": "not_found", "message": "Host not found in task results"}
- Task running: {"task_id": "xxx", "status": "running", "message": "Task is still running. Wait and try again"}

## Usage Example
```json
{"task_id": "abc-123", "host": "192.168.1.10"}
```
