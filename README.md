# AI-Bridge

AI-Bridge 是一个专门用于 **GPT 网页版（Web GPT）与 Codex 之间进行工程交接** 的 GitHub 仓库。

它不是聊天记录仓库，而是一个可追踪、可复现、以 Git commit 为边界的工程协作通道。

核心分工：

- **Codex**：负责架构设计、任务拆解、环境/硬件约束、测试方案、实机运行和验证。
- **GPT 网页版**：负责阅读 Codex 的工程要求，完成具体代码实现、修改、补全和文档化。
- **GitHub**：作为双方唯一共享状态、代码、测试证据和交接文档的来源。

> 基本原则：**要求写进文档，代码写进仓库，测试绑定 commit，结论必须有证据。不要依赖另一方“记得之前聊过什么”。**

---

## 1. 标准工作流

一次任务使用一个固定 Task ID，例如 `001`、`002`、`003`。

标准闭环：

```text
用户提出目标
    ↓
Codex：分析需求 / 设计架构 / 明确环境与验收标准
    ↓
handoffs/codex/NNN-task.md
    ↓
GPT 网页版：读取任务文档和现有代码
    ↓
GPT 网页版：编写或修改具体代码
    ↓
handoffs/web-gpt/NNN-result.md
    ↓
Codex：拉取并锁定 GPT 提交的 commit
    ↓
Codex：在真实目标环境运行测试
    ↓
handoffs/codex/NNN-verification.md
    ↓
PASS → 任务结束
FAIL → Codex 写明复现条件和失败证据 → GPT 下一轮修复
```

任何一方都不应只在聊天中给出关键结论而不写入仓库。

---

## 2. 角色职责

### 2.1 Codex 的职责

Codex 默认负责 **“决定该怎么做，以及确认它是否真的能工作”**。

主要职责：

1. 理解目标和实际使用场景。
2. 设计总体架构、模块边界、接口和数据流。
3. 明确目标硬件、操作系统、驱动、CUDA/TensorRT/Python 等环境约束。
4. 调研第三方库、API、驱动和兼容性。
5. 把工程要求转化为可执行的验收标准。
6. 编写或指定实机测试方法。
7. 在真实机器、真实 GPU、真实输入上运行测试。
8. 记录性能、日志、错误、版本信息和复现步骤。
9. 对 GPT 网页版提交的**明确 commit**进行独立验证。
10. 测试失败时，不只写“失败”，而要给出足以让 GPT 修复的证据。

Codex 默认**不承担大段具体业务实现代码**，除非：

- 用户明确要求；
- 为了构造测试工具、最小复现或环境探针；
- 修改极小且这样做明显比再次交接更合理。

即使 Codex 修改代码，也必须在交接文档里说明哪些文件由 Codex 改过，避免职责边界不清。

### 2.2 GPT 网页版的职责

GPT 网页版默认负责 **“把已经明确的工程方案落实成完整代码”**。

主要职责：

1. 开工前先读取本 README、当前任务文档和相关源码。
2. 按 Codex 给出的架构、接口、约束和验收条件实现代码。
3. 必要时重构现有实现，但不得无理由偏离已确认架构。
4. 补齐异常处理、边界条件、配置、日志和必要注释。
5. 能在仓库侧完成的静态检查、单元测试或逻辑验证应尽量完成。
6. 把最终代码提交到 GitHub。
7. 写 `handoffs/web-gpt/NNN-result.md`，准确说明改了什么、如何运行、哪些内容尚未实机验证。
8. 不得把“理论上可行”描述成“已经在目标机器验证通过”。

如果 Codex 的文档存在明显冲突或缺少不可推断的关键参数，GPT 应在结果文档中明确记录，而不是静默猜测后宣称完成。

---

## 3. 仓库目录约定

当前约定：

```text
AI-Bridge/
├─ README.md
├─ handoffs/
│  ├─ codex/
│  │  ├─ 001-task.md
│  │  ├─ 001-verification.md
│  │  └─ ...
│  └─ web-gpt/
│     ├─ 001-result.md
│     └─ ...
├─ analysis-output/
│  └─ ...
├─ <项目源码>
└─ <测试代码>
```

### `handoffs/codex/`

用于 Codex 交给 GPT 的工程输入，以及 Codex 的实机验证结果。

### `handoffs/web-gpt/`

用于 GPT 网页版完成实现后的交付说明。

### `analysis-output/`

用于保存有长期价值的原始测试输出，例如：

- benchmark CSV/JSON；
- 环境快照；
- GPU/驱动信息；
- 日志；
- 性能对比结果；
- 测试生成的非敏感数据。

不要把一次性无意义的临时文件大量提交进去。

---

## 4. Task ID 与文件命名

每个独立目标分配一个三位数字 Task ID：

```text
001
002
003
...
```

推荐文件：

```text
handoffs/codex/002-task.md
handoffs/web-gpt/002-result.md
handoffs/codex/002-verification.md
```

如果同一个任务发生多轮失败修复，保留历史，不覆盖关键证据：

```text
handoffs/web-gpt/002-result-r01.md
handoffs/codex/002-verification-r01.md
handoffs/web-gpt/002-result-r02.md
handoffs/codex/002-verification-r02.md
```

仓库早期已经存在的不带 `r01` 的文件可以继续视为第一轮，无需重命名。

---

## 5. Codex 任务文档规范

Codex 新建 `handoffs/codex/NNN-task.md` 时，应尽可能包含下面的信息。

```markdown
# Task NNN — <任务名称>

TASK_STATUS: READY_FOR_GPT

## Goal
最终要解决什么问题。

## Background
必要背景，说明为什么要做。

## Target environment
- OS:
- CPU:
- GPU:
- GPU architecture / compute capability:
- Driver:
- CUDA:
- TensorRT:
- Python:
- 关键依赖版本:

## Architecture
模块划分、调用链、数据流、接口和关键设计决定。

## Required changes
明确要求 GPT 新增、修改、删除什么。

## Interfaces / contracts
输入、输出、类型、尺寸、错误处理、文件格式、API 约束等。

## Constraints
不能破坏的行为、兼容性、性能、显存、延迟、依赖、安全约束等。

## Acceptance criteria
必须可验证，例如：
- 指定输入产生指定输出；
- V100 上走 FP16；
- RTX 5070 上成功加载 TensorRT engine；
- 峰值显存低于 X MiB；
- 单次延迟低于 X ms；
- 某组测试全部 PASS。

## Test plan
Codex 后续会如何在实机验证。

## Out of scope
本轮明确不做什么。

## Deliverables
GPT 最终应提交哪些代码、测试和结果文档。
```

### 任务文档禁止使用模糊验收

不推荐：

```text
性能尽量快
兼容性要好
代码写完善一点
```

推荐：

```text
在指定 RTX 5070 环境下，batch=1、输入 120x60 时记录 P50/P95 latency；
程序必须在缺失 TensorRT engine 时返回明确错误而不是静默切换；
V100 路径不得调用 FP8-only kernel。
```

---

## 6. GPT 网页版交付文档规范

GPT 完成代码后写：

```text
handoffs/web-gpt/NNN-result.md
```

建议模板：

```markdown
# Web GPT Result NNN

TASK_STATUS: READY_FOR_CODEX

## Source task
handoffs/codex/NNN-task.md

## Implementation summary
这次实际做了什么。

## Changed files
- `path/a.py` — 修改原因
- `path/b.py` — 修改原因

## Key implementation decisions
说明重要实现细节，以及与 Codex 架构要求的对应关系。

## How to run
```bash
<命令>
```

## Checks performed by Web GPT
只写实际完成过的检查。

## Not verified
明确列出只能由 Codex 实机确认的事项。

## Known limitations / risks
已知限制、可能风险、待验证假设。

## Commit
`<完整 commit SHA>`

WEB_GPT_RESULT: READY_FOR_CODEX
```

### GPT 不得伪造测试结果

以下表述只有真正执行过相应测试时才能使用：

- “测试通过”；
- “TensorRT 已成功加载”；
- “V100 可运行”；
- “延迟为 2.8 ms”；
- “显存占用为 500 MiB”。

没有目标机器时应写：

```text
Not verified: 需要 Codex 在目标 RTX 5070 + TensorRT 环境实测。
```

---

## 7. Codex 实机验证规范

Codex 验证 GPT 的代码时，必须先记录**被测试 commit**。

不能只写“测试了 main”。`main` 会变化，无法复现。

建议模板：

```markdown
# Codex Verification NNN

TASK_STATUS: VERIFIED_PASS

## Source
- Task: `handoffs/codex/NNN-task.md`
- GPT result: `handoffs/web-gpt/NNN-result.md`
- Tested commit: `<完整 commit SHA>`

## Environment
实际测试机器的软件和硬件环境。

## Test commands
```bash
<实际执行的命令>
```

## Results
逐项列出验收条件和 PASS / FAIL。

## Measurements
延迟、吞吐、显存、GPU 利用率等实际数据。

## Logs / artifacts
需要时引用 `analysis-output/` 下的原始结果。

## Issues found
如果失败，写清楚错误表现、复现方法、日志和怀疑范围。

CODEX_VERIFICATION: PASS
```

验证失败时使用：

```text
TASK_STATUS: VERIFIED_FAIL
CODEX_VERIFICATION: FAIL
```

并必须至少给出：

1. 被测试 commit；
2. 实际环境；
3. 执行命令；
4. 输入条件；
5. 实际输出或错误；
6. 期望输出；
7. 关键日志；
8. 是否稳定复现。

这样 GPT 才能直接进入下一轮修改，而不是重新猜问题。

---

## 8. 状态标记

为了让 GPT 和 Codex 能快速判断下一步，每份交接文档顶部使用统一状态。

允许的主要状态：

| 状态 | 含义 |
|---|---|
| `READY_FOR_GPT` | Codex 已给出足够信息，等待 GPT 实现 |
| `NEEDS_INPUT` | 缺少用户或环境信息，当前不能可靠继续 |
| `READY_FOR_CODEX` | GPT 已完成代码，等待 Codex 实机验证 |
| `VERIFIED_PASS` | Codex 已验证通过 |
| `VERIFIED_FAIL` | Codex 已验证失败，需要 GPT 修复 |
| `BLOCKED` | 存在外部阻塞项 |

不要使用含义不清的 `DONE` 代替验证状态。

“代码写完”不等于“实机验证通过”。

---

## 9. Git 与 commit 规则

### 9.1 一个 commit 应表达一个清晰阶段

推荐 commit message：

```text
docs(task-002): define V100 FP16 requirements
feat(task-002): implement FP16 TensorRT path
fix(task-002): handle dynamic input shapes
 test(task-002): add engine compatibility checks
 docs(task-002): record Codex verification
```

### 9.2 测试必须绑定 commit

Codex 的所有测试结论都必须能回答：

> **“你测试的是哪个 commit？”**

### 9.3 不覆盖另一方的证据

- GPT 不应改写 Codex 已经完成的 verification 文档来把 FAIL 改成 PASS。
- Codex 不应重写 GPT 的 result 文档来描述不同实现。
- 下一轮使用新文件或新的 revision，保留历史。

### 9.4 不要提交秘密

禁止提交：

- API key；
- GitHub token；
- 密码；
- Cookie；
- 私钥；
- 带身份信息的配置；
- 未脱敏的内部地址或凭证。

配置文件只提交模板，例如：

```text
config.example.json
.env.example
```

---

## 10. 环境与性能测试规则

对于 GPU、CUDA、TensorRT、OCR、图像匹配、视频编解码等环境敏感任务，测试文档必须尽量记录：

```text
OS
CPU
GPU 完整型号
GPU VRAM
NVIDIA Driver
CUDA Runtime / Toolkit
TensorRT
cuDNN（如相关）
Python
关键 Python package 版本
模型 / engine SHA256（如相关）
输入尺寸
batch size
precision (FP32 / FP16 / BF16 / FP8 / INT8)
warmup 次数
正式测试次数
```

性能数据至少说明统计口径。不要只写一个没有上下文的“FPS”或“耗时”。

例如：

```text
warmup = 50
runs = 1000
batch = 1
input = 120x60
latency P50 = ... ms
latency P95 = ... ms
VRAM peak = ... MiB
```

---

## 11. 冲突处理优先级

如果不同来源的要求冲突，按以下优先级处理：

1. 用户最新的明确指令；
2. 当前 Task 的 Codex 任务文档；
3. 已通过的最新 Codex verification；
4. 本 README 的通用规范；
5. 旧任务和旧交接文档；
6. 聊天中的历史推断。

发现冲突时应明确记录冲突，而不是偷偷选择其中一个版本。

---

## 12. 开工前检查清单

### GPT 网页版读取任务时

- [ ] 已读取 `README.md`
- [ ] 已找到最新 Task ID
- [ ] 已读取对应 Codex task 文档
- [ ] 已检查当前相关源码
- [ ] 已理解目标环境
- [ ] 已确认验收条件
- [ ] 已区分“可在这里验证”和“必须交给 Codex 实机验证”的项目

### Codex 开始验证时

- [ ] 已读取 GPT result 文档
- [ ] 已确认完整 commit SHA
- [ ] 已拉取该 commit，而不是不确定的工作区状态
- [ ] 已记录实际环境
- [ ] 已按验收标准逐项测试
- [ ] 已保存必要日志和 benchmark 原始数据
- [ ] 已给出明确 PASS / FAIL

---

## 13. 最小交接协议

如果任务很小，不需要写长文档，但至少保证下面四件事存在：

### Codex → GPT

```text
TASK_ID
GOAL
REQUIRED_CHANGES
ACCEPTANCE_CRITERIA
```

### GPT → Codex

```text
TASK_ID
CHANGED_FILES
COMMIT_SHA
NOT_VERIFIED
```

### Codex → GPT / End

```text
TASK_ID
TESTED_COMMIT_SHA
TEST_COMMAND
RESULT
PASS_OR_FAIL
```

只要这三段信息完整，即使对话上下文丢失，双方仍然可以仅依赖 GitHub 恢复工作。

---

## 14. 本仓库的最终原则

AI-Bridge 的目标不是让两个 AI 同时“随便改代码”，而是形成明确的工程流水线：

```text
Codex = Architect + Test Engineer + Real-machine Verifier
GPT Web = Implementation Engineer
GitHub = Shared State + Source of Truth + Audit Trail
```

每次交接都应做到：

- **可读**：下一方不需要原聊天上下文也能继续；
- **可执行**：要求不是抽象描述，而是可以直接落实；
- **可复现**：测试绑定环境、命令和 commit；
- **可追踪**：谁提出要求、谁实现、谁验证都能从仓库看出来；
- **不冒充验证**：没有跑过的东西就明确写“未验证”；
- **保留失败证据**：失败结果也是下一轮最重要的输入。

当聊天内容与仓库记录不一致时，优先把新的有效结论写回仓库，再继续下一阶段。