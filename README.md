# auto-paint

画板，使用 AutoLang / AutoUI 开发的独立应用。

本仓是首批产品源码基线；当前能力以导入版本为准，仓库描述中的产品方向不表示全部已实现。

## 运行

安装对应版本的 `auto` CLI 后，从本仓根执行：

```sh
auto run -r vm              # 桌面（iced/VM）档
auto run -r vue --server vm # 浏览器（vue）档：front 17834 + 后端 17835
```

前端端口：`17834`；导出后端端口：`17835`（`pac.at` `back_port`）。

**vue 档必须带 `--server vm`**：本 app 无 rust 后端，默认 `auto run`
（rust 后端生成）不可用；导出（SVG）依赖 17835 的 VM HTTP 服务，无后端时
保存/加载仍可用、导出会显式失败。

共享 StyleKit 已固定在 `vendor/stylekit`，无需相邻 auto-lang 示例目录。

## 验收

```sh
python tests/basic/verify_basic.py --profile vm    # 基础能力（VM 轨）
python tests/basic/verify_basic.py --profile vue   # 基础能力（vue 轨，17834/17835 需空闲）
python tests/desktop_mcp.py                        # VM 轨回归（AUTO_BIN 指向 auto CLI）
```

能力范围与合同见 [docs/specs/paint/basic-capabilities.md](docs/specs/paint/basic-capabilities.md)。

## 来源与组合

来源提交、路径与文件 hash 见 `SOURCE-IMPORT.json`。首次导入提交保留在 `source-sync` 分支；完整 v0.5 恢复后从该基线导入差异，再与产品开发线合并。

AutoOS 通过 [`apps/031-paint`](https://github.com/auto-stack/auto-os/tree/v0.6-dev/apps/031-paint) submodule 固定本仓版本；教学 Demo 保留在来源仓。

已有测试随源导入；端口与平台相关测试需要按本仓配置准备运行环境。安装/启动与双端完整功能验收是不同检查项。

## 基本能力补齐计划（2026-10-29）

[PAINT-001：可靠像素画板、保存恢复与作品导出](docs/plans/archived/001-reliable-pixel-paint.md) 为本app的基础能力执行合同（已交付归档），实施与双端验收见计划 §8/§9 与 [T-01 能力决策](docs/plans/evidence/001/capability-decision.md)。
总状态与前置见 [AutoOS B类总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。基础能力通过后再考虑Linux；A类统一等待 auto-os-distro 完成 Nix＋COSMIC 基础，后续增强另会话。

开发使用独立 clone `D:/autostack/auto-paint` 的 main；AutoOS 内对应子模块仅固定已交付提交，流程见 [App开发与子模块](https://github.com/auto-stack/auto-os/blob/main/docs/design/strategy/app-submodule-workflow.md)。
