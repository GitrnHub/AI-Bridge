# Artifact & Compression Policy

本文件回答一个常见问题：**AI-Bridge 是否应该用压缩包在 Codex 和 Web GPT 之间传源码或测试文件？**

结论：**默认不应该。压缩包是 artifact 格式，不是版本控制协议。**

## 1. 源码为什么不打包

Git commit 已经定义一棵精确文件树。正常源码直接逐文件提交具有以下优势：

- diff 可读；
- 单文件修改清晰；
- merge/rebase 可用；
- blame/history 可追踪；
- agent 可以只读取需要的文件；
- 测试和验证可以绑定 commit SHA；
- Git 自身会对对象进行压缩和 pack/delta 优化。

把同一份源码再放进 `project.zip` 不增加确定性，反而把许多独立文件变成一个不透明二进制 blob。

因此禁止把以下模式作为日常交接：

```text
source.zip
latest.zip
fixed.zip
final-v2.zip
project-20260909.7z
```

## 2. 什么时候压缩包是合理的

压缩包只有在“**包本身就是需要传递的 artifact**”时合理，例如：

- 构建出的可执行程序及其 DLL/资源需要整体分发；
- 多份日志/trace/core dump 需要一次性交给对方分析；
- 测试语料必须保持目录结构且文件数量非常多；
- 离线安装包；
- 外部系统只接受单个归档文件；
- 需要保存某次不可复现实验的完整输出快照。

即使使用压缩包，源码的 source of truth 仍应是 Git commit，除非有非常特殊的外部限制。

## 3. 存储位置决策表

| 内容 | 默认位置 | 是否压缩 | 说明 |
|---|---|---:|---|
| 源码、Markdown、配置、脚本 | 普通 Git | 否 | 保持 diff 能力 |
| 小型测试 fixture / 必要图片 | 普通 Git | 通常否 | 只提交真正需要版本化的内容 |
| 大型二进制且每次 checkout 都需要 | Git LFS | 可选 | LFS 用 pointer 管理实际大文件 |
| Release/里程碑 EXE、模型、安装包 | GitHub Release assets | 可选/常用 | 不污染 Git history |
| CI 构建结果、失败日志、coverage、截图 | GitHub Actions artifacts | 可选 | 临时/运行级输出 |
| 超大模型、数据集、录屏、dump | 外部对象存储 | 常用 | 仓库只记录 manifest + checksum |
| Git tag 对应源码包 | GitHub 自动 source ZIP/tarball | 不手工提交 | Release/tag 已提供 |

## 4. GitHub 大文件边界

按 GitHub 当前公开文档：

- 普通 Git 中单文件超过 **50 MiB** 会警告；
- 单文件超过 **100 MiB** 会被 GitHub 阻止；
- GitHub 建议仓库尽量保持小型，理想上小于约 1 GB；
- 真正需要随 Git 版本化的大文件使用 Git LFS；
- Release asset 单文件可到 **2 GiB**，适合分发二进制；
- Actions artifact 适合构建输出、日志、测试结果、截图等 workflow 产物。

**不要通过“先压缩到 100 MiB 以下”来规避架构问题。** 如果文件本质上是大型 artifact，应选择 LFS、Release、Actions artifact 或对象存储。

## 5. LFS 什么时候用

使用 Git LFS 的必要条件通常是：

1. 文件必须与源码版本一起 checkout；
2. 文件确实需要版本控制；
3. 文件是大型二进制，普通 Git 不合适。

典型：

- 必须随项目版本对应的模型权重；
- 大型设计资产；
- 必需但无法方便重建的二进制资源。

如果文件只是构建出来的 `.exe`、TensorRT engine、临时 benchmark dump，通常 Release/Actions artifact 比 LFS 更合适。

## 6. Release 什么时候用

GitHub Release 适合：

- 交付给人下载的 EXE/安装包；
- 某个里程碑的模型、engine、bundle；
- 需要与 tag/commit 明确对应的稳定二进制。

Release 本身基于 Git tag，GitHub 会为 tag 自动提供源码 ZIP/tarball。因此不要额外把相同源码 ZIP 提交进仓库。

## 7. Actions Artifact 什么时候用

适合一次 workflow 的：

- build output；
- test results；
- logs；
- crash dump；
- screenshots；
- coverage；
- benchmark raw output。

这类数据往往只在调试/验证阶段需要，不应永久膨胀 Git history。

## 8. 外部存储什么时候用

以下情况优先外部对象存储：

- 多 GB 数据集；
- 大型视频/帧序列；
- 巨型模型；
- 大量临时实验产物；
- artifact 超出 Release/LFS 的便利范围；
- 数据有独立生命周期或访问控制需求。

仓库必须在 exchange 的 `artifacts.md` 中记录可定位信息。

## 9. Artifact Manifest 必填项

任何不直接保存在 Git 的 artifact 至少记录：

```text
name
type
location / release tag / artifact id
size_bytes
sha256
produced_from_commit
producer
purpose
created_at
retention / expiry（如果有）
```

如果是模型/engine，建议额外记录：

```text
framework / runtime
precision
input profile
hardware compatibility
build environment
```

这样即使文件移动，也能判断拿到的是否是同一个 artifact。

## 10. 压缩格式选择

确需归档时：

- `.zip`：默认跨平台选择，Windows/macOS/Linux 都容易处理；
- `.tar.gz`：Unix/Linux 目录树、权限/符号链接语义更重要时使用；
- `.7z`：只有压缩率确实重要且双方明确有工具时使用，不作为默认协议；
- 密码保护 archive：禁止作为 AI 自动交接常规方式，会妨碍自动化和审计。

避免：

- archive 套 archive；
- 只发压缩包却不记录源 commit；
- 用压缩包替代 Git patch/diff；
- 同一内容同时在 Git、Release、LFS 多份无规则保存。

## 11. 可复现构建优先

如果一个大文件能可靠从源码生成，优先保存：

```text
source commit
build script
build environment
parameters
checksum of output
```

而不是永久把每一次生成结果都提交进 Git。

无法复现、代价极高或需要对外分发的结果，再保存为 Release/LFS/外部 artifact。

## 12. 对 AI-Bridge 的最终规则

**正常交接：Git files + commit SHA。**

**大文件交接：artifact location + manifest + SHA256。**

**压缩包：只有当“归档本身”有实际传输价值时才使用。**
