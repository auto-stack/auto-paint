# auto-paint

画板，使用 AutoLang / AutoUI 开发的独立应用。

更新：2026-11-01。001已交付归档/r2、7/7；16×16/V2工程/SVG，原VM27/27、Vue22/22和desktop_mcp31项为冻结记录。 本轮未重跑产品验收。

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

AutoOS 通过 [`apps/auto-paint`](https://github.com/auto-stack/auto-os/tree/main/apps/auto-paint) submodule 固定本仓版本；教学 Demo 保留在来源仓。

已有测试随源导入；端口与平台相关测试需要按本仓配置准备运行环境。安装/启动与双端完整功能验收是不同检查项。

## 基本能力补齐计划（2026-10-29）

[PAINT-001：可靠像素画板、保存恢复与作品导出](docs/plans/archived/001-reliable-pixel-paint.md) 为本app的基础能力执行合同（已交付归档），实施与双端验收见计划 §8/§9 与 [T-01 能力决策](docs/plans/evidence/001/capability-decision.md)。
总状态与前置见 [AutoOS B类总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。基础能力通过后再考虑Linux；A类统一等待 auto-os-distro 完成 Nix＋COSMIC 基础，后续增强另会话。

开发使用独立 clone `D:/autostack/auto-paint` 的 main；AutoOS 内对应子模块仅固定已交付提交，流程见 [App开发与子模块](https://github.com/auto-stack/auto-os/blob/main/docs/design/strategy/app-submodule-workflow.md)。


## 当前后续计划（2026-11-01）

[PAINT-002：独立运行、跨重启工程与SVG验收](docs/plans/002-standalone-project-and-svg.md) 为 **drafting/r1、0/7，尚未实施**。固定原生KV与Vue同源localStorage两个profile，复验真实编辑、跨进程重开、下一次编辑和SVG逐格oracle；不强加新绘图功能。

先T-00核验实际源码/CLI/编译或渲染tool、已有SDK、冷准备与失败边界；实证缺项才转实际owner最小前置。既有测试入口继续复用，历史绿总数不能替代新必需UI操作。只用隔离数据/本次进程；不清共享target或终止用户实例。无实证业务缺口时不为完成计划强改业务源码。

[路线图](docs/roadmap-v0.6.md) · [现实现规范](docs/specs/paint/basic-capabilities.md)。开发与顺序复审在D:/autostack/auto-paint独立clone main，一app一写入者；不在OS组合子模块开发，不建junction/symlink。本轮只准备/提交push计划和导航，不实现、不改Spec/旧ledger和归档，不更新AutoOSpin。各app独立验收后由统一OS计划装配，Linux仍WAIT_DISTRO_M1。

保留16×16与SVG范围。VM文件KV、Vue同源localStorage不自动共享；002须复用同一持久profile证明跨进程重开。PNG、图层/大画布和跨端同步另排。
