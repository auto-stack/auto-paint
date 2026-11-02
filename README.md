# auto-paint

画板，使用 AutoLang / AutoUI 开发的独立应用。

更新：2026-11-02。002 work段完成（待复审）：独立运行门VM50/50×2、Vue45/45×2、desktop_mcp31/31连续绿（坏tool负控非零）；修复vue后端断开导出假成功。001的VM27/27、Vue22/22为001冻结记录。

## 运行

安装对应版本的 `auto` CLI 后，从本仓根执行：

```sh
auto run -r vm              # 桌面（iced/VM）档
auto run -r vue --server vm # 浏览器（vue）档：front 17834 + 后端 17835
```

前端端口：`17834`；导出后端端口：`17835`（`pac.at` `back_port`）。

**vue 档必须带 `--server vm`**：本 app 无 rust 后端，默认 `auto run`
（rust 后端生成）不可用；导出（SVG）依赖 17835 的 VM HTTP 服务，后端断开
时导出显式失败（无假成功）、画布与已保存工程不变，恢复后下一次导出成功。

共享 StyleKit 已固定在 `vendor/stylekit`，无需相邻 auto-lang 示例目录。

## 验收

```sh
python tests/basic/verify_basic.py --profile vm    # 50 项（001 V组 + 002 P组）
python tests/basic/verify_basic.py --profile vue   # 45 项（17834/17835 需空闲；运行自有持久浏览器 profile）
AUTO_BIN=<auto CLI> python tests/desktop_mcp.py    # VM 轨回归 31 项（必须显式指定 AUTO_BIN）
```

能力范围与合同见 [docs/specs/paint/basic-capabilities.md](docs/specs/paint/basic-capabilities.md)；独立运行边界（两 profile、存储身份、冷准备、后端生命周期）见 [docs/specs/paint/standalone-runtime.md](docs/specs/paint/standalone-runtime.md)。

## 来源与组合

来源提交、路径与文件 hash 见 `SOURCE-IMPORT.json`。首次导入提交保留在 `source-sync` 分支；完整 v0.5 恢复后从该基线导入差异，再与产品开发线合并。

AutoOS 通过 [`apps/auto-paint`](https://github.com/auto-stack/auto-os/tree/main/apps/auto-paint) submodule 固定本仓版本；教学 Demo 保留在来源仓。

已有测试随源导入；端口与平台相关测试需要按本仓配置准备运行环境。安装/启动与双端完整功能验收是不同检查项。

## 基本能力补齐计划（2026-10-29）

[PAINT-001：可靠像素画板、保存恢复与作品导出](docs/plans/archived/001-reliable-pixel-paint.md) 为本app的基础能力执行合同（已交付归档），实施与双端验收见计划 §8/§9 与 [T-01 能力决策](docs/plans/evidence/001/capability-decision.md)。
总状态与前置见 [AutoOS B类总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。基础能力通过后再考虑Linux；A类统一等待 auto-os-distro 完成 Nix＋COSMIC 基础，后续增强另会话。

开发使用独立 clone `D:/autostack/auto-paint` 的 main；AutoOS 内对应子模块仅固定已交付提交，流程见 [App开发与子模块](https://github.com/auto-stack/auto-os/blob/main/docs/design/strategy/app-submodule-workflow.md)。


## 当前后续计划（2026-11-02）

[PAINT-002：独立运行、跨重启工程与SVG验收](docs/plans/002-standalone-project-and-svg.md) 为 **execution_done/r1、5/7（work完成，待独立复审）**。两profile真实编辑/跨进程强杀重开/下一次编辑/SVG逐格oracle已全绿；修复vue后端断开导出假成功（app.at Export try/catch，PAINT-002唯一实证业务缺口）；Spec SD-01修订/SD-02新增已随work提交，待复审确认。

T-00决策稿见 [docs/plans/evidence/002/standalone-decision.md](docs/plans/evidence/002/standalone-decision.md)；探针与负控原始证据在 `D:/autostack/plan-artifacts/paint-002/`（本地，不入库）。复审通过后由merge归档/push。

[路线图](docs/roadmap-v0.6.md) · [现实现规范](docs/specs/paint/basic-capabilities.md) · [独立运行规范](docs/specs/paint/standalone-runtime.md)。开发与顺序复审在D:/autostack/auto-paint独立clone main，一app一写入者（复审期间暂停实现写入）；不在OS组合子模块开发，不建junction/symlink。归档/merge只完成本app的Spec/计划/提交push与自有临时产物收尾，不更新AutoOS gitlink、manifest或.gitmodules。

保留16×16与SVG范围。VM文件KV、Vue同源localStorage不自动共享（两个已声明profile，不互享不是数据丢失）。PNG、图层/大画布和跨端同步另排。
