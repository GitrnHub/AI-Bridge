# AI-Bridge

AI-Bridge 是一个长期存在的 **GPT 网页版 ↔ Codex 通用工程交接仓库**。

它不是为某个特定项目、某一种代码、某一台机器或某一次任务建立的；它的作用是给两个彼此不能共享完整会话状态的 AI 提供一个稳定、可追踪、可恢复的中继层。

默认分工：

- **Codex**：Architecture / Planning / Environment / Real-machine Test / Verification
- **GPT Web**：Concrete Implementation / Refactor / Repair / Integration / Documentation
- **GitHub**：Shared State / Source of Truth / Audit Trail

一句话原则：

> **不要把关键上下文留在聊天里。能影响下一方工作的内容，都应进入仓库。**

---

## 1. AI-Bridge 解决什么问题

GPT 网页版和 Codex 可能分别拥有不同能力、环境和上下文：

- Codex 可能能接触真实工作目录、设备、GPU、驱动、编译器、服务或测试环境；
- GPT 网页版更适合集中阅读上下文、推理实现方案并生成或修改完整代码；
- 双方的聊天历史不应被假定为共享；
- `main` 会移动，测试对象必须能被精确定位；
- 一个工作可能跨多天、多轮修复、多个项目，甚至完全切换技术栈。

因此 AI-Bridge 把交接从“自然语言聊天”提升为一个轻量协议：

```text
Context / Requirement / Architecture
             ↓
          Codex handoff
             ↓
      GPT Web implementation
             ↓
         exact Git commit
             ↓
     Codex real-world verification
             ↓
      PASS / evidence-backed FAIL
             ↓
     next handoff or completion
```

这里的“工作”可以是任何工程事项：新功能、Bug、重构、脚本、环境诊断、模型部署、性能优化、配置、迁移、数据处理、网页、桌面程序、GPU 测试、兼容性验证等。

协议本身不依赖具体语言、框架或硬件。

---

## 2. 三个核心对象

AI-Bridge 不以“一个仓库只能对应一个 Task”为前提，而是围绕三个对象组织。

### 2.1 Workspace

`Workspace` 表示一段相对独立的上下文，可以对应：

- 一个项目；
- 一个代码库；
- 一个实验；
- 一个长期主题；
- 一个临时问题。

推荐使用稳定、可读的 slug，例如：

```text
ocr-runtime
image-registration
web-tool
gpu-compat
```

不要求预先创建固定 workspace 目录；它主要用于交接文档的元数据和索引。

### 2.2 Handoff

`Handoff` 是一次明确的“把当前状态交给另一方”。

它可以是：

- Codex → GPT Web：需求、架构、测试发现、失败证据；
- GPT Web → Codex：代码实现、修复结果、待实机验证内容；
- Codex → GPT Web：验证失败后的下一轮证据；
- Codex → End：验证通过后的终态记录。

### 2.3 Artifact

`Artifact` 是交接引用的实际产物，例如：

- 源码；
- 测试；
- 配置模板；
- benchmark；
- 日志；
- 环境快照；
- 图片、JSON、CSV 等非敏感测试产物。

重要产物必须能通过文件路径、commit SHA、文件哈希或明确版本定位。

---

## 3. 仓库结构

推荐结构：

```text
AI-Bridge/
├─ README.md
├─ handoffs/
│  ├─ INDEX.md                 # 当前路由表 / 最近状态
│  ├─ codex/                   # Codex 发出的交接与验证
│  └─ web-gpt/                 # GPT Web 发出的实现交接
├─ templates/                  # 可复制的标准模板
├─ analysis-output/            # 日志、benchmark、环境快照等证据
├─ <源码 / 脚本 / 配置 / 测试>
└─ ...
```

现有旧文件例如：

```text
handoffs/codex/001-verification.md
handoffs/web-gpt/001-result.md
```

继续有效，不需要为了新规范重命名。

---

## 4. 打开仓库后的读取顺序

任何一方进入 AI-Bridge 时，默认按下面顺序获取状态：

1. 读取根目录 `README.md`；
2. 读取 `handoffs/INDEX.md`；
3. 找到与当前 workspace / handoff 相关的最新文档；
4. 根据文档中的 `parent` / `source` 追溯必要上下文；
5. 检查引用的 commit、源码和 artifacts；
6. 只在完成上述步骤后开始修改或测试。

**不要仅凭文件名最大的编号猜测当前工作。**

多个 workspace 可以并行存在，`INDEX.md` 才是快速路由入口。

---

## 5. 通用 Handoff ID

新交接推荐使用：

```text
YYYYMMDD-HHMM-<workspace>-<short-topic>
```

例如：

```text
20260909-2030-gpu-compat-runtime-check
20260910-0115-web-tool-upload-fix
```

对应文件可为：

```text
handoffs/codex/20260909-2030-gpu-compat-runtime-check.md
handoffs/web-gpt/20260909-2110-gpu-compat-runtime-check.md
```

旧式 `001 / 002 / 003` 编号仍兼容，但新格式更适合长期、多项目和并行交接。

Handoff ID 的目标是**唯一和可追踪**，不是表达优先级。

---

## 6. 每份交接文档的统一头部

所有新 handoff 文档顶部应包含一个轻量、可机器读取的元数据块：

```yaml
---
bridge_version: 1
handoff_id: 20260909-2030-example-runtime-check
workspace: example
from: codex
to: web-gpt
type: request
status: ready
parent: null
source_commit: null
target_commit: null
created_at: 2026-09-09T20:30:00+08:00
---
```

字段定义：

| 字段 | 含义 |
|---|---|
| `bridge_version` | AI-Bridge 协议版本 |
| `handoff_id` | 本次交接唯一 ID |
| `workspace` | 所属上下文 / 项目 slug |
| `from` | `codex` 或 `web-gpt` |
| `to` | `codex`、`web-gpt` 或 `end` |
| `type` | 本次交接类型 |
| `status` | 当前状态 |
| `parent` | 直接上游 handoff ID，没有则为 `null` |
| `source_commit` | 产生本次结论时基于的 commit，可空 |
| `target_commit` | 希望下一方处理/验证的 commit，可空 |
| `created_at` | 带时区的 ISO 8601 时间 |

### 推荐的 `type`

```text
request          要求下一方实现或处理
implementation   GPT Web 的实现交付
verification     Codex 的验证结果
failure          实机失败证据 / 修复请求
context          上下文补充
benchmark        性能或对比测试
decision         已确认的架构/接口决定
```

### 推荐的 `status`

```text
ready            信息完整，目标方可继续
in_progress      已开始处理
needs_input      缺关键输入
blocked          外部条件阻塞
pass             已验证通过
fail             已验证失败
superseded       已被新 handoff 替代
closed           已结束且无需继续
```

---

## 7. Codex 的默认职责

Codex 默认负责：

1. 理解真实目标与使用环境；
2. 设计总体架构、模块边界和接口；
3. 识别系统、硬件、驱动、依赖、权限和版本约束；
4. 把模糊需求转化为可验证条件；
5. 必要时制作环境探针、最小复现和测试脚本；
6. 在真实目标环境执行测试；
7. 保存日志、benchmark、错误、环境信息和复现步骤；
8. 对 GPT Web 的**明确 commit**做独立验证；
9. PASS 时给出可复现证据；
10. FAIL 时把足以修复的信息重新交给 GPT Web。

Codex 更像：

```text
Architect + Integration/Test Engineer + Real-machine Verifier
```

Codex 可以修改代码，但如果修改超出测试工具、环境探针或非常小的修正，应在 handoff 中明确声明，避免双方同时无记录地改同一部分。

---

## 8. GPT Web 的默认职责

GPT Web 默认负责：

1. 阅读 README、INDEX、上游 handoff 和相关源码；
2. 把 Codex 已明确的架构与要求落实成具体实现；
3. 编写、修改、补全或重构实际代码；
4. 完成必要的异常处理、边界条件、配置和注释；
5. 能在当前环境验证的内容应实际验证；
6. 不能验证的环境相关事项必须明确标为 `Not verified`；
7. 把代码提交到 GitHub；
8. 生成 implementation handoff，交给 Codex 实机复测。

GPT Web 更像：

```text
Implementation Engineer
```

**不得把静态推理或“看起来正确”描述成真实设备已经验证通过。**

---

## 9. Codex → GPT Web：交接内容

一次实现请求至少应回答：

```text
WHAT      要实现 / 修复什么
WHY       为什么需要它
WHERE     涉及哪些文件 / 模块 / 接口
CONTRACT  输入输出和必须保持的行为
CONSTRAINTS 不能违反什么约束
EVIDENCE  已知日志、测试、环境事实
ACCEPTANCE 如何判断完成
NEXT      GPT Web 完成后应交付什么
```

如果是实机失败回传，还应包含：

```text
TESTED_COMMIT
ENVIRONMENT
COMMAND
INPUT
EXPECTED
ACTUAL
ERROR / LOG
REPRODUCIBILITY
```

不要只写：

```text
还是不行，修一下。
```

---

## 10. GPT Web → Codex：交接内容

实现交付至少应包含：

```text
SOURCE_HANDOFF
IMPLEMENTATION_SUMMARY
CHANGED_FILES
KEY_DECISIONS
HOW_TO_RUN
CHECKS_PERFORMED
NOT_VERIFIED
KNOWN_RISKS
TARGET_COMMIT
NEXT_ACTOR: codex
```

关键规则：

> **交给 Codex 测试的是 commit，不是“我刚才写的那版代码”。**

如果交付文档本身和代码无法在同一个 commit 中互相引用，可在文档里引用代码 commit，并由后续 verification 引用最终测试 commit；不要伪造不存在的 SHA。

---

## 11. Codex 验证规则

Codex 开始验证前必须确定：

```text
TESTED_COMMIT = <完整 SHA>
```

不要只写：

```text
tested main
```

因为 `main` 会变化。

验证报告至少写：

```text
TESTED_COMMIT
ENVIRONMENT
TEST_COMMANDS
ACCEPTANCE_RESULTS
MEASUREMENTS（如相关）
ARTIFACTS / LOGS
PASS_OR_FAIL
```

### PASS

只有目标条件确实被验证后才能：

```yaml
status: pass
to: end
```

### FAIL

失败时：

```yaml
status: fail
to: web-gpt
type: failure
```

然后附上足够的复现证据，使 GPT Web 可以在没有原聊天记录的情况下继续修复。

---

## 12. `handoffs/INDEX.md`：路由表

`INDEX.md` 不是完整日志，而是**当前状态缓存**。

建议每个活跃 workspace 一行：

```markdown
| Workspace | Current handoff | State | Next actor | Target commit | Note |
|---|---|---|---|---|---|
| example-a | `...handoff-id...` | ready | web-gpt | `abc123...` | implement parser |
| example-b | `...handoff-id...` | fail | web-gpt | `def456...` | reproduce on target machine |
```

规则：

- 新 handoff 创建后更新对应 workspace 的行；
- 已结束的 workspace 可移动到 History；
- `INDEX.md` 只做导航，详细信息仍以实际 handoff 文档和 commit 为准；
- 如果 INDEX 与 handoff 内容冲突，以**更新、更具体且可定位的 handoff + commit** 为准，并修正 INDEX。

---

## 13. 多项目与并行工作

AI-Bridge 必须允许多个 workspace 同时存在。

因此：

- 不使用一个全局 `CURRENT_TASK=002` 控制所有工作；
- 不假设编号最大就是当前工作；
- 每份 handoff 都声明 `workspace`；
- 每个 workspace 都有自己的 parent 链；
- 一方只修改自己正在处理的 handoff 链所引用的内容；
- 不相关工作不应因为另一个 workspace 的 PASS/FAIL 被隐式关闭。

---

## 14. 上下文压缩原则

交接文档不是聊天全文备份。

应保留的是**会影响下一步决策的信息**：

- 已确认需求；
- 架构决定；
- 接口契约；
- 真实环境；
- 已排除方案；
- 已知风险；
- 错误和日志；
- 测试结果；
- commit / 文件 / artifact 定位。

可以省略：

- 无结果的闲聊；
- 已被后续决定完全替代的探索；
- 与当前工作无关的长篇讨论。

目标是让另一方**无需原会话也能继续，但不需要重新阅读全部历史**。

---

## 15. 决策与事实分离

文档中最好明确区分：

```text
FACT        实际观察、命令输出、真实测试结果
DECISION    用户或架构已经确认的选择
ASSUMPTION  尚未验证但当前实现暂时依赖的假设
PROPOSAL    可选方案，尚未确认
```

尤其是硬件、驱动、网络、性能、第三方 API 等环境敏感问题，不应把 `ASSUMPTION` 写成 `FACT`。

---

## 16. Git 规则

### 精确引用

使用完整 commit SHA 记录正式验证对象。

### 不覆盖证据

已经完成的失败验证不应被直接改写成成功。

正确方式是创建下一份 handoff：

```text
failure → implementation → verification
```

保留链路。

### Commit message

推荐：

```text
docs(bridge): add architecture handoff
feat(<workspace>): implement requested change
fix(<workspace>): address verification failure
test(<workspace>): add regression coverage
docs(bridge): record verification result
```

不强制某种编程语言或分支策略。

---

## 17. Artifact 与大文件

`analysis-output/` 适合保存有复现价值的轻量证据：

- `.txt` / `.log`
- `.json`
- `.csv`
- 环境快照
- benchmark 汇总
- 非敏感测试输出

大型模型、engine、视频、数据集或二进制不应无脑提交 Git。

如果实际文件位于其他地方，handoff 中至少记录：

```text
名称
版本
来源
SHA256（可获得时）
生成命令（可获得时）
```

---

## 18. 安全规则

禁止提交：

- API key；
- access token；
- 密码；
- Cookie；
- SSH / TLS 私钥；
- 未脱敏凭证；
- 不应公开的个人或内部敏感信息。

配置使用模板：

```text
.env.example
config.example.json
```

真实秘密由实际环境注入。

---

## 19. 冲突优先级

如果信息冲突，默认优先级：

1. 用户最新明确指令；
2. 当前 handoff 中明确的新要求；
3. 已验证且仍适用的事实；
4. 当前 workspace 的既有架构决定；
5. 本 README 的通用协议；
6. 更早的 handoff；
7. 聊天记忆或推断。

发现冲突时应记录，而不是静默选择。

---

## 20. 最小协议

即使某次工作非常小，也至少留下以下字段。

### Codex → GPT Web

```text
HANDOFF_ID
WORKSPACE
GOAL
REQUIRED_CHANGE
ACCEPTANCE
NEXT_ACTOR: web-gpt
```

### GPT Web → Codex

```text
HANDOFF_ID
PARENT
WORKSPACE
CHANGED_FILES
TARGET_COMMIT
NOT_VERIFIED
NEXT_ACTOR: codex
```

### Codex → End / GPT Web

```text
HANDOFF_ID
PARENT
WORKSPACE
TESTED_COMMIT
RESULT
EVIDENCE
NEXT_ACTOR: end | web-gpt
```

只要这组信息完整，即使两边上下文都丢失，也能从 GitHub 恢复工作。

---

## 21. 开工检查

### GPT Web

- [ ] 已读 `README.md`
- [ ] 已读 `handoffs/INDEX.md`
- [ ] 已确认 workspace
- [ ] 已读取当前 handoff 与必要 parent
- [ ] 已检查相关源码和引用 commit
- [ ] 已区分事实、决定与假设
- [ ] 已确认哪些内容无法在网页侧实机验证

### Codex

- [ ] 已读 `README.md`
- [ ] 已读 `handoffs/INDEX.md`
- [ ] 已确认 workspace
- [ ] 已读取 GPT implementation handoff
- [ ] 已固定要测试的完整 commit SHA
- [ ] 已记录真实环境
- [ ] 已逐项执行验收
- [ ] 已保存必要证据
- [ ] 已给出 PASS 或 evidence-backed FAIL

---

## 22. 协议设计目标

AI-Bridge 最终追求六个性质：

**Recoverable**  
任何一方丢失聊天上下文后，只靠仓库仍能恢复。

**Traceable**  
能知道要求从哪里来、谁实现、验证了哪个 commit。

**Reproducible**  
重要测试可以依靠环境、命令、输入和 artifact 重现。

**General**  
不绑定某个项目、语言、框架、模型或硬件。

**Asymmetric by design**  
充分利用 Codex 的架构/实机能力与 GPT Web 的集中代码实现能力，而不是要求二者做完全相同的事情。

**Evidence over confidence**  
“应该能工作”与“真实验证通过”必须严格区分。

---

## 23. 最简心智模型

```text
Codex
  ↓  把架构、环境事实、要求、实测结果写成 handoff
GitHub / AI-Bridge
  ↓  提供可追踪共享状态
GPT Web
  ↓  把 handoff 落实成具体代码并提交 commit
GitHub / AI-Bridge
  ↓
Codex
  ↓  在真实环境验证明确 commit
PASS → 记录并结束当前链
FAIL → 带证据创建下一份 handoff
```

**AI-Bridge 本身不是某个工作的 README，而是一套让 GPT Web 和 Codex 可以反复用于任何工程工作的交接协议。**
