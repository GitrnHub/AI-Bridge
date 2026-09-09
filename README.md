# AI-Bridge

AI-Bridge 是一个 **GPT 网页版（Web GPT）与 Codex 的通用 Git 交接仓库**。

它不绑定某个具体项目、语言、GPU、框架或任务类型。它提供一套稳定协议，让两个 AI 即使没有共享聊天上下文，也能仅依赖 GitHub 恢复当前状态、继续工作并保留验证证据。

## 角色

- **Codex**：架构、任务拆解、环境调查、真实机器操作、测试、benchmark、失败复现、最终验证。
- **Web GPT**：根据 Codex 的明确输入完成具体实现、重构、修复、测试代码和交付说明。
- **GitHub/Git**：唯一共享状态、源码、变更历史和验证边界。

核心原则：

> **Git commit 是代码快照；exchange 文档是语义交接；artifact manifest 是大文件/二进制的索引。不要把聊天记忆当成接口。**

## 新结构

```text
AI-Bridge/
├─ README.md
├─ AGENTS.md
├─ .gitignore
├─ bridge/
│  ├─ PROTOCOL.md
│  ├─ ARTIFACTS.md
│  ├─ registry.yaml
│  └─ templates/
│     ├─ STATE.yaml
│     ├─ CONTEXT.md
│     ├─ REQUEST.md
│     ├─ RESPONSE.md
│     ├─ VERIFICATION.md
│     └─ ARTIFACTS.md
└─ workspaces/
   ├─ README.md
   └─ <workspace>/
      ├─ .bridge/
      │  ├─ state.yaml
      │  ├─ context.md
      │  └─ exchanges/
      │     └─ <handoff-id>/
      │        ├─ request.md
      │        ├─ response.md
      │        ├─ verification.md
      │        ├─ artifacts.md
      │        └─ evidence/          # 仅小型、适合 Git 的证据
      └─ <实际工作文件/源码>
```

`workspace` 是通用容器，可以代表一个程序、实验、调查、自动化、文档工程、硬件验证或任何需要连续交接的工作域。

## 标准闭环

```text
Codex 创建/更新 workspace
        ↓
Codex 写 request.md，明确设计、约束、验收方法
        ↓
Web GPT 在同一 exchange 中实现并写 response.md
        ↓
Codex 锁定 implementation commit，在真实环境验证
        ↓
verification.md
   ├─ FAIL → Web GPT 修复 → 再验证
   └─ PASS → 合并为 accepted baseline
```

详细规则见 [`bridge/PROTOCOL.md`](bridge/PROTOCOL.md)。

## 压缩包结论

**正常源码交接不使用 ZIP/7z/tar 包。**

原因：

1. Git commit 本身已经是精确快照，不需要再把源码打包来“固定版本”。
2. Git 会对对象进行压缩和打包，而源码保持逐文件管理，便于 diff、review、merge 和 blame。
3. ZIP/7z 对 Git 来说基本是不可语义 diff 的二进制容器；反复提交源码压缩包会显著降低可审查性并膨胀历史。
4. GitHub Release 已可基于 tag 自动提供源码 ZIP/tarball，没有必要在仓库里再提交一份 `source.zip`。

压缩包只在它本身是**交付 artifact**时使用，例如构建产物集合、日志包、测试语料包、离线安装包，或对方工具明确要求单文件包。

完整决策表见 [`bridge/ARTIFACTS.md`](bridge/ARTIFACTS.md)。

## Git 工作方式

- `main`：协议 + 已接受/已验证的 workspace 基线。
- 活跃交接默认使用短期分支：`bridge/<workspace>/<handoff-id>`。
- Codex 验证时必须写完整 tested commit SHA，不能只写“测试 main”。
- 验证失败继续在同一 exchange/分支迭代，Git 历史保留每轮实现。
- 验证通过后再合并回 `main`；需要 review/CI 时优先用 Pull Request。

## 开始一个 workspace

1. 创建 `workspaces/<slug>/`。
2. 复制 `bridge/templates/STATE.yaml` 为 `.bridge/state.yaml`。
3. 复制 `bridge/templates/CONTEXT.md` 为 `.bridge/context.md`。
4. 在 `bridge/registry.yaml` 注册 workspace。
5. 新交接创建 `.bridge/exchanges/<handoff-id>/`，从模板复制 request/response/verification/artifacts 文件。
6. `handoff-id` 推荐使用 UTC 时间 + 简短 slug，例如：`20260909T123500Z-fp16-runtime`。

## 不变原则

- **未运行 ≠ 已验证。**
- **推测 ≠ 事实。**
- **代码完成 ≠ 实机通过。**
- **大文件位置必须可追踪且有校验值。**
- **不要提交密码、Token、Cookie、私钥或未脱敏敏感数据。**
- **重要决定必须落入仓库，而不是只存在于聊天。**
