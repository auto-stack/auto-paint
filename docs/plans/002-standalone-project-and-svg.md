---
plan_id: PAINT-002
status: drafting
feature_name: "独立运行、跨重启工程与SVG验收"
author: [Codex]
created_at: 2026-11-01
updated_at: 2026-11-01
plan_revision: 1
current_step: 1
total_steps: 7
base_branch: main
base_commit: c1301656e5575f799875c51f31125e6557cb54d2
depends_on: ["PAINT-001"]
supersedes_spec_components: ["docs/specs/paint/basic-capabilities.md"]
new_spec_components: ["docs/specs/paint/standalone-runtime.md"]
touched_goals: []
---

# PAINT-002：独立运行、跨重启工程与SVG验收

## 0. 变更摘要

001已交付16×16可靠像素工程与SVG，本计划收口当前工具链独立运行、跨进程重开与真实导出。以验证和必要修复为主，不将画板扩为专业绘图软件，也不强行要求Rust后端。

## 1. 目标

从本仓准备/启动原生VM或Vue＋VM HTTP，真实操作编辑/撤销重做/保存，关闭进程后同一存储重开逐格一致并可再次编辑；独立SVG与画布逐格匹配，失败不假成功。无实证业务缺口时允许零业务源码改动。

非目标：PNG、多尺寸/图层/笔刷/压感、跨端自动共享存储、云同步、OS集成/Linux。

## 2. 架构方案

本仓为主导仓，开发/检查/最终复审顺序使用 `D:/autostack/auto-paint` 独立clone的 `main`，一app一写入者，复审时暂停实现写入；不在AutoOS子模块开发，不建junction/symlink。框架若确有缺项，先核实现有公共能力和当前实际owner，再在owner仓另立最小前置并遵守其worktree规约，本计划不授权越仓改实现。

应用业务保持纯.at；复用既有仓储、UI、测试，不手写业务Rust、不改生成Rust/Vue来交付。源知识为docs/specs；本轮只列Spec提案，不写canonical、旧specs.json或手工索引。未知技术方案由T-00有界调查，不能靠占位/必需skip关闭验收。

独立运行门使用新建且本次拥有的临时数据/端口/构建输出；不删除既有app/框架target、不停止他人实例。CLI和真实编译/渲染tool都记版本/hash及发现路径；进程清理按本次spawn归属，不凭端口或命令行相似就杀进程。冷准备允许耗时，但须有阶段、就绪判定、有界超时和非零失败；预算及资源边界在T-00先冻结。

保持.hex像素真值、PAINT-V2及v1只读迁移；原生文件KV与Vue同源localStorage仍是两个已声明的存储profile，不把跨profile不共享当数据丢失，也不声称全端同步。正式VM启动复用现有 `auto run -r vm`；Vue导出须 `auto run -r vue --server vm`，工具实际行为由T-00核对。

## 3. 技术栈

现有.at、AutoUI storage/VM HTTP、SVG、MCP/Playwright。复用tests/basic/verify_basic.py、desktop_mcp.py及独立XML/256格oracle，不新增绘图引擎。

## 4. 需求分析与背景调查

用户2026-11-01要求接续其余原B类应用的下一步计划，沿上一轮“计划/README/roadmap、提交push，不开始实现、不更新OS子模块”的范围执行。Reader已转另一个会话按Readest新目标跟踪；Blog现有上游阻塞由原计划继续，Chat/Charts不在本轮改面。应用单独运行不等OS装配或其他app；Linux仍WAIT_DISTRO_M1（Nix＋COSMIC基础）。

001记录VM27/27、Vue22/22及desktop_mcp31项，历史全同盘恢复债当前已不复现并有固定反例。本轮未发现必须追加绘图功能的证据；需核实当前工具下是否真跨进程重开同一profile、导出后端可达、冷缓存及失败门自足。

Spec明确Vue本地存储与VM KV不同，默认Rust生成并非支持profile。原导出API写后回读验证成功，失败对既有输出目标的实际语义应在T-00核实，不承诺SDK没有提供的掉电原子性。

| 来源文件 | SHA256 |
|---|---|
| `docs/specs/paint/basic-capabilities.md` | `f51971f8933944295d147c203c74f01c30f5496c32f1d58e4fc664cb35de2d23` |
| `src/front/app.at` | `240c59264591c8e60074e2e6d3b8a922a39d0c5a3c9aecde73e993dcf9f82858` |
| `src/back/api.at` | `d9a6f777c1958057466c730729975a4f6ecbef604b4b6382d29616fdcf085a88` |
| `tests/basic/verify_basic.py` | `565ce84a7af66ba38592fd1df4a00dc2c4626c3ea1fa56afb24573650c93a47a` |
| `tests/desktop_mcp.py` | `600c310a8a7368a091ea555d2d655a0fb092d726d2289e53a80350c81caf41ab` |

## 5. 详细设计

T-00新增 `docs/plans/evidence/002/standalone-decision.md`：固定CLI/tool、两个正式profile与后端生命周期、原生 `AUTO_VM_STORAGE_FILE`/Vue持久浏览器profile、冷准备和导出错误预算。探针与现有门都只能用自有临时存储，不能清用户浏览器数据。

继续用 `python tests/basic/verify_basic.py --profile vm|vue`；T-02补不足的跨进程/强杀后重开与下一次编辑。全白/全黑/稀疏图案、v1迁移/坏v2拒绝及SVG逐坐标颜色oracle保留。真实UI点击保存/加载/导出，独立文件解析是oracle，不直接写KV或注入像素来替代用户编辑证明。

成功导出需实际文件可独立解析、16×16/256格身份与画布一致；中文/空格路径作合法样本。空路径、坏路径、后端不可用时失败可见且工程/当前画布保留，解除后下一次导出成功。旧目标存在时的覆盖/失败语义由T-00明确，不在失败时伪称旧输出仍完整；若现路径破坏用户旧输出，需最小保全修复并验证。

### 规范增量

| delta_id | add/modify/retire | docs/specs/... target | before/after rule | rationale | acceptance IDs |
|---|---|---|---|---|---|
| SD-01 | modify | docs/specs/paint/basic-capabilities.md | 保留16×16/V2/SVG，补当前重开/失败/覆盖实证边界 | 使运行与数据声明准确 | AC-02/03 |
| SD-02 | add | docs/specs/paint/standalone-runtime.md | 两正式profile、存储身份/冷准备与永久门 | 独立运行可重复 | AC-01/03 |

## 6. 测试设计

P用例owner_stage=work，T-02在既有入口建立所缺用例；不把重新生成一张同样的图当作恢复。

| Case ID | AC | 输入/入口 | oracle/预期 | 边界 |
|---|---|---|---|---|
| P-01 | AC-01 | 两profile独立准备/首启，坏tool/端口冲突/无导出后端 | 实际可画、声明的服务可达；错误可见且清理只及自有资源 | VM HTTP是合法后端 |
| P-02 | AC-02 | UI编辑稀疏图/全白/全黑、撤销重做、保存后正常/强杀重开 | 同一存储256格逐项一致；再编辑/保存/重开仍对；Vue复用持久profile | 不要求Vue↔VM自动迁移 |
| P-03 | AC-02/03 | UI导出到中文/空格路径；空/不可写/既有目标与后端断开 | 独立XML和像素oracle匹配；失败工程不变、语义明确，恢复后成功 | 非PNG/掉电原子保证 |
| P-04 | AC-03 | v1迁移/坏快照拒绝、故意恢复错色或缺导出等反例 | 错数据断言红且整体非零，合法对照通过，无必需skip/零场景 | 复用001数据不删反例 |

最终review同clone独立上下文检查存储身份和真实再次打开；不只看screenshots或同一内存store。无缺陷则交付验证/文档增量，不强改业务代码。

## 7. 验收标准

- AC-01（owner_stage=work）：两个正式profile准备/首启和失败收尾自足，P-01通过。
- AC-02（owner_stage=work）：实际编辑/工程存取、跨进程重开及下一次编辑、真实SVG一致，P-02/03通过。
- AC-03（owner_stage=work）：兼容/失败保全和失败控制、永久入口与SD候选对应真实边界，P-03/04通过。
- AC-04（owner_stage=review）：冻结实现/依赖独立复审AC-01..03和SD-01/02。
- AC-05（owner_stage=merge）：仅app规范/新计划归档计数/提交push收尾，不更新OSpin。

## 8. 执行步骤

- [x] T-00（owner_stage=work；依赖001；AC-01..03）：核实正式profile/持久存储/后端/覆盖失败语义，输出有界决策稿。
  [✅ 已完成 2026-11-02] 决策稿 docs/plans/evidence/002/standalone-decision.md；§4 五SHA零漂移；探针 D:/autostack/plan-artifacts/paint-002/t00/（plan-002 目录被 DATABASE-002 占用，改用 paint-002）。VM：强杀重开→Load逐格一致→再编辑、中文/空格路径字节级oracle、既有目标整体覆盖、失败可见+恢复 全绿。vue：persistent profile 强杀浏览器重开一致、后端断开导出假成功（stale exported，生成器裸 await 抛出）为唯一实证业务缺口 → app.at try/catch 最小修复转 T-02。
- [ ] T-01（owner_stage=work；依赖T-00；AC-01）：在既有门固定自有资源、准备/首启和错误判定，不强制Rust或清共享缓存。
- [ ] T-02（owner_stage=work；依赖T-01；AC-02/03）：补P-01..04的真实重开/导出与反例，回放旧矩阵；只修实证缺口。
- [ ] T-03（owner_stage=work；依赖T-02；AC-03）：证明失败后再次编辑/导出及负控非零，准备SD候选。
- [ ] T-04（owner_stage=work；依赖T-03；AC-01..03）：核对漂移/覆盖，更新README/roadmap并提交execution_done。
- [ ] T-05（owner_stage=review；依赖T-04；AC-04）：同clone独立上下文最终复审。
- [ ] T-06（owner_stage=merge；依赖T-05 pass；AC-05）：仅app规范/归档/提交push收尾。

## 9. 复审记录

- stage: new | plan_id: PAINT-002 | plan_revision: 1 | outcome: pass（有界T-00准备就绪；本轮没有实现或产品验收） | next: work/T-00（等待后续实施指令）。
- 已归档001、现实现Spec和产品源码保持不变；规划结构/链接通过不等于功能通过。review以同一clone的独立上下文核验，不自动创建agent/chat或指定模型。

## 10. 待澄清事项

当前没有需要用户重复确认的产品方向。技术不确定性由T-00记录真实证据、owner与依赖任务；若需要改变目标、削减必需验收或扩大跨仓写入范围，先明确报告，受影响任务保持未完成。归档/merge只完成本app的Spec/计划/提交push与自有临时产物收尾，不更新AutoOS gitlink、manifest或.gitmodules；后续OS统一计划接收已单独验证的固定SHA。
