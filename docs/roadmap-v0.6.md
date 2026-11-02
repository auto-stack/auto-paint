# auto-paint：独立可用性路线图

更新：2026-11-02。以Spec与真实交付为准，计划目标不表示已实现。

| 顺序 | 计划/成果 | 当前状态与边界 |
|---|---|---|
| 基础 | [001首轮能力](plans/archived/001-reliable-pixel-paint.md) | 001已交付归档/r2、7/7；16×16/V2工程/SVG，VM27/27、Vue22/22和desktop_mcp31项为001冻结记录。 |
| 已交付 | [PAINT-002：独立运行、跨重启工程与SVG验收](plans/archived/002-standalone-project-and-svg.md) | 002已交付归档/r1、7/7（独立复审3轮pass，R-1..R-4关闭）：VM50/50×5连续绿、Vue45/45、desktop_mcp31/31+坏tool负控非零；修复vue后端断开导出假成功；Spec SD-01修订/SD-02新增已落地。 |
| 之后 | AutoOS统一装配 | 另立统一OS计划，接收各app单独验证/推送的精确提交；本轮不改pin |
| 之后 | Linux支持 | WAIT_DISTRO_M1，等Nix＋COSMIC发行版基础；不阻塞本app本机任务 |

固定原生KV与Vue同源localStorage两个profile，复验真实编辑、跨进程重开、下一次编辑和SVG逐格oracle；不强加新绘图功能。002实测：强杀进程/浏览器树后同一存储/持久profile重开逐格一致、再编辑有效；中文/空格路径、既有目标整体覆盖、后端断开显式失败+恢复成功；oracle变异反例非空洞。

PNG、图层/大画布另排，不要求Rust后端或跨端自动共享工程。

工作位D:/autostack/auto-paint独立clone main，实施与独立上下文复审顺序共用，一app一写入者（复审期间暂停实现写入）。复用既有验证入口；真实UI/磁盘oracle对应本次源码和CLI/tool（auto plan-890-verified-r7-t19-14-g47d8f7b），无必需skip/零场景。失败控制要能检测实际错误，只回收本次进程/隔离数据，不清共享缓存。

[README](../README.md) · [现实现规范](specs/paint/basic-capabilities.md) · [独立运行规范](specs/paint/standalone-runtime.md)
