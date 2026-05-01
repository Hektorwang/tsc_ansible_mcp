## Handling "running" Status
If status is "running":
- MUST: Call get_result(task_id) every 60 seconds until status is no longer "running".
- MUST: Present the final result to the user only after status is no longer "running".
- MUST NOT: Analyze or speculate on the cause of the delay.
- MUST NOT: Ask the user for instructions or suggest manual intervention.
- MUST NOT: Change the polling interval.
- MUST NOT: Report partial or intermediate results to the user.
- MUST NOT: Proceed to any next step until the final result is received.
