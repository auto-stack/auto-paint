---
plan_id: PAINT-002
status: archived
feature_name: "独立运行、跨重启工程与SVG验收"
author: [Codex]
created_at: 2026-11-01
updated_at: 2026-11-02
plan_revision: 1
current_step: 7
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
- [x] T-01（owner_stage=work；依赖T-00；AC-01）：在既有门固定自有资源、准备/首启和错误判定，不强制Rust或清共享缓存。
  [✅ 已完成 2026-11-02]（↩ review R-1 重开 → 已修复复绿：settled_snap 静默判定+click重址+paint验证/回滚，连续2轮50/50绿）verify_basic.py：vue 档换运行自有 user-data-dir 持久浏览器 profile（launch_persistent_context）；进程/端口清理按 spawn 前 pid 窗口判定（外来占用者不清理）；P-01 门自足检查（自有存储/profile、有界就绪、外来端口可见）；坏 tool 负控 = 显式 FAIL + 退出码 1（negctl 实测 exit 1，无挂起）。
- [x] T-02（owner_stage=work；依赖T-01；AC-02/03）：补P-01..04的真实重开/导出与反例，回放旧矩阵；只修实证缺口。
  [✅ 已完成 2026-11-02]（↩ review R-1 重开 → 已修复复绿：红跑已在§9披露，修复后 vm×2/vue×2 连续绿）唯一实证业务缺口修复：app.at Export try/catch（vue 后端断开 fetch reject → 显式 "export failed"，根除 stale exported 假成功；vue 生成器实测正确发射 try/catch，VM 档休眠分支）。P-02：vm 强杀进程树两次重开逐格一致+再编辑；vue 强杀浏览器树持久 profile 重开一致+再编辑。P-03：中文/空格路径字节级 oracle、既有目标整体覆盖、后端断开失败可见+零文件+恢复成功。P-04：变异反例（单格改色 oracle 必红）。V-01..03 旧矩阵原样回放。验收：vm 48/48、vue 45/45（attachments/002 报告 JSON）。
- [x] T-03（owner_stage=work；依赖T-02；AC-03）：证明失败后再次编辑/导出及负控非零，准备SD候选。
  [✅ 已完成 2026-11-02]（↩ review R-1/R-3 重开 → 已修复复绿：新增 vm 未保存编辑反例（P-02 50项含2新检查），负控复跑 exit 1）失败后再次编辑/导出已证（P-02/P-03）；desktop_mcp 31/31 回放 exit 0；坏 tool 负控整体非零（exit 1）；变异反例 oracle 非空洞。SD 候选落地：SD-01 basic-capabilities.md 修订（后端断开/覆盖/路径词汇/P组入口）、SD-02 standalone-runtime.md 新增（两 profile/存储身份/冷准备/导出后端生命周期）。
- [x] T-04（owner_stage=work；依赖T-03；AC-01..03）：核对漂移/覆盖，更新README/roadmap并提交execution_done。
  [✅ 已完成 2026-11-02]（↩ review R-1 重开 → 已修复复绿：README/roadmap 计数更新为 50/45/31）§4 五 SHA 基线零漂移后才动手；README/roadmap 更新（新计数 48/45/31、AUTO_BIN 必填、002 状态）；本计划状态 execution_done 5/7。
- [x] T-05（owner_stage=review；依赖T-04；AC-04）：同clone独立上下文最终复审。
  [✅ 已完成 2026-11-02] 独立子代理三轮：round1 needs_fix（R-1 门竞态 40/8 红实锤+红跑未披露+R-2/R-3）→ 修复 15abfa2 → round2 R-1 残留两窄竞态+R-4 → 修复 b4f727c → round3 **OUTCOME: pass**（R-1..R-4 全关闭机制+实证确认；vm 50/0×5 跨两独立上下文连续绿含复审×2、vue 45/0×2、desktop_mcp 31/0；AC-01..04 全 pass；笔记 plan-artifacts/paint-002/review/rereview-round2-notes.md）。
- [x] T-06（owner_stage=merge；依赖T-05 pass；AC-05）：仅app规范/归档/提交push收尾。
  [✅ 已完成 2026-11-02] 本仓规约=main即交付线（无独立dev分支，增量落地，基线c130165→7提交线性）。canonical@tip：basic-capabilities.md 8a0bcf3f…、standalone-runtime.md 37dccb07…（=复审绑定内容）。归档 git mv→docs/plans/archived/，计划文件已提交默认分支（PLAN-104 UAT-K13）。收尾：plan-artifacts/paint-002/ 全删（evidence已折入计划+决策稿），retention registry 已刷新；push origin main；无部署工件需重建（app由源码 auto run 运行，验收即产线形态）；AutoOS pin未动；批量回归台账缺失=观察项（本仓全部门=三入口126项刚在交付树连续绿）。

## 9. 复审记录

- stage: new | plan_id: PAINT-002 | plan_revision: 1 | outcome: pass（有界T-00准备就绪；本轮没有实现或产品验收） | next: work/T-00（等待后续实施指令）。
- 已归档001、现实现Spec和产品源码保持不变；规划结构/链接通过不等于功能通过。review以同一clone的独立上下文核验，不自动创建agent/chat或指定模型。
- stage: work | plan_id: PAINT-002 | plan_revision: 1 | round: 1 | from: drafting | to: execution_done | outcome: pass | worktree: D:/autostack/auto-paint（本仓固定独立clone） | branch: main | base_commit: c130165 | code_commit: 见 git log（T-00 78cbec4，work段提交随后） | dependency_revisions: auto CLI 0.1.0+plan-890-verified-r7-t19-14-g47d8f7b（auto-man），auto-ui-tool 0.1.0 dcde8058 | task_ids: T-00,T-01,T-02,T-03,T-04 | evidence: docs/plans/evidence/002/standalone-decision.md；验收 vm 48/48、vue 45/45、desktop_mcp 31/31 exit 0；坏tool负控 exit 1；探针/负控原始记录 D:/autostack/plan-artifacts/paint-002/（本地scratch，不入库） | blockers: 无 | next_responsible_role: review（T-05 独立最终复审，AC-04）
  - 唯一实证业务缺口：vue 后端断开导出假成功 → app.at Export try/catch 修复，生成器实测正确发射；VM 档休眠分支不受影响。
  - 授权链：/goal 完成计划002 → /auto-plan-goal 全链授权（work/review/有界repair/merge）；scratch 用 paint-002 目录（plan-002 已被 DATABASE-002 占用）。
  - 统一回归门：本仓无独立统一回归（verify_basic 两档 + desktop_mcp 即全部门）；已全部在冻结码上通过。
- stage: review | review_scope: final | reviewer_identity: 独立子代理（同clone独立上下文，agent_cb81f411，未参与实现） | plan_id: PAINT-002 | plan_revision: 1 | outcome: needs_fix | worktree_path: D:/autostack/auto-paint | branch: main | reviewed_commit: 17e3334 | base_commit: c130165 | dependency_revisions: auto plan-890-verified-r7-t19-14-g47d8f7b / auto-ui-tool 0.1.0 dcde8058 | spec_inputs: basic-capabilities.md@17e3334、standalone-runtime.md@17e3334 | acceptance_results: AC-01 pass；AC-02/03 partial（R-1 门不稳定）；AC-04 pass（本复审完成） | pending_closeout_gates: 修复后连续绿轮次 + merge收尾 | findings: R-1(major) 验收门冻结码非确定——复审者vm首跑40/8红（杂散红格(12,7)/(12,10)，vnode重渲染竞态误址），work侧vue首跑43/2红（恢复段期望bug，已当轮修正但未在收据披露）；R-2(minor) SD-02"vue不带--server vm"无本轮实证（001记录未复验）；R-3(minor) SD-02"未保存内存编辑不跨进程"vm侧为推断无直接反例 | evidence: D:/autostack/plan-artifacts/paint-002/review/（review-notes.md+5门日志）；红证 verify-vm-1793625067.json(40/8)、verify-vue-1793624446.json(43/2)；绿证 verify-vm-1793625292.json(48/0)、vue 45/0、desktop 31/0 | next: work（修R-1 harness竞态+披露红跑+R-2/R-3补证，连续绿后同agent复审）
- stage: work | plan_id: PAINT-002 | plan_revision: 1 | round: 2（repair R-1/R-2/R-3） | from: executing | to: executing（待复审确认） | outcome: pass（修复完成） | worktree: D:/autostack/auto-paint | branch: main | base_commit: c130165 | code_commit: 见 git log（repair 提交） | dependency_revisions: 不变 | task_ids: T-01,T-02,T-03,T-04（reopen→fix） | evidence: R-1 修复——VmSession.settled_snap 快照静默判定（连续两次结构一致才定址，杜绝重渲染期 vnode 误址）；click 未命中/类型错自动重址一次；paint(…, expect) 逐次验证落格、杂散即 Undo 回滚重试（≤3）；vue P-03 恢复段 Load 首次不符自动重载重试。R-3 修复——P-02 新增 vm 未保存编辑反例两检查（live 可见→强杀重开后不在，vm 计数 48→50）。R-2 修复——standalone-runtime.md 两处措辞收敛（001 记录标注未复验、反例指针）。红跑披露（review 要求）：work 期 vue 首跑 43/2 红系恢复段期望 bug（当轮复跑复绿，期望守卫在修复提交落地；verify-vue-1793624446.json）；复审者 vm 首跑 40/8 红系 harness vnode 竞态（verify-vm-1793625067.json，本修复目标）；两者均非 app 业务缺陷。修复后门矩阵：vm 50/0×2、vue 45/0×2、desktop_mcp 31/0、坏tool负控 exit 1（verify-vm-1793625743/1793625913.json、verify-vue-1793625978/1793626128.json，日志 plan-artifacts/paint-002/review/post-fix-*） | blockers: 无 | next_responsible_role: review（复审确认 R-1..R-3 关闭）
- stage: review | review_scope: final | reviewer_identity: 独立子代理 agent_cb81f411（同clone独立上下文，未参与实现；round3 复审） | plan_id: PAINT-002 | plan_revision: 1 | outcome: pass | worktree_path: D:/autostack/auto-paint | branch: main | reviewed_commit: fca907b（业务码=17e3334 未动，修复仅 harness+收据） | base_commit: c130165 | dependency_revisions: auto plan-890-verified-r7-t19-14-g47d8f7b / auto-ui-tool 0.1.0 dcde8058 | spec_inputs: basic-capabilities.md@fca907b、standalone-runtime.md@fca907b | acceptance_results: AC-01 pass、AC-02 pass（vm×5 连续绿跨两上下文含复审×2）、AC-03 pass、AC-04 pass | pending_closeout_gates: T-06 merge（spec落地核验/归档/push/收尾） | findings: 无开放（R-1..R-4 全关闭；非阻塞观察：rr2 vm1 exit1 判工具链环境噪声未复现、set_path 理论窗口受响亮失败守卫） | evidence: rereview-round2-notes.md + rr2-gate-* 日志（plan-artifacts/paint-002/review/） | next: merge
- stage: work | plan_id: PAINT-002 | plan_revision: 1 | round: 3（repair 续：复审round1后R-1残留+R-4） | from: executing | to: executing（待复审确认） | outcome: pass（修复完成） | worktree: D:/autostack/auto-paint | branch: main | base_commit: c130165 | code_commit: 15abfa2→b4f727c | dependency_revisions: 不变 | task_ids: T-01,T-02（harness only，app.at 未动——复审确认修复范围正确） | evidence: 复审round1确认 R-2/R-3/披露关闭、stray-paint 腐蚀模式消灭，残留两个更窄竞态：Mode A（Load 后 px 读取抢跑 RebuildCells）、Mode B（Export press 丢失于 set_path→渲染窗口）+R-4（收据"当轮已修"措辞过强）。修复：Load/Save 终态等待（wait_status/_press_to_status，终端状态是 handler 最后一句→px/文件已完成）；export_verify 效果判定（文件字节/失败状态，规避状态栏 stale 终值假匹配——首轮 press_to 即因此 43/2 红）；R-4 措辞改为"当轮复跑复绿"。红跑披露：rr2 首批 vm1 app 中途 exit 1（工具链已知间歇不稳，T-00 决策稿有记，当批 vm2/vue 复跑即绿，未复现）、vue 43/2（press_to stale 缺陷，本轮 export_verify 根除）。修复后门矩阵：vm 50/0×3 连续（verify-vm-1793627629/1793627783/1793627977.json）、vue 45/0（verify-vue-1793627829.json）、desktop_mcp 31/0（rr2b-* 日志） | blockers: 无 | next_responsible_role: review（round 2 复审：≥3 连续绿独立复跑）

- stage: merge | plan_id: PAINT-002:r1 | outcome: pass | delivery: main 线性 c130165→39033d0（work 78cbec4/17e3334，repair 15abfa2/b4f727c，receipts fca907b/39033d0） | checkpoints: prepared（reviewed fca907b=交付内容；spec targets docs/specs/paint/{basic-capabilities,standalone-runtime}.md）→ landed（本仓规约 main 即默认分支，无 rebase/ff 步骤；tip=归档提交）→ canonical_verified（hash 8a0bcf3f…/37dccb07…@tip；smoke=同树 5 连续绿门）→ archived（docs/plans/archived/002-standalone-project-and-svg.md，status archived，7/7）→ cleaned（无独立worktree可清；plan-artifacts/paint-002/ 全删+registry 刷新） | landing_checks: app 由源码 auto run 运行（验收即产线形态），无发布二进制/web bundle 需重建；AutoOS gitlink/manifest/.gitmodules 未动 | batch_regression: docs/plans/.last-batch-regression.json 缺失——本仓无批量台账（001 亦无），全部门=verify_basic vm50/vue45+desktop_mcp31 已在交付树连续绿，登记为观察项 | push: origin/main | completion_kind: delivered
## 10. 待澄清事项

当前没有需要用户重复确认的产品方向。技术不确定性由T-00记录真实证据、owner与依赖任务；若需要改变目标、削减必需验收或扩大跨仓写入范围，先明确报告，受影响任务保持未完成。归档/merge只完成本app的Spec/计划/提交push与自有临时产物收尾，不更新AutoOS gitlink、manifest或.gitmodules；后续OS统一计划接收已单独验证的固定SHA。
