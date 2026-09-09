# AI-Bridge Protocol v2

本协议定义 Web GPT 与 Codex 通过 GitHub 进行通用、可恢复、可验证交接的方式。

## 1. 设计目标

协议必须同时满足：

- **通用**：不绑定某个技术栈或单一项目；
- **自包含**：失去聊天上下文仍能继续；
- **并行安全**：多个 workspace/exchange 可同时进行；
- **Git-native**：利用 branch、commit、diff、PR，而不是用压缩包模拟版本控制；
- **可验证**：每个结论都能关联环境、命令、commit 和证据；
- **低维护**：状态文件只保存当前路由，历史由 Git 保留。

## 2. 三层模型

### Workspace

一个长期工作域：代码库、实验、调查、工具、硬件验证、文档或其它连续主题。

路径：

```text
workspaces/<workspace>/
```

实际工作文件直接位于该目录中，不要求统一语言或固定 `src/` 结构。

### Workspace Bridge State

每个 workspace 的协议元数据：

```text
workspaces/<workspace>/.bridge/
├─ state.yaml
├─ context.md
└─ exchanges/
```

`state.yaml` 只描述当前状态；`context.md` 保存长期有效事实和设计决定。

### Exchange

一次有明确发送方、接收方和目标的交接单元：

```text
.bridge/exchanges/<handoff-id>/
├─ request.md
├─ response.md
├─ verification.md
├─ artifacts.md
└─ evidence/
```

同一 exchange 的多轮修改不创建 `r01/r02` 目录；直接更新这些文件，由 Git commit 历史保留版本。`verification.md` 追加每次验证记录。

## 3. Handoff ID

禁止使用全仓库 `001/002/003` 作为唯一标识，因为并行 workspace 会冲突。

推荐：

```text
YYYYMMDDTHHMMSSZ-<short-slug>
```

例如：

```text
20260909T123500Z-engine-compat
```

要求：

- UTC；
- 全仓库唯一；
- slug 简短可读；
- 不依赖聊天编号。

## 4. 状态机

`state.yaml` 的主要状态：

```text
idle
ready_for_web_gpt
ready_for_codex
verification_failed
verified
blocked
closed
```

`next_actor`：

```text
codex
web-gpt
user
none
```

典型转换：

```text
idle
  ↓ Codex request
ready_for_web_gpt
  ↓ Web GPT response + implementation commit
ready_for_codex
  ↓ Codex test FAIL
verification_failed
  ↓ next_actor=web-gpt
ready_for_web_gpt
  ↓ fix
ready_for_codex
  ↓ Codex PASS
verified
```

## 5. 角色边界

### Codex

负责“定义、落地测试环境、验证”：

- architecture；
- constraints；
- interfaces/contracts；
- environment；
- acceptance criteria；
- real-machine tests；
- benchmark；
- reproducibility；
- verification。

### Web GPT

负责“实现”：

- concrete code；
- refactor；
- fix；
- unit/integration test code；
- configs/scripts/docs needed by implementation；
- response documentation。

边界不是权限墙。必要时任何一方都可跨界，但必须在文档中声明做了什么，不能让下一方误以为修改来自另一方。

## 6. Request 规则

Codex 的 `request.md` 是 Web GPT 的执行合同。

必须自包含，至少覆盖：

- Goal
- Background only if necessary
- FACT / DECISION / ASSUMPTION / PROPOSAL
- Current baseline commit
- Relevant paths
- Required changes
- Interfaces/contracts
- Constraints
- Acceptance criteria
- Test plan
- Out of scope
- Artifact dependencies

验收必须尽量可执行。

坏：

```text
性能优化一下。
兼容性做好。
```

好：

```text
在指定环境下执行 command X；返回码必须为 0；
输入 Y 时输出必须满足 Z；
P95 latency < N ms；
不允许静默 fallback。
```

如果 request 在 Web GPT 开工后发生变化，不应静默重写原要求；在 `Amendments` 追加时间、作者和变更原因。

## 7. Response 规则

Web GPT 在 `response.md` 记录：

- source request；
- implementation commit；
- changed files；
- implementation summary；
- design deviations；
- checks actually run；
- not verified；
- known risks；
- artifact changes；
- exact commands for Codex。

禁止把“代码看起来正确”写成“目标机器已通过”。

## 8. Verification 规则

每次 Codex 验证追加一条 attempt：

```text
Attempt N
Tested commit
Environment
Commands
Acceptance item → PASS/FAIL
Measurements
Evidence
Observed issue
Conclusion
```

验证必须绑定完整 commit SHA。

如果失败，证据要足够让 Web GPT 不依赖原聊天即可继续修复。

如果通过：

- `state.status = verified`
- `state.next_actor = none`
- 设置 `accepted_commit`
- 更新 registry
- 将已验证工作合并回 `main`

## 9. Branch / PR 规则

### 默认

```text
main = accepted baseline
bridge/<workspace>/<handoff-id> = active exchange branch
```

推荐流程：

1. Codex 从 `main` 创建 exchange branch；
2. Codex 写 request；
3. Web GPT 在同一 branch 实现；
4. Codex 测试具体 implementation commit；
5. FAIL：继续 branch；
6. PASS：写 verification；
7. 通过 PR 或明确 merge 合入 `main`。

PR 对非 trivial 修改是推荐项，因为它天然提供 diff、讨论和 CI/status checks；但协议不强制所有微小 context-only 修改都开 PR。

不要在未验证时把 `main` 描述成“最终正确版本”。

## 10. Registry 与 State

`bridge/registry.yaml` 是入口索引，不保存详细历史。

每个 workspace 的 `state.yaml` 才是该 workspace 当前路由的 source of truth。

不要同时维护多份重复状态文本，以免漂移。

## 11. Context

`context.md` 只放长期有效信息：

- 已确认环境事实；
- 关键设计决定及原因；
- 稳定接口；
- 持久约束；
- 常用测试方法；
- 重要外部依赖。

不要把每次运行日志都堆进 context；短期信息属于 exchange，原始输出属于 evidence/artifact。

## 12. 证据

适合 Git 的小型证据可以放：

```text
evidence/*.txt
evidence/*.json
evidence/*.csv
evidence/*.md
```

图片或小型必要测试 fixture 也可正常 Git 跟踪，但不要把大量 frame、dump、构建目录长期提交到仓库。

大文件遵循 `ARTIFACTS.md`。

## 13. 冲突优先级

发生冲突时：

1. 用户最新明确指令；
2. 当前 exchange 的最新 Amendment；
3. 当前 exchange request；
4. workspace context/state；
5. workspace 内更深层 AGENTS.md；
6. 根 AGENTS.md / 本协议；
7. 旧 exchange / 历史聊天推断。

发现冲突应写入 exchange，不要静默猜测。

## 14. 安全

禁止提交：

- API keys / tokens；
- passwords；
- cookies/session；
- private keys；
- 未脱敏个人或内部敏感数据；
- 不应公开的大型原始数据。

使用 `.env.example` / config template，真实值留在安全环境。

## 15. 最小交接

极小工作也至少需要：

Codex → Web GPT：

```text
goal
baseline commit
required change
acceptance criteria
```

Web GPT → Codex：

```text
implementation commit
changed files
not verified
how to test
```

Codex → End/Web GPT：

```text
tested commit
test command/result
PASS or FAIL
next actor
```

做到这三步，即使聊天全部丢失，仍可从仓库恢复工作。
