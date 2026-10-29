# PAINT-001 T-01 能力决策记录（capability-decision）

- 日期：2026-10-29
- 执行检出：`D:/autostack/auto-paint`（独立开发 clone，main）
- 基线核对：HEAD = origin/main = `56025f2fce0453a6759a620a0c919159beb8b6fc`，工作树无 WIP；
  计划 §4 四个冻结 SHA256 全部一致（app.at / SPEC.md / pac.at / desktop_mcp.py）。

## 工具链身份

| 组件 | 版本/来源 |
|---|---|
| auto CLI | `auto 0.1.0+v0.0.20-117-g873fa23`，二进制 `D:/autostack/auto-man/target/debug/auto.exe`（auto-man `crates/auto`，构建于 auto-man `873fa23`，HEAD `e6cc06f`） |
| 运行时实现参考 | auto-lang 工作区 HEAD `0f80b3e21`（只读参考，未改动、未跑其 cargo t/docs_gen） |
| node / pnpm | v25.2.1 / pnpm 11.6.0（vite 5.4.21 由脚手架锁定） |
| python | 3.14.2（requests 可用） |

## 端口与权限

- `front_port: 17834`（pac.at 既有）= vite dev server；**绑定 localhost/::1，不响应 127.0.0.1 裸连**（验收脚本必须用 `http://localhost:17834`）。
- `17835`：空闲且可用。已验证作为 `back_port`（pac.at 或 `-B 17835`）承载 VM HTTP 服务（axum/hyper，`0.0.0.0` 监听）。写文件权限正常（用户目录下真实落盘）。

## 双端能力矩阵（实测）

| 能力 | VM UI（`auto run -r vm`，iced） | vue（`auto run`/`-r vue`） |
|---|---|---|
| `storage.get/set` | 文件支撑 JSON KV（按 cwd 哈希落盘 temp；`AUTO_VM_STORAGE_FILE` 可重定向→测试隔离用） | 浏览器 localStorage（同源持久） |
| 直接 `fs.write/read_text/exists` | **真实磁盘 IO**（绝对路径可用） | **不可用**：编译为 `__vmOnly` 抛错桩（auto-lang `vue_capabilities.rs` Plan 444 ④b，实测生成码确认） |
| `use back.api: f()`（`#[api]` 声明） | **进程内直调**（VM 合并模式，无需 HTTP） | 生成为 `@/lib/api` fetch 客户端 → vite 代理 → VM HTTP 服务；需 `--server vm` 启动后端 |

## 关键实测证据（探针工程 `tmp/probe-app/`，gitignored 本地工件）

1. **VM 轨既有全量**：`AUTO_BIN=<auto-man> python tests/desktop_mcp.py` →
   **31 passed / 0 failed / 0 skipped**（旧基线 30 PASS + 1 SKIP）。
   **P553-D1（全同串列表 Redo/Load 塌缩）在当前工具链上未复现**：T6 redo→256 红 PASS、
   T8 load→256 红 PASS（uniform 快照恢复 px 长度 256，实测）。AC-02 的"原 P553-D1 不得
   SKIP 作为通过"在 V-01 中以全白/全黑/单点/棋盘矩阵继续覆盖。
2. **VM 进程内 api→fs.write**：探针 app `auto run -r vm`（无 server）经 autoui MCP 点击
   Export → `probe_export(path, content)` 进程内执行，`tmp/probe-app/probe-out.txt`
   真实写出且内容逐字节等于回读值（09:22 文件时间戳）。
3. **vue split api→fs.write**：`auto run -r vue --server vm`（front 17834 / back 17835）→
   `POST /api/probe/export` 返回回读串 `"api-write-ok"`，磁盘文件内容一致。
   生成的 `gen/front/vue/src/App.vue` 含 `import { probe_export } from '@/lib/api'`，
   `dist/src/lib/api.ts` 为 fetch 客户端（链路完整）。
4. **失败语义（框架缺口→应用层闭环）**：`shim_file_write_text` 对失败**静默返回 0**
   （`let _ = fs::write(...)`）；向目录路径写实测返回 0 且无异常。⇒ 导出成败不能依赖
   fs.write 返回值，必须**写后回读比对**（等价应用方案，AC-03/AC-04 采用）。
5. **旧 v1 storage 实际内容**：`%TEMP%/auto-vm-storage/56a8320c3255ee8d.json` 的
   `paint.canvas.v1` = 256 段 ` bg-[#rrggbb] ` 类串以 `|` 连接（全红盘 3839 字节实测）。
   **旧格式真值是 Tailwind 类串，不是十六进制色值**；T-02 迁移按
   `^\s*bg-\[#([0-9a-fA-F]{6})\]\s*$` 解析，非法段拒绝。
6. **str/join/序列化**：列表 `join("|")`、`split("|")`、storage 往返（daemon 直评
   `storage.set/get`、`parts.join`）实测正常。

## 决策（后续实现依赖）

- **导出格式**：SVG 文本（计划已定）；编码路径 = `use back.api: export_svg(path, content)`
  单一代码路径。VM UI 档进程内直调；vue 档必须以 `auto run -r vue --server vm`
  profile 启动（README/执行入口记录，不静默换 mock）。导出后回读比对，不一致→失败状态。
- **工程保存**：新键 `paint.project.v2`（版本头+色值数组），旧键 `paint.canvas.v1`
  只读迁移；坏数据拒绝且不覆盖当前画布。
- **资源边界**：画布固定 16×16=256 格；undo/redo 栈上限沿用 20；SVG 输出约数 KB 量级；
  storage 值 <8KB。未设隐藏上限。
- **缺项与 owner**：
  - vue 无后端时导出不可用（`__vmOnly`）——本计划以"vue 档强制 `--server vm`"闭环；
    浏览器直接下载（blob/data URL）类框架能力缺口留给 auto-lang owner（未立项，
    不阻塞本计划，因 split profile 已满足 AC-03/04 的用户任务）。
  - `fs.write` 错误吞没——框架缺口，应用层回读比对闭环（同上，不阻塞）。
  - P553-D1 在当前工具链未复现——按已修复处理，V-01 用反例矩阵证明，不再按债 SKIP。

## 隔离声明

所有探针在 `tmp/probe-app`（gitignored）与 `%TEMP%` 隔离存储中进行，未接触真实用户数据；
MCP 端口用 `pick_free_port`/固定 9353 探针端口，应用前端 17834/后端 17835 先核空闲再占。
