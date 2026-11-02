# PAINT-002 T-00 独立运行决策稿（standalone-decision）

- 日期：2026-11-02
- 执行检出：`D:/autostack/auto-paint`（独立开发 clone，main，HEAD `e9ca97e`，工作树无 WIP）
- 基线核对：计划 §4 五个冻结 SHA256 全部一致（basic-capabilities.md / app.at / api.at /
  verify_basic.py / desktop_mcp.py），零漂移。
- 原始探针：`D:/autostack/plan-artifacts/paint-002/t00/`（probe_vm.py、probe_vue.py、
  probe_vm_report.json、probe_vue_report.json、probe_vm.log、probe_vue.log、out/）。
  注：`plan-artifacts/plan-002/` 已被另一仓 DATABASE-002 的 scratch 占用，本计划改用
  `plan-artifacts/paint-002/`，避免跨计划互写。

## 1. 冻结身份（本轮实测）

| 项 | 值 |
|---|---|
| auto CLI | `auto 0.1.0+plan-890-verified-r7-t19-14-g47d8f7b`，`D:/autostack/auto-man/target/debug/auto.exe`，sha256 `6f1925ea0e9fa037…` |
| tool host | `auto-ui-tool 0.1.0`，`D:/autostack/auto-ui/target/debug/auto-ui-tool.exe`，sha256 `dcde805852745168…` |
| python / node / pnpm | 3.14.2 / v25.2.1 / 11.6.0（requests 2.34.2、playwright chromium 可用） |
| 端口 | 17834/17835（pac.at 固定）本轮起点空闲；探针 MCP 端口由 free_port(9600+) 动态取得 |
| vue 绑定 | vite front 绑 localhost（非裸 127.0.0.1），沿用 001 结论 |

## 2. 两个正式 profile 与后端生命周期

| | vm 档 | vue 档 |
|---|---|---|
| 启动 | `auto run -r vm` + 隔离 `AUTO_VM_STORAGE_FILE` + 自有 `AUTOUI_MCP_PORT` | `auto run -r vue --server vm`（front 17834 + VM HTTP 后端 17835） |
| 存储 | 文件 KV（env 重定向 → 本次自有 JSON） | 浏览器 localStorage；**playwright `launch_persistent_context`（自有 user-data-dir）下跨浏览器进程持久**（V2 实测） |
| 导出 | `#[api] export_svg` 进程内直调 | 同一 api 经 vite 代理 → 17835；**杀掉 17835 后导出失败**（V4 实测） |
| 冷启动 | MCP ~3s + UI 就绪 ~5s（暖 target）；重启后 ~2.5s | dev server 起服务 <150s 预算内（实测数十秒）；沿用 001 观察：vite 子进程可能 ~90-100s 自行退出（`pnpm exited 143`），验收驱动须重启容忍 |
| 就绪判定/失败 | 既有 VmSession 有界等待（MCP 90×1s + UI 60×2s，进程退出即失败）保持；非零退出码路径已有 | `VueApp.start()` 150s 有界等待 + alive() 探测保持；失败非零 |

冷缓存（首次编译/首装）允许更久：门只依赖"有界等待 + 超时即非零失败"，与暖/冷无关；本轮不清理共享 target（规约 §2）。

## 3. 实证结果（全部真实 UI 输入链，独立 oracle）

**VM 档（probe_vm.py，全绿）**：
- B 跨进程重开：UI 编辑 10 点稀疏图 → Save(`saved`) → **taskkill 强杀进程树** → 同一
  storage 重启 → 白板初态 → Load → 256 格逐项一致 → 再次编辑(55) → Save → 再强杀重开
  → Load 仍逐项一致。Init 不自动加载（显式 Load 是合同行为，非缺陷）。
- C 中文/空格路径导出：`out/中文 目录/画作 测试.svg` 落盘，XML 可解析、逐坐标逐色
  匹配、**字节级等于 oracle**。
- D 既有目标覆盖：对已存在文件再次导出不同内容 → 文件被**整体覆盖**为新内容
  （mtime 前移、字节等于新 oracle）。覆盖 = 真实语义，写入 SD 候选。
- E 失败与恢复：不存在目录路径 → `export failed` 可见、画布 256 格不变；改回好路径
  → 下一次导出成功。旧输出在失败时未被触碰（失败路径写不进任何文件）。

**vue 档（probe_vue.py）**：
- V1/V2 持久 profile：自有 user-data-dir，编辑+Save → **强杀整个 chromium 进程树** →
  以同一 profile 重启新浏览器进程 → Load → 256 格逐项一致 → 再编辑(55)+Save。浏览器
  进程重启后 localStorage 存活（同源持久 profile 实证）。
- V3 中文/空格路径导出经后端 → 字节级 oracle 一致；XML 可解析。
- V5 恢复：重启 app + 重开浏览器 → Load 一致 → 下一次导出成功。

## 4. 实证缺口（唯一业务缺陷，转 T-02 修复）

**vue 后端断开时导出假成功**：杀掉 17835 后点击 Export——文件未写（fail 路径无文件）、
画布不变，但**状态条仍显示 `exported`**（V4 实测）。根因：生成器把 `Export` 产出为
`await export_svg(...)` 裸调用（`gen/front/vue/src/lib/api.ts` fetch reject → App.vue
`Export()` 中 await 抛出），后续 status 赋值不执行 → 状态条停留在上次成功的
`exported`，对用户声称成功。违反规范 §3"失败可见"；违反 P-03"后端断开失败语义明确"。

- 责任层：app 业务源码可用 AutoLang `try/catch`（关键字实测存在；auto-blog
  `draft_store.at` 有 front 侧先例）包裹导出调用，失败置 `export failed` —— 属
  **app 内最小修复**，不需要越仓改框架。VM 档进程内直调不会走 catch（休眠分支），
  改动后两档行为一致。
- 备选（若 vue 生成器在 handler 位不支持 try/catch）：await 前先置过渡状态
  （如 `exporting…`），失败时不再显示 stale `exported`——仍诚实但不显式失败；仅作
  回退，不作首选。
- 同型排查：Save 已有写后回读保护（无 await 抛出面）；Load 全同步无此缺陷。

## 5. 对 T-01/T-02/T-03 的固定决策

1. **T-01**：门资源全部本次自有（temp storage、动态 MCP 端口、自有 user-data-dir、
   temp 输出 SVG）；清理只杀本次 spawn 的进程树（含窗口期判定，见 probe_vue.py
   `App.stop/kill_back_only`）；不 clear 用户浏览器数据、不动共享 target。
2. **T-02**：verify_basic 增补——vm：强杀重开→Load 一致→再编辑；vue：persistent
   context（替换一次性 new_context）+ 强杀浏览器重开→Load 一致→再编辑；两档
   中文/空格路径导出、既有目标覆盖、后端断开失败可见（修复后断言 `export failed`）
   + 恢复后成功。既有 V-01/02/03 反例矩阵原样保留回放。
3. **T-03**：负控证明 oracle 非空洞（对导出文件做受控变异 → 断言必须红、整体非零），
   复用 001 数据反例不删。
4. Spec 增量（SD-01 modify basic-capabilities / SD-02 add standalone-runtime）候选项
   按 §3/§4 实测边界起草：覆盖=整体覆盖、后端断开=显式失败可见、两 profile 存储
   身份、冷准备就绪判定、vue persistent profile 验收入口。

## 6. 预算与边界

- 探针/验收只用自有临时资源；进程清理凭本次 spawn 归属（PID/窗口期），不凭端口或
  命令行相似性杀进程。
- 不要求 PNG、掉电原子性；`fs.write` 失败静默返回 0 的框架缺口由写后回读判定
  （001 已登记），本轮维持该判定不动摇。
- 本轮未发现必须新增绘图功能的实证缺口；除 §4 的导出失败可见性外，业务源码零改动。
