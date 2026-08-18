# GEO 监测工具包（GEO Monitoring Toolkit）

面向 **GEO（Generative Engine Optimization）** 的完整监测工具：当用户用泛化词向国内 AI 平台（豆包 / 文心一言 / Kimi / 通义千问 / 腾讯元宝）提问时，跟踪品牌 / 展会能否被提及、推荐位次多少，并产出可视化对比报告。

> 应用案例：[BRAND]旗下 [EXPO] [EXPO_NAME]，在「越南机床展参展」「中国参展越南工业展推荐」等 60 个泛化词下的 AI 引擎可见度监测。

## ✨ 能力

| 能力 | 说明 |
|---|---|
| DeepSeek API 采样 | Responses API + web_search 强制联网，60 问全自动，周度快照 |
| 浏览器采样 | Playwright 复用登录态，覆盖豆包/文心/Kimi/通义/元宝 5 引擎 |
| 基线分析 | 提及率 / TOP3 推荐率 / [BRAND]提及 / 引用域名 / 竞争格局 |
| 数据整合 | 5 引擎 × 60 问去重取最长 → 300 行 CSV |
| HTML 报告 | 多引擎对比热力矩阵、位次分布、结论建议 |
| 断点续跑 | `--resume` / `--ids` 精确补跑，不限流/验证码/思考阶段误判 |

## 📁 结构

```
geo-monitoring/
├── scripts/            # 核心 Python 脚本 + 启动 Chrome 批处理
├── templates/          # 60 问问题集 + 人工采样记录模板
├── skills/             # DSH / WorkBuddy 通用 skill（SKILL.md + references）
├── plugin/             # DSH 插件（cordis.patch.yml + lib/index.js）
├── docs/               # 操作手册
└── examples/           # 示例输出
```

## 🚀 快速开始

```powershell
# 1. 依赖
pip install playwright
# （Playwright 无需额外浏览器安装，走系统 Chrome）

# 2. 配置 DeepSeek key（API 通道）
$env:DEEPSEEK_API_KEY = 'sk-xxx'

# 3. 启动专用 Chrome 并登录 5 个引擎（一次性）
.\scripts\启动_调试Chrome_EN.bat

# 4. DeepSeek 试跑
python scripts\geosample_deepseek.py --limit 6

# 5. 浏览器试跑（豆包）
python scripts\geo_sample_browser.py --engine doubao --limit 3

# 6. 全量 + 分析 + 报告
python scripts\geo_sample_browser.py --engine doubao
python scripts\geoanalyze.py
python scripts\integrate_data.py
python scripts\generate_report.py
```

详细操作见 `docs/操作手册.md` 与 `skills/geo-monitoring/SKILL.md`。

## 🔌 作为 DSH 插件安装

插件源码在 `plugin/`（`cordis.patch.yml` + `lib/index.js`）。安装到 DSH profile：

```yaml
# 在某 profile 的 cordis.yml 或 agent preset 中加入：
- id: geo-monitoring
  name: dsh-plugin-geo-monitoring
```

插件注册 `geo-monitor` 工具：模型在任何会话里调用它即获得完整 GEO 监测工作流指引。

## 🧠 作为 skill 使用

`skills/geo-monitoring/SKILL.md` 是 DSH / WorkBuddy 通用的 Markdown skill：
- **DSH**：放入 agent preset 的 skills 挂载目录，或作为独立 skill 目录引用
- **WorkBuddy / 其他 AI 工作台**：将 `SKILL.md` + `references/` 作为技能文件导入，AI 即按五步工作流执行

## 📄 输出物

- `GEO采样_api快照_*.csv` / `GEO采样_浏览器_<引擎>_*.csv` — 原始采样
- `GEO采样_基线报告_*.md` — 基线分析
- `GEO采样_5引擎整合_*.csv` — 300 行整合数据
- `GEO多引擎对比报告_*.html` — 可视化报告

## 📄 许可证

MIT
