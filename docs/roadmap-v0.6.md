# auto-paint：独立可用性路线图

更新：2026-11-01。以Spec与真实交付为准，计划目标不表示已实现。

| 顺序 | 计划/成果 | 当前状态与边界 |
|---|---|---|
| 基础 | [001首轮能力](plans/archived/001-reliable-pixel-paint.md) | 001已交付归档/r2、7/7；16×16/V2工程/SVG，原VM27/27、Vue22/22和desktop_mcp31项为冻结记录。 |
| 当前优先 | [PAINT-002：独立运行、跨重启工程与SVG验收](plans/002-standalone-project-and-svg.md) | drafting/r1、0/7，未实施；先T-00核实当前工具/SDK与实际owner |
| 之后 | AutoOS统一装配 | 另立统一OS计划，接收各app单独验证/推送的精确提交；本轮不改pin |
| 之后 | Linux支持 | WAIT_DISTRO_M1，等Nix＋COSMIC发行版基础；不阻塞本app本机任务 |

固定原生KV与Vue同源localStorage两个profile，复验真实编辑、跨进程重开、下一次编辑和SVG逐格oracle；不强加新绘图功能。

PNG、图层/大画布另排，不要求Rust后端或跨端自动共享工程。

工作位D:/autostack/auto-paint独立clone main，实施与独立上下文复审顺序共用，一app一写入者。复用既有验证入口；真实UI/磁盘oracle对应本次源码和CLI/tool，无必需skip/零场景。失败控制要能检测实际错误，只回收本次进程/隔离数据，不清共享缓存。

本轮只规划/README/roadmap并push，不实现、不写现实现Spec/旧ledger或改001归档，不更新AutoOS子模块。Reader新目标由单独会话跟踪，Blog上游问题沿原合同继续，不作为本计划的全局前置。

[README](../README.md) · [现实现规范](specs/paint/basic-capabilities.md)
