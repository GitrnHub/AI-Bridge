# Workspaces

每个子目录是一个独立、长期存在的工作域。

```text
workspaces/<slug>/
├─ .bridge/
│  ├─ state.yaml
│  ├─ context.md
│  └─ exchanges/<handoff-id>/
└─ <actual files>
```

## 命名

使用稳定、短、可读的 slug，例如：

```text
ocr-runtime
image-registration
web-tooling
gpu-compat
```

不要把日期或一次性 task 编号作为 workspace 名；日期属于 handoff-id。

## 创建

从 `/bridge/templates/` 复制 state/context/exchange 模板，并在 `/bridge/registry.yaml` 增加索引。

## 代码布局

AI-Bridge 不强制 workspace 内部必须使用 `src/`、`tests/` 等统一结构。保持该工作本身最自然的项目布局；`.bridge/` 只负责协作元数据，不侵入具体技术栈。
