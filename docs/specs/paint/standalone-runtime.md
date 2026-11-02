# paint 独立运行规范（PAINT-002 SD-02）

> 状态：随 PAINT-002 提出，记录本 app 脱离 OS 装配独立运行的真实边界：
> 两个正式 profile、存储身份、冷准备与永久验收入口。与
> [basic-capabilities](basic-capabilities.md) 互补；冲突时以实测为准并回改本文。

## 1. 独立运行合同

应用单独运行不等 OS 装配或其他 app。两个正式启动 profile：

| profile | 启动 | 载体 |
|---|---|---|
| vm | `auto run -r vm` | iced/VM 桌面（`AUTOUI_MCP_PORT` 暴露 autoui 工具面） |
| vue | `auto run -r vue --server vm` | vite front 17834 + VM HTTP 后端 17835 |

默认 `auto run`（rust 后端生成）不可用——本 app 无 rust 后端；vue 档必须
带 `--server vm`，否则导出无后端承载（保存/加载仍可用）。

## 2. 存储身份（两 profile 不互享）

| | vm | vue |
|---|---|---|
| 工程/画布存储 | 文件支撑 KV，`AUTO_VM_STORAGE_FILE` 可重定向（测试隔离用） | 浏览器 localStorage（同源） |
| 持久性 | 文件随路径持久 | 同源持久；验收用运行自有 user-data-dir 持久浏览器 profile（Playwright `launch_persistent_context`） |
| 跨进程重开 | 同一存储文件重启 → 显式 Load 恢复 256 格逐项一致 | 强杀浏览器树后以同一 profile 重启 → Load 逐项一致 |

- Init **不自动加载**：新会话白板初态是合同行为，恢复经显式 Load。
- 未保存的内存编辑不跨进程存活（两档一致）；`Load` 恢复的是最后一次
  Save 的快照。
- 两 profile 存储不自动共享、不迁移：vm 文件 KV 与 vue localStorage 是
  两个已声明 profile，跨 profile 不共享**不是数据丢失**，不声称全端同步。

## 3. 冷准备与失败门

- 就绪判定有界：vm 档 MCP 探测 + 首帧快照（约 90s+120s 上限）；vue 档
  front+back 探测（150s 上限）。暖 target 实测秒级（vm ~3-5s）；冷缓存
  （首次编译/首装）允许更久，门只依赖"有界等待 + 超时即失败"。
- 失败非零：坏 tool 路径 → 显式 FAIL 检查 + 整体退出码 1，不假成功、
  不挂起；无必需 skip/零场景。
- 资源纪律：数据/端口/构建输出/浏览器 profile 全部本次新建自有；进程
  清理只及本次 spawn 的进程树（按启动前端口 pid 窗口与自有命令行特征
  判定），不凭端口或命令行相似性杀进程，不清用户浏览器数据、不动共享
  target。vue dev server 可能 ~90-100s 自行退出（`pnpm exited 143`，框架
  观察），验收驱动须重启容忍。

## 4. 导出后端生命周期（vue 档）

- 导出经 vite 代理 → 17835 VM HTTP 服务（`#[api] export_svg`）。
- 后端断开（17835 不可达）：fetch reject → try/catch → 状态条显式
  "export failed"，不产生文件，当前画布与已保存工程不变；不得显示
  stale "exported"（PAINT-002 修复的假成功缺陷）。
- 后端恢复（重启 `auto run -r vue --server vm`）：重开页面 → Load →
  下一次导出成功，内容与当前画布逐格一致。

## 5. 验收入口（永久回归）

```sh
python tests/basic/verify_basic.py --profile vm    # 48 项
python tests/basic/verify_basic.py --profile vue   # 45 项
AUTO_BIN=<auto CLI> python tests/desktop_mcp.py    # 31 项
```

P 组（002）：P-01 门自足 / P-02 强杀重开逐格一致 + 再编辑 / P-03 导出
路径与后端断开失败可见 + 恢复 / P-04 变异反例 oracle 非空洞、负控非零。
导入/导出用例用 10 点稀疏设计图（2026-10-29 用户裁定）。

## 6. 非目标

PNG、掉电原子性保证、跨端/跨 profile 自动共享存储、云同步、OS 集成、
Linux（WAIT_DISTRO_M1）、多尺寸/图层/笔刷/压感。
