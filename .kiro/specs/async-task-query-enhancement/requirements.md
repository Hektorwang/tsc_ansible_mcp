# Requirements Document: Enhanced Async Task Query System

## Introduction

This feature enhances the existing async task execution system by implementing a structured three-tier query pattern. Currently, all async tools (ansible_shell, ansible_copy, ansible_fetch, check_host_status) return task_id and support basic result querying via get_result. This enhancement adds:

1. **Immediate validation response** with clear polling guidance for LLM agents
2. **Three-tier query pattern**: Task summary → Host list → Individual host details
3. **Structured statistics** showing success/failed host counts
4. **Individual host detail queries** by task_id + host IP

The goal is to provide LLM agents with clear, progressive access to task results without overwhelming context, while maintaining backward compatibility with existing implementations.

## Glossary

- **Task**: An asynchronous operation (shell command, file copy, file fetch, or host status check) executed across multiple target hosts
- **Task_ID**: Unique identifier (UUID) assigned to each task upon creation
- **Query_Service**: The enhanced get_result tool that provides three-tier query capabilities
- **Host_Result**: Execution result for a single host, including return code (rc), stdout, stderr, and status
- **Task_Summary**: High-level task information including overall status and success/failed host counts
- **LLM_Agent**: The AI agent that invokes MCP tools and interprets results
- **Polling**: Periodic querying of task status using task_id until completion
- **Task_Repository**: SQLite database storing task metadata and summary results
- **Result_Store**: JSON file storage for detailed host-level execution results

## Requirements

### Requirement 1: Immediate Task Validation and Response

**User Story:** As an LLM agent, I want to receive immediate validation feedback when I submit a task, so that I know whether my request is valid and can begin polling for results.

#### Acceptance Criteria

1. WHEN an async tool (ansible_shell, ansible_copy, ansible_fetch, check_host_status) receives a request, THE Tool SHALL validate all required parameters before creating the task
2. IF validation fails, THEN THE Tool SHALL return an error response with status "error" and a descriptive message
3. WHEN validation succeeds, THE Tool SHALL create a task_id and return it immediately
4. WHEN a task is created, THE Tool SHALL include polling guidance in the response message
5. THE polling guidance SHALL recommend checking task status every 30-60 seconds using get_result(task_id)
6. WHEN a task completes within 55 seconds, THE Tool SHALL return the complete result directly
7. WHEN a task exceeds 55 seconds, THE Tool SHALL return status "running" with the task_id and polling instructions

### Requirement 2: Task Summary Query (Tier 1)

**User Story:** As an LLM agent, I want to query a task's overall status and statistics, so that I can understand the big picture before diving into host details.

#### Acceptance Criteria

1. WHEN get_result is called with only task_id, THE Query_Service SHALL return a task summary
2. THE task summary SHALL include the task_id, overall status, total host count, success host count, and failed host count
3. WHEN the task is still running, THE Query_Service SHALL return status "running" with a message to poll again
4. WHEN the task is not found, THE Query_Service SHALL return status "not_found" with task_id
5. WHEN the task has no result data yet, THE Query_Service SHALL return status with a message indicating no result data
6. THE task summary SHALL NOT include individual host details (stdout, stderr, rc)
7. FOR ALL completed tasks, the sum of success_count and failed_count SHALL equal total_host_count

### Requirement 3: Host List Query with Status Filter (Tier 2)

**User Story:** As an LLM agent, I want to retrieve a list of hosts filtered by execution status, so that I can identify which hosts succeeded or failed without retrieving full details.

#### Acceptance Criteria

1. WHEN get_result is called with task_id and status="failed", THE Query_Service SHALL return all failed host results
2. WHEN get_result is called with task_id and status="success", THE Query_Service SHALL return all successful host results
3. THE failed host results SHALL include host IP, rc, stdout, stderr for each failed host
4. THE successful host results SHALL include host IP, rc, stdout, stderr for each successful host
5. THE response SHALL include total_failed or total_success count matching the number of returned hosts
6. WHEN no hosts match the status filter, THE Query_Service SHALL return an empty host list with count 0
7. THE status filter SHALL accept only "failed" or "success" as valid values

### Requirement 4: Individual Host Detail Query (Tier 3)

**User Story:** As an LLM agent, I want to query execution details for a specific host, so that I can investigate individual failures without retrieving all host results.

#### Acceptance Criteria

1. WHEN get_host_detail is called with task_id and host IP, THE Query_Service SHALL return the execution result for that specific host
2. THE host detail SHALL include host IP, rc, stdout, stderr, and execution status
3. WHEN the specified host is not found in the task results, THE Query_Service SHALL return status "not_found" with a descriptive message
4. WHEN the task_id is invalid, THE Query_Service SHALL return status "not_found" for the task
5. THE host IP parameter SHALL match exactly the host identifier used in the task execution
6. THE response SHALL include only the requested host's data, not other hosts

### Requirement 5: Enhanced Tool Response Guidance

**User Story:** As an LLM agent, I want clear instructions in tool responses, so that I know what to do next without guessing.

#### Acceptance Criteria

1. WHEN an async tool returns status "running", THE Tool SHALL include a message with the exact get_result call syntax
2. THE message SHALL specify the recommended polling interval (30-60 seconds)
3. WHEN get_result returns a task summary with failures, THE Query_Service SHALL include guidance on querying failed hosts
4. THE guidance SHALL mention using status="failed" to retrieve failed host details
5. WHEN get_result returns failed host list, THE Query_Service SHALL include guidance on querying individual host details
6. THE guidance SHALL mention using get_host_detail(task_id, host_ip) for specific host investigation
7. ALL guidance messages SHALL be concise (under 200 characters) to minimize token usage

### Requirement 6: Backward Compatibility

**User Story:** As a system maintainer, I want existing integrations to continue working, so that the enhancement does not break current functionality.

#### Acceptance Criteria

1. WHEN get_result is called with task_id only (no status parameter), THE Query_Service SHALL return the task summary (new behavior)
2. WHEN get_result is called with task_id and status="failed", THE Query_Service SHALL return failed host results (existing behavior preserved)
3. WHEN get_result is called with task_id and status="success", THE Query_Service SHALL return successful host results (enhanced from existing)
4. THE Task_Repository database schema SHALL remain unchanged
5. THE Result_Store file format SHALL remain unchanged
6. ALL existing async tools (ansible_shell, ansible_copy, ansible_fetch, check_host_status) SHALL continue to work without modification to their core logic
7. THE 55-second timeout behavior SHALL remain unchanged

### Requirement 7: Query Service Tool Registration

**User Story:** As a developer, I want the new query tools to be properly registered in the MCP server, so that LLM agents can discover and use them.

#### Acceptance Criteria

1. THE Query_Service SHALL register get_result as an MCP tool with updated description
2. THE Query_Service SHALL register get_host_detail as a new MCP tool
3. THE get_result tool description SHALL document all three query modes: summary, failed hosts, successful hosts
4. THE get_host_detail tool description SHALL document the task_id and host parameters
5. THE tool descriptions SHALL include usage examples for each query mode
6. THE tool descriptions SHALL specify required and optional parameters
7. THE tool descriptions SHALL be written in clear, concise language suitable for LLM interpretation

### Requirement 8: Error Handling and Edge Cases

**User Story:** As an LLM agent, I want clear error messages for invalid queries, so that I can correct my requests without confusion.

#### Acceptance Criteria

1. WHEN get_result is called with an invalid task_id format, THE Query_Service SHALL return status "error" with a descriptive message
2. WHEN get_result is called with an invalid status value (not "failed" or "success"), THE Query_Service SHALL return status "error" with valid options
3. WHEN get_host_detail is called with an invalid host IP format, THE Query_Service SHALL return status "error" with a descriptive message
4. WHEN a task has no hosts (empty target list), THE Query_Service SHALL return summary with total_host_count 0
5. WHEN a task is still running and get_host_detail is called, THE Query_Service SHALL return status "running" with a message to wait
6. WHEN the Result_Store file is missing but Task_Repository has the task, THE Query_Service SHALL return status "error" with a message about missing result file
7. ALL error messages SHALL include the task_id for traceability

### Requirement 9: Performance and Scalability

**User Story:** As a system operator, I want query operations to be efficient, so that the system can handle high query volumes without degradation.

#### Acceptance Criteria

1. WHEN get_result is called for task summary, THE Query_Service SHALL read only the Task_Repository (not the Result_Store file)
2. WHEN get_result is called with status filter, THE Query_Service SHALL read the Result_Store file once and filter in memory
3. WHEN get_host_detail is called, THE Query_Service SHALL read the Result_Store file once and extract only the requested host data
4. THE Query_Service SHALL NOT load all host results into memory when only summary is requested
5. FOR ALL query operations, response time SHALL be under 100ms for tasks with up to 100 hosts
6. THE Query_Service SHALL support concurrent queries without data corruption
7. THE Query_Service SHALL use file locking when reading Result_Store files to prevent race conditions

### Requirement 10: Documentation and Examples

**User Story:** As a developer integrating with this system, I want comprehensive documentation, so that I can understand the query patterns without reading source code.

#### Acceptance Criteria

1. THE system SHALL provide a usage guide document explaining the three-tier query pattern
2. THE usage guide SHALL include examples for each query tier with sample requests and responses
3. THE usage guide SHALL include a decision tree for when to use each query mode
4. THE usage guide SHALL document the polling workflow with timing recommendations
5. THE tool descriptions in MCP SHALL include at least one example per query mode
6. THE error messages SHALL be documented with their causes and resolutions
7. THE documentation SHALL be written in both English and Chinese (中英文双语)

