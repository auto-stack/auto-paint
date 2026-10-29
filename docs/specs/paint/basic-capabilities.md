# paint 基本能力规范（PAINT-001）

> 状态：随 PAINT-001 r2 提出，经最终复审后为本 app 的 canonical 模块规范。
> 历史 `SPEC.md`（根目录）是 v1 导入时的观察/再生描述，保留作来源，不再
> 作为当前能力的权威；本文与其冲突时以本文为准。

## 1. 用户任务（首版合同）

- 画一张 16×16 像素图：铅笔/橡皮/油漆桶（连通泛洪）/吸管，8×2 色板 +
  当前色，20 步撤销/重做，清空/新建。
- **可靠保存/重开**：工程存取（尺寸/色值/版本），重开逐格一致；旧 v1
  数据可读迁移。
- **导出作品**：用户指定路径导出独立 SVG，可在其他程序打开。

非目标：自由笔触/大画布、图层、专业笔刷、压感、云同步、Linux 适配。
首版图像输出格式固定为 SVG；PNG 不在承诺内。

## 2. 数据模型

- **画布**：固定 16×16 = 256 格；像素真值 = 受验证 hex 色值（`#rrggbb`），
  闭合词汇表 = 16 色板 + 白色（`#ffffff`，橡皮色）。Tailwind 类串只是展示
  派生（`chip_of` 词汇表映射），不是真值。
- **工程存储**（storage `paint.project.v2`）：`"PAINT-V2|16|16|<hex×256>"`，
  共 259 段。写入后回读比对一致才置 saved（写入结果不用无条件 saved 标记）。
- **旧格式**（storage `paint.canvas.v1`）：256 段 ` bg-[#rrggbb] ` 类串以
  `|` 连接。只读迁移：解析为 hex，非 256 项/非词汇表色整体拒绝。
- **拒绝语义**：Load/Undo/Redo 快照应用逐项校验，任一项非法或长度非 256
  → 整体拒绝，状态条可见（"bad save data"），当前画布不改动。
- **撤销**：hex 快照串栈，上限 20；栈空时撤销/重做显示
  "nothing to undo/redo"。

## 3. 导出（SVG）

- 用户在输入框指定绝对路径，点击 Export。
- 输出：独立 SVG 文本——16×16 viewBox、白色底 rect、每非白格一个
  `shape-rendering="crispEdges"` rect（x=列,y=行,w=h=1,fill=hex）。
  色值全部来自闭合词汇表，无用户自由文本，无转义面。
- **写后回读**：后端写文件并回读磁盘实际内容，前端与期望全串比对——
  一致置 "exported"；路径为空/写入失败回读不一致 → 状态条可见失败
  （"export: path required"/"export failed"），当前画布与已保存工程
  不受影响。（框架缺口：`fs.write` 失败静默返回 0，故回读比对是本合同
  的成败判定，登记于 auto-paint capability-decision。）

## 4. 双端行为

| 能力 | VM（`auto run -r vm`） | vue（`auto run -r vue --server vm`） |
|---|---|---|
| 工程保存/加载 | storage（文件支撑 KV） | 浏览器 localStorage（同源持久） |
| SVG 导出 | `#[api] export_svg` 进程内直调 | 同一 api 经 VM HTTP 服务（back_port 17835） |
| 像素编辑/撤销/重做 | 同一 `app.at`，行为一致 | 同左 |

- vue 档导出依赖后端服务：**必须以 `auto run -r vue --server vm` 启动**
  （无后端时保存/加载仍可用，导出失败可见）。默认 `auto run` 走 rust
  后端生成，本 app 无 rust 后端，不可用。
- vue 端生成的输入控件以 `v-model` + `@input` 双绑定；文件级函数的形参
  不得与 model 字段同名（vue 生成器会将函数体内与字段同名的标识符改写
  为 ref 访问，见 `app.at` `build_svg` 注记；框架缺口登记 auto-ui/auto-lang）。

## 5. 验收入口

```sh
python tests/basic/verify_basic.py --profile vm    # 27 项
python tests/basic/verify_basic.py --profile vue   # 22 项（需 17834/17835 空闲）
python tests/desktop_mcp.py                        # VM 轨回归 31 项
```

V-01 像素向量逐项一致（全白/全黑/单点/稀疏设计图，save→重开→load）；
V-02 SVG 导出（XML 解析、逐坐标逐色、oracle 逐字节、真实渲染）；V-03
坏数据拒绝与 v1 迁移、不可写路径失败可见。全同盘（全白/全黑）恢复为
固定回归反例（历史债 P553-D1，工具链 v0.0.20-117-g873fa23 起不复现，
不得以 SKIP 作为通过）。
