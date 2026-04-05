# TSC_ANSIBLE_MCP 技术规格说明

## 1. 技术约束

### 1.1 运行环境

- `python` 版本: `3.13`
- 本地 `bash` 版本: `5+`
- 目标主机 `bash` 版本: `4+`

### 1.2 必须

- 必须使用`半角`标点符号
- python 必须`面向对象`
- 必须使用 `pathlib` 标准库操作路径
- 必须使用 `loguru` 管理日志, 在 `lib` 下封装日志模块 `tsc_logger.py`
- 数据库管理必须使用 `orm`
- 若有 api 接口必须提供 `swagger`
- `requests` 必须使用 `session`
- `mcp` 必须对工具提供 `instruction`
- 读取 `yaml` 必须使用 `yaml.safe_load()` 或 `yaml.safe_load_all()`
- python, typescript 必须使用 Docstrings
- javascript 必须使用 JSDoc
- python 必须使用 type hint

### 1.3 优先选择

- 重型项目后端优选 `django`, 轻型项目后端优选 `fastapi`
- 接口选择: `restful` > `rpc`, `异步` > `同步`
- 优先选择使用 `sqlalchemy` + `pandas` 操作数据库
- 配置文件格式优先选择顺序: `toml` > `ini` > `yaml` > `json` > `python dict`
- `MCP` 服务优先选择 `Streamable HTTP` > `SSE`
- python 和 shell 优先选择不用 `eval` 的方式, 若要用, **必须**提示我人工确认该语句
- 非必须双向交互场景不考虑 `websocket`

### 1.4 禁止

- 禁止使用 `emoji`
- 禁止画 `ascii文字图`, 若有必要用 `mermaid` 流程图语法
- python 禁止`面向过程`
- 数据库管理禁止使用`裸sql`
- python 禁止使用 `pickle`
- 禁止使用 `os.path`
- 禁止使用 `typescript`
- 禁止使用`全角`标点符号

### 1.5 代码格式化及校验(若无法通过校验, 提示我人工处理)

- python 脚本通过 `mypy` 校验,
- python 脚本通过 `black` 格式化
- python 脚本通过 `pylint` 校验
- shell 脚本通过 `dev_tools/shfmt` 格式化
- shell 脚本通过 `dev_tools/shellcheck` 校验
- ansible 剧本通过 `ansible-lint` 校验
- js 通过 `eslint` 校验

## 2. 路径约束

- `venv/`: 本工具 `python` 虚环境
- `bin/`: 本工具脚本, 可执行文件
- `doc/`: 设计文档
- `tmp`: 临时文件
- `logs/`: 日志文件
- `lib/`: 库/包文件
- `test/`: 测试文件
- `dev_tools/`: 开发辅助工具, 如
- `roles`, `playbooks/`, `retries`, `ansible.cfg`: ansible 相关文件路径
- `pylintrc`: `pylint` 配置文件
- `pyproject.toml`: `mypy` 配置文件
- `.eslintrc.js`: `eslint` 配置文件
- `etc/inventory.yml`: inventory配置
- `etc/tsc_ansible_mcp.toml`: 主配置文件
- `logs/tsc_ansible_mcp.db`: SQLite 数据库

## 3. 目标服务器基础运行环境

### 3.1 tsc_tools

#### 3.1.1 tsc_tools 安装包

nginx `base_url`, `分发路径` 可在主配置文件配置

| 属性       | 值                                                 |
| ---------- | -------------------------------------------------- |
| 安装包格式 | `tsc_tools-{version}-{arch}-{date}.sh`             |
| 分发方式   | `nginx` 静态文件服务                               |
| nginx 服务 | 本机环境 `http://192.168.19.22` (主配置文件可配置) |
| 分发路径   | `/tsc_tools-2.0.3.beta10-noarch-20260210.sh`       |

**安装包 URL 示例**：

```text
http://192.168.19.22/tsc_python-0.9.5-Redhat-x86_64-20260330.sh
```

#### 3.1.2 安装后路径

| 路径            | 说明                                                            |
| --------------- | --------------------------------------------------------------- |
| 安装根目录      | `/home/tsc/tsc_tools/micromamba/envs/tsc_python`                |
| Python 解释器   | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`    |
| Python 版本链接 | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3.13` |

#### 3.1.3 幂等性检查顺序

执行 `tsc_tools` 安装前，按以下方法检查是否已安装：

1. `test -d /home/tsc/tsc_tools/`
2. `test -f /home/tsc/tsc_tools/release-note.md`

若任一检查通过，则跳过安装。

### 3.2. Python 环境规格

#### 3.2.1 tsc_python 安装包

| 属性        | 值                                                 |
| ----------- | -------------------------------------------------- | --- |
| 安装包格式  | `tsc_python-{version}-{distro}-{arch}-{date}.sh`   |
| python 版本 | `3.13`                                             |
| 分发方式    | `nginx` 静态文件服务                               |
| nginx 服务  | 本机环境 `http://192.168.19.22` (主配置文件可配置) |
| 分发路径    | `/tsc_python-0.9.5-redhat-x86_64-20260330.sh`      |     |

**安装包 URL 示例**：

```text
http://192.168.19.22/tsc_python-0.9.5-Redhat-x86_64-20260330.sh
```

### 3.2.2 安装后路径

| 路径            | 说明                                                            |
| --------------- | --------------------------------------------------------------- |
| 安装根目录      | `/home/tsc/tsc_tools/micromamba/envs/tsc_python`                |
| Python 解释器   | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`    |
| Python 版本链接 | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3.13` |

### 3.2.3 幂等性检查顺序

执行 Python 安装前，按以下顺序检查是否已安装：

1. 系统 Python：`which python3`
2. tsc_python：`test -f /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`

若任一检查通过，则跳过安装。

## 4. SSH 认证规格

### 4.1 认证方式优先级

依据优先级 fallback

| 优先级 | 认证方式      | 参数       | SSH 选项                                                              |
| ------ | ------------- | ---------- | --------------------------------------------------------------------- |
| 1      | 密码认证      | `password` | 增加`-o PreferredAuthentications=password -o PubkeyAuthentication=no` |
| 2      | ~/.ssh/config | 无需参数   | 操作系统默认行为                                                      |
| 3      | SSH 密钥      | 无需参数   | 操作系统默认行为                                                      |

### 4.2 SSH 连接参数

| 参数                  | 默认值           | 说明                   |
| --------------------- | ---------------- | ---------------------- |
| 端口                  | 继承操作系统默认 | 可通过 `port` 参数覆盖 |
| 用户                  | root             | 可通过 `user` 参数覆盖 |
| 超时                  | 600s             | 主配置文件 中          |
| StrictHostKeyChecking | no               | 禁用主机密钥检查       |
| ForwardX11            | no               | 禁用 X11 转发          |
| GSSAPIAuthentication  | no               | 禁用 GSS               |
| VerifyHostKeyDNS      | no               | 禁用dns检查            |
| StrictHostKeyChecking | no               | 禁用服务端指纹检查     |
| UserKnownHostsFile    | no               | 禁用指纹记录           |

### 4.3 密码认证特殊处理

当使用密码认证时，必须添加以下 SSH 选项以避免尝试密钥认证：

```bash
-o PreferredAuthentications=password -o PubkeyAuthentication=no
```

**原因**：开发机器可能存在需要密码的 SSH 密钥，默认会尝试密钥认证导致卡住。

## 5. 归一化映射规格

### 5.1 架构映射

| 原始值    | 归一化值  |
| --------- | --------- |
| `aarch64` | `aarch64` |
| `arm64`   | `aarch64` |
| `x86_64`  | `x86_64`  |
| `amd64`   | `x86_64`  |

### 5.2 发行版映射

| 原始值           | 归一化值 |
| ---------------- | -------- |
| `rhel`           | `RedHat` |
| `centos`         | `RedHat` |
| `almalinux`      | `RedHat` |
| `rocky`          | `RedHat` |
| `fedora`         | `RedHat` |
| `ubuntu`         | `Debian` |
| `debian`         | `Debian` |
| `linuxmint`      | `Debian` |
| `arch`           | `Arch`   |
| `manjaro`        | `Arch`   |
| `alpine`         | `Alpine` |
| `suse`           | `Suse`   |
| `opensuse`       | `Suse`   |
| `openeuler`      | `Euler`  |
| `fitserveros`    | `Euler`  |
| `fitstarryskyos` | `Euler`  |
| `hce`            | `Euler`  |
| `ningos`         | `Euler`  |

## 6. 执行参数规格

### 6.1 并发控制

| 参数    | 默认值 | 说明             |
| ------- | ------ | ---------------- |
| `forks` | 10     | 同时连接的主机数 |

### 6.2 超时控制

| 参数                 | 默认值 | 最大值 | 说明             |
| -------------------- | ------ | ------ | ---------------- |
| `default_timeout`    | 600s   | -      | 默认执行超时     |
| `max_timeout`        | 3600s  | -      | 最大允许超时     |
| `task_timeout`       | 600s   | -      | Ansible 任务超时 |
| `connection_timeout` | 30s    | -      | SSH 连接超时     |

### 6.3 重试策略

| 场景     | 重试次数 | 重试间隔 |
| -------- | -------- | -------- |
| 网络检查 | 3        | 5s       |

## 7. 输出格式规格

### 7.1 任务状态值

| 状态              | 说明         |
| ----------------- | ------------ |
| `pending`         | 任务待执行   |
| `running`         | 任务执行中   |
| `success`         | 任务成功完成 |
| `partial_success` | 部分主机成功 |
| `failed`          | 任务失败     |

### 7.2 主机状态值

| 状态        | 说明                     |
| ----------- | ------------------------ |
| `ready`     | 网络、SSH、Python 均正常 |
| `not_ready` | 至少一项检查失败         |
| `partial`   | 检查结果不完整           |
| `unknown`   | 无法确定状态             |

## 8. 高危命令黑名单

主配置文件配置命令黑名单, 拦截高危命令执行

- rm
- unlink
- halt
- shutdown
- mkfs
- parted
- reboot
- poweroff
- init
- dd
- format
- shred

**例外**：脚本中内含的这些操作无需屏蔽。

## 9. 依赖版本规格

| 依赖           | 版本要求  |
| -------------- | --------- |
| Python         | >= 3.13   |
| ansible-core   | >= 2.15.0 |
| ansible-runner | >= 2.3.0  |
| Flask          | >= 3.0.0  |
| Flask-RESTful  | >= 0.3.10 |
| pandas         | >= 2.0.0  |
| SQLAlchemy     | >= 2.0.0  |
| loguru         | >= 0.7.0  |

## 10. 测试环境规格

### 10.1 测试主机

| 属性 | 值                      |
| ---- | ----------------------- |
| IP   | `192.168.19.35`         |
| 端口 | `3204`                  |
| 用户 | `root`                  |
| 系统 | `CentOS Linux 7`        |
| 内核 | `3.10.0-693.el7.x86_64` |
| 架构 | `x86_64`                |

### 10.2 测试连接命令样例

```bash
sshpass -vp JScz-320400 ssh root@192.168.19.35 -p 3204 -o 'PreferredAuthentications=password' -o 'PubkeyAuthentication=no'
```

## 11. 相关文档

- [PRD 文档](./PRD.md)
- [架构设计文档](./ARCHITECTURE.md)
- [API 参考文档](./API-REFERENCE.md)
- [Agent 使用指南](./AGENT.md)
