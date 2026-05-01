# Bugfix Requirements Document

## Introduction

`ansible_shell` 执行成功后，MCP 客户端收到的响应显示所有主机均失败（`rc: -1`，`status: "failed"`）。
任务日志记录的状态为 `success`，但保存的结果 JSON 及返回给调用方的数据中，所有主机的 `rc` 均为 `-1`，`status` 为 `"failed"`。

该 bug 由两个相互关联的问题共同导致：

1. `ansible_shell` 返回的结构缺少 `success_hosts`、`failed_hosts`、`summary` 字段（`run_playbook` 通过 `_build_summary_result` 正确构建了这些字段，但 `ansible_shell` 绕过了该方法）。
2. `_parse_result` 将每台主机初始化为 `{"rc": -1, ...}` 作为默认值；若 `runner_on_ok` 事件未被正确匹配，这些默认值将被保留并作为最终结果输出。任务日志中 `Success: 0, Failed: 0` 证实了事件未被匹配的情况确实发生。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `ansible_shell` 在所有目标主机上执行成功（Ansible runner 返回 `rc=0`）THEN 系统将所有主机的结果记录为 `rc: -1`、`status: "failed"`

1.2 WHEN `ansible_shell` 执行完成后 THEN 系统返回的结果结构缺少 `success_hosts`、`failed_hosts`、`summary` 字段

1.3 WHEN `_run_ansible` 中的事件统计未匹配到 `runner_on_ok` 事件（`Success: 0, Failed: 0`）THEN `_parse_result` 保留所有主机的默认值 `rc: -1`，导致结果被误判为全部失败

1.4 WHEN `ansible_shell` 返回缺少 `success_hosts` 字段的结果 THEN `task_result_store.get_result(status='success')` 和 `get_result(status='failed')` 无法正确过滤主机，因为过滤逻辑依赖 `success_hosts` 字段

### Expected Behavior (Correct)

2.1 WHEN `ansible_shell` 在所有目标主机上执行成功 THEN 系统 SHALL 返回所有主机 `rc: 0`、`status: "success"` 的结果

2.2 WHEN `ansible_shell` 执行完成后 THEN 系统 SHALL 返回包含 `success_hosts`、`failed_hosts`、`summary`（含 `total`、`success`、`failed` 字段）的完整结果结构

2.3 WHEN `runner_on_ok` 事件未被 `_parse_result` 匹配时 THEN 系统 SHALL 提供回退机制，通过 `ansible_runner` 的 `result.stats` 或其他可靠来源正确判断主机执行状态，而非保留 `rc: -1` 默认值

2.4 WHEN `ansible_shell` 返回结果后 THEN 系统 SHALL 使用与 `run_playbook` 一致的 `_build_summary_result` 方法（或等效逻辑）构建完整的结果结构

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `ansible_shell` 在部分主机上执行失败（真实失败，非事件匹配问题）THEN 系统 SHALL CONTINUE TO 将这些主机标记为 `status: "failed"`，`rc` 为实际返回码

3.2 WHEN `ansible_shell` 遇到高风险命令拦截时 THEN 系统 SHALL CONTINUE TO 返回所有主机 `rc: -1`、`error_type: "high_risk_command"` 的失败结果

3.3 WHEN `ansible_shell` 遇到主机忙碌（host busy）时 THEN 系统 SHALL CONTINUE TO 返回所有主机 `rc: -1`、`error_type: "host_busy"` 的失败结果

3.4 WHEN `ansible_shell` 遇到主机不在 inventory 中时 THEN 系统 SHALL CONTINUE TO 返回所有主机 `rc: -1`、`error_type: "host_not_in_inventory"` 的失败结果

3.5 WHEN `run_playbook` 执行时 THEN 系统 SHALL CONTINUE TO 使用现有的 `_build_summary_result` 逻辑，行为不受本次修复影响

3.6 WHEN `task_result_store.get_result(task_id, status='failed')` 被调用时 THEN 系统 SHALL CONTINUE TO 依据 `success_hosts` 字段正确过滤并返回失败主机列表

---

## Bug Condition (Pseudocode)

**Bug Condition Function** — 识别触发 bug 的输入：

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type AnsibleShellExecution
  OUTPUT: boolean

  // 当 ansible_shell 执行完成，且 runner_on_ok 事件未被 _parse_result 正确匹配时触发
  RETURN X.ansible_runner_rc = 0
     AND X.parsed_results 中所有主机的 rc = -1  // 默认值未被覆盖
END FUNCTION
```

**Property: Fix Checking**

```pascal
FOR ALL X WHERE isBugCondition(X) DO
  result ← ansible_shell'(X)
  ASSERT result.status IN ["success", "partial_success"]
  ASSERT EXISTS host IN result.success_hosts WHERE result.results[host].rc = 0
  ASSERT "success_hosts" IN result
  ASSERT "failed_hosts" IN result
  ASSERT "summary" IN result
END FOR
```

**Property: Preservation Checking**

```pascal
FOR ALL X WHERE NOT isBugCondition(X) DO
  // 真实失败、高风险拦截、主机忙碌等场景
  ASSERT ansible_shell(X) = ansible_shell'(X)
END FOR
```
