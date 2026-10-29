---
plan_id: PAINT-001
status: drafting
feature_name: reliable-pixel-paint
author: [Codex]
created_at: 2026-10-29
updated_at: 2026-10-29
plan_revision: 2
current_step: 3
total_steps: 7
supersedes_spec_components: []
new_spec_components: [docs/specs/paint/basic-capabilities.md]
touched_goals: []
---

# PAINT-001：可靠像素画板、保存恢复与作品导出

## 0. 变更摘要

沿用 16×16 像素画板，修复全同色快照恢复并补可用的作品文件输出。

本轮只起草执行合同：没有实施功能、运行功能验收或将本app升为A类。auto-paint 的基本能力补齐不依赖 auto-os-distro；Linux 支持另等 Nix＋COSMIC 基础完成，增强设计另会话。

## 1. 目标

完成一张像素作品，能撤销/重做，可靠保存/重开，并导出可在其他程序打开的图像文件。

非目标：自由笔触/大画布、图层、专业笔刷、压感、截图工具、云同步、Linux 适配。PNG 不作为本次必需编码器；首版图像输出固定为 SVG。

## 2. 架构方案

应用逻辑继续纯 `.at`，前端/后端沿 AutoUI 现有结构；本仓为主导仓。应用工作检出固定 `D:/autostack/auto-paint`（独立开发clone），工作分支 `main`；执行/复审共用此检出，一个写入者。**复用该独立clone，不在组合子模块内并行开发，不建任何junction/symlink**。框架缺口在实际owner仓另立前置并按其worktree纪律执行，不在app手写Rust、修改生成Rust或绕过公开SDK。

领域像素用受验证颜色值而非 Tailwind 类作真值；明确 16×16/256 像素。保留并迁移既有 paint.canvas.v1（旧格式实际颜色映射由 T-01 核实），坏数据不覆盖当前画布。可恢复工程与 SVG 图像分开：工程保存尺寸/色值/版本，SVG 固定画布、单元格和安全颜色；写入结果不能用无条件 saved 标记。

跨仓总表：[B类基本能力总跟踪表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)。源Spec以所属仓 `docs/specs/` 为准；当前没有该app的canonical模块规范，旧根 `SPEC.md`（如有）只是历史Demo观察/再生描述，不能据此宣布真实功能已完成。新规范路径将在实际复审/merge后落地，本轮不写入已实现Spec。

## 3. 技术栈

Auto / AutoUI、当前匹配的AutoLang/AutoUI/AutoMan工具组合、各app已有widget/store/API；具体存储与平台接缝由T-01用实际源码和探针确认。Vue / VM 两端均需真实任务验收，不因某一后端不通就删掉原任务；如必须显式指定 server=vm 等启动profile，应先验证并记录到执行入口/README，不能静默换成mock。

## 4. 需求分析与背景调查

授权：用户于2026-10-29要求建立总跟踪表、复用Notes/Reader/Blog现有计划，并为其余B类应用准备基本能力补齐计划。此处授权的是**计划准备和必要的文档/组合版本登记**，不宣称已授权/完成本计划具体功能实现，不推定全量竞品复刻或Linux开发已启动。

2026-10-29用户明确改用 `D:/autostack/<产品仓名>` 独立clone开发，先push应用再更新子模块pin；此修订仅更新工作位置、跨仓链接和交付状态描述，功能目标、T-01..07依赖、work验收与Spec增量不变，不重置任务。旧开发位置被此用户决定替代。

冻结的观察基线：`a12bb20073e20a9ca3cc62b995af88cde66a75f7`（在本app `main` fetch origin后ff核对）；执行前重新核对HEAD/pin/WIP并记录变化。主产品统计为27个去重产品，B类9个；AutoJade旧名Jade Garden不重复计数。

SPEC.md 登记 P553-D1：VM 全同串列表在 Redo/Load 塌缩；app.at Save 直接 storage.set 后标 saved；尚无文件导出。根 SPEC 是现有 v1 观察，非已完成新能力。

已读来源（源码/文档观察，不是本轮实测）：

- `src/front/app.at`：SHA256 `5ff7495d2e6e6b2ffe0f3779635c5378775abc084f5837ef0a54ed5b9d953c97`。
- `SPEC.md`：SHA256 `7d19c7764428c1ffd61e060e9ffda851c3b4ed61dbfca73c7943bb08c8838810`。
- `pac.at`：SHA256 `3c7125467411f83c50bebad3e82ed0afe9e4eae023a6e370aa95fffff8154ada`。
- `tests/desktop_mcp.py`：SHA256 `600c310a8a7368a091ea555d2d655a0fb092d726d2289e53a80350c81caf41ab`。

## 5. 详细设计

### 执行入口和依赖

首个就绪任务仅T-01：在上述应用检出核对版本、清单、当前工具链、真实API与测试入口，用隔离数据跑能力探针。输出允许后续实现依赖的接口与不支持项；缺口需具名指向owner/前置计划及关闭条件。不得假造未存在API、跳过基础正确性，或以“将来Linux会解决”替代当前端的基本能力。

T-02..04按下列任务依赖顺序推进；T-05将本节拟议测试做成真实可复现入口，T-06/07保持未来阶段未勾选。合并后只有基础合同的全部必需工作/复审通过且父仓pin指向交付版本，才更新总表分类。发布包/所有Linux发行版不在本计划的成功声明里。

### 规范增量

| delta_id | action | docs/specs target | before/after rule | rationale | AC |
|---|---|---|---|---|---|
| SD-01 | add | `docs/specs/paint/basic-capabilities.md`（新） | Demo/未定义 → 本计划首版用户任务、数据模型和准确支持范围 | 以真实基本能力作为产品准入 | AC-01/02 |
| SD-02 | add | 同上，失败/恢复及交互节 | 未定义 → 保存/输出/失败、重启和两端行为的可验合同 | 防止假成功、旧数据丢失和单端冒充 | AC-03/04 |

根README/历史SPEC在实现落地时反链canonical目标，保留历史来源、不覆盖未经审查的旧约定；本计划不在draft阶段修改canonical知识或ledger。

## 6. 测试设计

本轮没有执行下列功能测试。先以真实应用入口和真实文件/服务为准，既有脚本若只验证演示数据，需要补有辨别力的真实数据正反例；禁止仅把UI文案变绿或用相同生产函数生成期望值。

| case_id | AC/task与责任 | 输入/设置 | 实际入口 | 必须观察的结果 |
|---|---|---|---|---|
| V-01 | T-01..05 / AC-01..04；由T-05制作永久回放 | 256格同白/同黑、单点/棋盘格 | 真实绘制/Save/Load/Undo/Redo UI | 每次读取的像素向量长度256且色值逐项一致。 |
| V-02 | T-01..05 / AC-01..04；由T-05制作永久回放 | 导出后独立打开 SVG | 真实导出→XML解析→图像渲染 | 画布16×16、像素位置/颜色与源模型一致；输出不含未转义内容。 |
| V-03 | T-01..05 / AC-01..04；由T-05制作永久回放 | 255项、非法颜色、旧v1与不可写路径 | Load/迁移/Save/Export | 拒绝坏输入而不改当前画布/原文件；合法旧作品可重开。 |

测试隔离：所有文件/数据库/服务均使用临时用户数据目录及明确测试端口，不接触真实用户数据；占用端口/不可写/损坏时明确失败。多个实例/取消/退出与恢复按本计划声明范围验证。资源预算若需限制，T-01明确单位/语义/拒绝或截断结果并在dependent实现前冻结；没有提出上限不等于无限规模承诺，不以隐藏硬上限代替验收。

可复现入口（**均由T-05新增/接通**）：`python tests/basic/verify_basic.py --profile vue`、`python tests/basic/verify_basic.py --profile vm`。入口应实际调用应用后端与两端UI，记录源码/工具/依赖版本、fixture hash及运行结果；不得仅调内存helper替代。按可用工具复用现有Playwright或VM MCP/autoui-verifier驱动。T-01记录真实启动命令、数据env、端口与适用CLI参数；两端都要证实实际支持的用户任务。

角色：本轮仅起草，没有派执行/复审agent。实现与最终复审按四技能分阶段；无明确独立上下文时如实声明并从工件重建，不能自称独立或擅自创建新会话/agent。只改app不触auto-lang crates时禁止跑其cargo t/docs_gen；框架前置按owner自己的门档验证。

## 7. 验收标准

| ID | owner_stage | observable / verification |
|---|---|---|
| AC-01 | work | 像素编辑正确：现有铅笔/橡皮/填充/吸色与撤销/重做保持正确；256格不因颜色一致而丢格。 |
| AC-02 | work | 存储完整：全白、全黑、单像素和混合图案保存→退出→重开/Redo 后256项及每格颜色一致，原 P553-D1 不得 SKIP 作为通过。 |
| AC-03 | work | 可用导出：用户指定路径导出独立 SVG；独立 XML/像素模型检查尺寸、位置和颜色，真实渲染可打开，不能仅把类串写入 SVG。 |
| AC-04 | work | 异常与双端：坏工程、旧v1数据、路径不可写/中断的失败可见且保留当前/已保存作品；Vue/VM 都完成绘制→保存→重开→导出。 |
| AC-05 | review | 冻结已提交实现与依赖，逐个重验AC-01..04和独立反例；核对SD-01/02与范围、实际证据，输出明确review结论；未闭项不可忽略。 |
| AC-06 | merge | 通过对应最终门后交付main并推送，父仓gitlink和组合验证可追溯；canonical/ledger/归档收尾完成，组合子模块显式detached，独立开发clone留在main；总表有证据地标A，A类Linux仍等待发行版前置。 |

## 8. 执行步骤

- [x] T-01（owner_stage=work；依赖 无；AC-01..04）：基线与全路径探针：复现全白/全黑/混合颜色的保存/重开与撤销；验证 Auto 列表/序列化替代表示、可靠存储结果和实际文件输出。SVG 是首版确定格式，不依赖未验证的 PNG 编码器。若需后端写文件，17835 为候选，先核端口/权限；框架缺陷须闭合或证明等价应用方案，不仅取消 SKIP。 输出新文件 `docs/plans/evidence/001/capability-decision.md`，记录可用API、版本/资源边界、缺项owner和最小闭环。
  [✅ 已完成 2026-10-29] 基线 HEAD=origin/main=56025f2、四文件冻结hash一致；VM轨 desktop_mcp **31 PASS/0 FAIL/0 SKIP**（P553-D1 全同盘 Redo/Load 在工具链 v0.0.20-117-g873fa23 未复现）；VM 进程内 back.api→fs.write 真实落盘（tmp/probe-app/probe-out.txt）；vue split（`-r vue --server vm`，front17834/back17835）POST /api/probe/export 写文件+回读一致；fs.write 失败静默→导出用回读比对闭环；旧 v1 storage 实为 256 段 ` bg-[#rrggbb] ` 类串（非hex）；vite 绑 localhost 不绑 127.0.0.1。详见 `docs/plans/evidence/001/capability-decision.md`。
- [x] T-02（owner_stage=work；依赖 T-01；AC-01..04）：可恢复像素模型：将 CSS 展示与颜色真值分离，补版本化工程格式、旧 v1 安全读取/迁移，拒绝非256项或非法色值。
  [✅ 已完成 2026-10-29] `app.at` 改为 hex 真值（词表=16色板+白，闭合集合）+ `chip_of` 展示派生（字面类串留源码保 JIT）；`paint.project.v2`="PAINT-V2|16|16|<hex×256>"，Save 写后回读比对才置 saved；Load 优先 v2（版本/尺寸/逐项校验）、无 v2 只读迁移 v1（` bg-[#hex] `→hex，split 消费 `#` 的坑已修），非256项/非词表色整体拒绝不动画布。验证：desktop_mcp **31/0/0**；隔离存储探针 `tmp/t02_probe.py` **12/12**（v1全红迁移/255项拒绝/坏v2头拒绝/存→清→载全串逐项一致/泛洪后双 undo 经混合快照到全白 uniform 恢复、px 未塌缩）。vue 端 `auto run -r vue --server vm` 编译+服务正常（默认 `auto run` 走 rust 后端会失败——启动 profile 已定，T-05 记入 README）。
- [x] T-03（owner_stage=work；依赖 T-02；AC-01..04）：可靠存取与图像输出：修复 Undo/Redo/Load 全同色退化；实现实际工程保存回读与 SVG 文件导出；失败不改已保存版本、不破坏旧文件。
  [✅ 已完成 2026-10-29] 全同色退化在 T-02 已实证不复现（uniform 双 undo/redo/载全过，desktop_mcp 31/0/0 复跑）；工程保存回读 T-02 已验（全串逐项比对）。SVG 导出落地：`src/back/api.at` `#[api] export_svg(path,content)`（fs.write+回读返回磁盘实文，fs.write 失败静默→前端全串比对闭环）；`pac.at` back_port 17835；`app.at` Export/SetPath + `build_svg`（16×16 白底+非白格 crispEdges rect，词表色无转义面，col=k%16/row 减法环）。验证：VM 轨 `tmp/t03_probe.py` **13/13**（空路径拒绝/单红格导出→XML 解析 16×16 2 rect (0,0) 红/无未转义内容/目录路径→"export failed" 可见且画布不变）；desktop_mcp 复跑 **31/0/0**；vue split（17834/17835）POST /api/paint/export 写文件+回读一致，生成 App.vue 含 Export/SetPath/export_svg 接线（浏览器级 UI 驱动归 T-05 双端验收）。
- [ ] T-04（owner_stage=work；依赖 T-03；AC-01..04）：用户操作闭环：沿用现有画笔/填充/吸色与20步撤销范围，增加明确保存/加载/导出状态和路径；失败保留当前作品，不追加新绘画功能。
- [ ] T-05（owner_stage=work；依赖 T-02..04；AC-01..04）：完成独立数据/失败回放和两端真实UI验收，新建 `tests/basic/verify_basic.py` 调度入口（可复用既有脚本），同时保存命令/输入hash/真实结果与原始失败；准备 canonical Spec 增量，提交实现，转 execution_done。
- [ ] T-06（owner_stage=review；依赖 T-05；AC-05）：在同一app检出暂停实现，按冻结提交、真实数据和独立反例最终复审；核对Spec增量与双端结果，说明上下文独立性限制；未满足返回修复，不将数据错误降为债务。
- [ ] T-07（owner_stage=merge；依赖 T-06；AC-06）：完成实际提交/推送/父仓gitlink验证，沉淀canonical Spec与derived ledger、归档；刷新总表A/B与证据，组合子模块显式detach，独立开发clone留在main。Linux仍等待发行版门，不因文档或脚本存在宣布已可用。

## 9. 复审记录

- 历史 r1起草回执见 `0901c657337b33dfd1ca0d87d860947d83ed98c4`；其开发位置/收尾状态描述由本次修订替代，既有功能与验收合同保留。
- stage: new | plan_id: PAINT-001 | plan_revision: 2 | outcome: pass（独立clone路径修订就绪；功能未实施/未验收） | next: work/T-01（另行执行）。
- 本次只改工作位置、跨仓链接与AC-06/T-07的检出收尾说明，不变更基础能力要求；独立clone开发，组合子模块只固定已交付版本。
- 本轮核对源码/Spec缺口、历史任务、路径、基线和计划唯一性；未执行实现/功能测试，所有7项任务保持未勾选；通过的是草案结构/相互引用检查，不是产品验收。

## 10. 待澄清事项

无必须先向用户确认的产品身份问题；技术可行性与资源边界由 T-01 冻结，缺口保持具名阻塞。
