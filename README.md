# 知几 zhiji —— Eval-Native Personal Agent（M0）

纯 Python 标准库，零依赖。评测器与每个技能同生；verdict 即自进化的奖励信号。

## 快速开始
```powershell
cd D:\codex\zhiji
python -m zhiji.cli init        # 建库 + 契约校验 + 回归门 + 晋升
python -m zhiji.cli seed        # 5 个演示任务（✓/✗/待确认）
python -m zhiji.cli serve       # http://127.0.0.1:8765
python -m pytest tests/ -q      # 27 项测试
```

## 前端（Vue 3，Today 风格）
主界面是"今日时间线"而非后台看板：问候语 + 待确认收件箱 + 带核验回执的任务卡 + 👍/👎 反馈。
- `web/` —— Vue 3 + Vite 单文件组件工程（`src/views` 四页：今日/任务/记忆/技能）
- `web/dist/` —— 构建产物，由标准库服务器直接托管，**运行时不需要 Node**
- 改前端后：`cd web && npm install && npm run build`，刷新页面即可
- 前端开发模式：`npm run dev`（Vite 5173，`/api` 代理到 8765）
- `web/legacy.html` —— 旧版后台风页面，dist 缺失时自动回退
- `web/verify.mjs` —— CDP 验收脚本（Edge headless：布局测量 + 提交→确认→批准 E2E + 截图）
  运行前先起调试浏览器：`msedge --headless=new --remote-debugging-port=9222 --user-data-dir=web/.edge-cdp about:blank`

## 模块
- `zhiji/contracts.py` 三件套契约校验（无评测器不上线）
- `zhiji/evaluators.py` AST 白名单断言引擎 + verdict 合成（断言→judge→用户信号）
- `zhiji/engine.py` 任务状态机 + 确认闸门 + 核验回执 + 指标
- `zhiji/router.py` 三级路由 connector→replay→vision(桩)
- `zhiji/replay.py` S2 晋升门：golden cases 沙箱回归
- `zhiji/memory.py` S1 每晚巩固（写日记）
- `zhiji/connectors/` 日报/盯价/对账（demo 数据源可切真实 RSS/HTTP）
- `zhiji/api.py` HTTP API + 静态托管（M1 换 FastAPI 时契约不变）

## 铁律
1. 每个技能 = 执行器 + 评测器 + 数据契约，缺一不上线。
2. 敏感动作（花钱/发消息/删除）永远人工确认；自进化不能扩权。
3. 连续 2 次失败自动降级；晋升必须过回归门。
4. 记忆/轨迹端侧存储（SQLite 单文件），导出训练需显式授权。

详见《Personal-Agent技术实现方案-知几.md》《Personal-Agent产品设计方案-知几.md》。

## 日常使用（不需要写 JSON）
- **一键启动**：双击 `start-zhiji.bat`（起服务器并自动打开浏览器）。
- 点右上角「＋」→ 直接用自然语言说意图（如"帮我盯耳机降到 1500 元"），会自动选中对应技能并展开友好表单；JSON 参数只保留在折叠的"开发者模式"里。
- **真实晨报**：日报表单里勾选信息源（少数派/阮一峰/Hacker News/36氪）即真实联网抓取 RSS；全不勾则用演示数据。
- **真实对账**：先用 `python tools/convert_bill.py 微信或支付宝导出账单.csv -o actual.csv` 转换官方导出账单（自动识别格式/GBK 编码，过滤退款与关闭交易），再准备应有账目 `expected.json`（`{"entries":[{"id","amount"}]}`），在对账表单选"我自己的账单文件"填两个路径即可。`tools/examples/expected.json` + `tools/examples/actual.csv` 是可参考的样例。

