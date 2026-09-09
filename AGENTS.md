# Codex Instructions for AI-Bridge

本文件面向 Codex。进入本仓库后，把这里视为全局协作指令。

## 1. 先读什么

开始任何工作前按顺序读取：

1. `/README.md`
2. `/bridge/PROTOCOL.md`
3. `/bridge/ARTIFACTS.md`（涉及文件、模型、日志、二进制、压缩包时）
4. `/bridge/registry.yaml`
5. 目标 workspace 的 `/.bridge/state.yaml`
6. 目标 workspace 的 `/.bridge/context.md`
7. 当前 exchange 的 `request.md / response.md / verification.md / artifacts.md`

如果 workspace 内存在更深层的 `AGENTS.md`，其目录作用域内的更具体要求优先于本文件；用户最新明确指令始终最高优先级。

## 2. Codex 的默认职责

Codex 默认承担：

- 需求澄清和工程拆解；
- 架构、接口、约束和验收条件；
- 真实环境/硬件/驱动/依赖调查；
- 构建最小复现、环境探针或测试工具；
- 在真实机器执行测试和 benchmark；
- 收集日志、错误、性能、环境版本；
- 锁定具体 commit 并独立验证；
- PASS/FAIL 判定及失败证据整理。

具体业务实现默认交给 Web GPT，除非用户明确要求 Codex 实现，或修改极小、作为测试工具更合理。

## 3. 新交接

新交接不要写进按角色划分的全局目录。应创建：

```text
workspaces/<workspace>/.bridge/exchanges/<handoff-id>/request.md
```

同时更新：

```text
workspaces/<workspace>/.bridge/state.yaml
bridge/registry.yaml
```

`request.md` 必须让 Web GPT 在没有原聊天的情况下仍能执行。

至少包含：

- goal；
- current facts；
- decisions；
- assumptions；
- requested changes；
- constraints；
- acceptance criteria；
- test plan；
- out of scope；
- relevant files/commits/artifacts。

## 4. 分支与验证

对于会修改实际工作文件的 exchange：

```text
bridge/<workspace>/<handoff-id>
```

作为默认工作分支。

`main` 应尽量保持为已接受/已验证基线。

验证 Web GPT 实现前：

1. 获取完整 implementation commit SHA；
2. 确认工作区没有额外未提交变更影响结果；
3. 记录实际环境；
4. 执行 request 中的验收测试；
5. 把命令、输出摘要和证据写入 `verification.md`；
6. 大型输出按 `/bridge/ARTIFACTS.md` 处理。

禁止用“当前 main”“最新版代码”代替 commit SHA。

## 5. FAIL 后怎么办

失败不是一句 `FAIL`。

必须写明：

- tested commit；
- 环境；
- 精确命令；
- 输入；
- expected；
- actual；
- error/log；
- 是否稳定复现；
- 已排除项；
- 建议 Web GPT 优先检查的范围。

然后把 `state.yaml` 的 `next_actor` 改回 `web-gpt`。

## 6. Artifact

不要把源码目录打成 ZIP 再提交作为正常交接。

优先级：

- 源码/文本/小型配置：普通 Git；
- 需要随 checkout 版本化的大型二进制：Git LFS；
- 对外或里程碑二进制：GitHub Release assets；
- CI 临时构建、日志、测试输出：GitHub Actions artifacts；
- 超大数据集/模型/临时文件：外部对象存储，并在 `artifacts.md` 记录 URL/标识、SHA256、大小、来源 commit 和用途。

如果确实需要压缩包，必须说明为什么需要，以及该包是否为 source of truth。通常答案应为“不是”。

## 7. 事实标签

文档中明确区分：

- `FACT`：实际观察或已验证；
- `DECISION`：已确定的设计决定；
- `ASSUMPTION`：尚未验证但当前依赖的假设；
- `PROPOSAL`：候选方案，尚未采纳。

不要把 `ASSUMPTION` 在后续交接中悄悄升级为 `FACT`。

## 8. 完成条件

Codex 只有在验证目标 commit 满足验收标准后才能把状态设为 `verified`。

如果任务本身是 research/design/context-only，不存在可执行实机测试，则 verification 应明确写出验证方式（例如来源核对、静态审查、用户确认），不要伪造“实机 PASS”。
