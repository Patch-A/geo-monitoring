---
name: geo-monitoring
description: 完整的 GEO（生成式引擎优化）监测工作流：用 DeepSeek API + Playwright 浏览器对豆包/文心一言/Kimi/通义千问/腾讯元宝做 AI 引擎采样（60 问固定问题集），分析提及率/TOP3 推荐率/[BRAND]提及/引用域名/竞争格局，并生成 HTML 多引擎对比报告。当用户要做「AI 平台品牌可见度监测」「GEO 效果度量」「AI 引擎采样基线」「品牌提及率统计」时使用。包含脚本用法、断点续跑、限流/验证码处理、位次人工回填等完整操作指引。
---

<!-- geo-monitoring:v1 -->

# GEO 监测工作流（GEO Monitoring Toolkit）

面向「当用户用泛化词（如"越南机床展参展"）向国内 AI 平台提问时，品牌/展会能否被推荐」这一目标的完整监测方法。配套 Python 脚本 + 固定 60 问问题集，可重复执行、可跨引擎对比、可产出 HTML 报告。

## 1. 适用场景

- 品牌 / 展会 / 子品牌在 AI 引擎（豆包、文心、Kimi、通义、元宝，可选 ChatGPT/Perplexity）的**提及率、推荐位次**基线建立与周度监测
- GEO 内容发布前后效果对比（已发布 vs 未发布关键词）
- 竞争格局研判（AI 回答里常推荐哪些竞品）

## 2. 目录结构

```
geo-monitoring/
├── scripts/
│   ├── geosample_deepseek.py      # DeepSeek API 采样（联网检索）
│   ├── geo_sample_browser.py      # 浏览器采样（Playwright + 已登录 Chrome）
│   ├── geoanalyze.py              # 基线分析（提及率/TOP3/域名/竞品）
│   ├── integrate_data.py          # 5 引擎数据整合（去重取最长）
│   ├── generate_report.py         # HTML 多引擎对比报告
│   └── 启动_调试Chrome_EN.bat      # 启动专用 Chrome（登录态隔离）
├── templates/
│   ├── GEO采样_问题集.csv          # 60 问固定问题集（A-F 六组 × 10 问）
│   └── GEO采样_基线记录_模板.csv    # 人工采样记录模板
├── skills/geo-monitoring/         # 本 skill（SKILL.md + references）
├── plugin/                        # DSH 插件（cordis.patch.yml + lib/index.js）
└── docs/                          # 操作手册与示例
```

## 3. 五步工作流

### 3.1 准备（一次性）
- 启动专用 Chrome：双击 `scripts/启动_调试Chrome_EN.bat`（端口 9222，独立 profile，登录态隔离）；或让浏览器脚本自动启动（它会用同一 profile）
- 在专用 Chrome 里登录目标引擎各一次：豆包 / 文心一言 / Kimi / 通义千问 / 腾讯元宝
- 配置 DeepSeek key：`$env:DEEPSEEK_API_KEY='sk-xxx'`（只进环境变量，勿写文件）

### 3.2 DeepSeek API 采样（自动，周度快照主数据）
```powershell
python scripts/geosample_deepseek.py --limit 6    # 试跑 6 问
python scripts/geosample_deepseek.py              # 全量 60 问
python scripts/geosample_deepseek.py --resume     # 断点续跑
python scripts/geosample_deepseek.py --probe      # 探测 1 问看响应结构
```
> 引擎说明：该脚本走 Responses API + web_search 工具（`enable_search` 已废弃），强制联网检索，回答含 2026 档期与引用来源。

### 3.3 浏览器采样（人工登录态复用，覆盖全部引擎）
```powershell
python scripts/geo_sample_browser.py --engine doubao --limit 3   # 试跑
python scripts/geo_sample_browser.py --engine yiyan              # 全量（文心）
python scripts/geo_sample_browser.py --engine kimi --ids A7,D5   # 只补指定题号
python scripts/geo_sample_browser.py --engine tongyi --group B   # 按组跑
python scripts/geo_sample_browser.py --engine yuanbao --resume   # 断点续跑
python scripts/geo_sample_browser.py --engine kimi --debug       # dump DOM 适配新引擎
```
> 引擎 key：doubao / yiyan / tongyi / yuanbao / kimi。每题自动重试 3 次，失败自动刷新重试并截图到 `浏览器截图/`。

### 3.4 基线分析
```powershell
python scripts/geoanalyze.py                       # 全部引擎
python scripts/geoanalyze.py --only 豆包,DeepSeek  # 指定引擎
```
> 产出 `GEO采样_基线报告_YYYYMMDD.md`（提及率 / TOP3 率 / 按核心词 / 引用域名 Top15 / 竞争实体频次 / 位次待判定清单）。

### 3.5 整合 + HTML 报告
```powershell
python scripts/integrate_data.py    # 5 引擎去重整合 -> GEO采样_5引擎整合_*.csv（300 行）
python scripts/generate_report.py   # -> GEO多引擎对比报告_*.html
```

## 4. 关键规则与坑

### 4.1 问题集固定，跨期可比
`templates/GEO采样_问题集.csv` 为 60 问定稿（A-F 六组 × 10 问，含意图维度）。**采样中途不要增删题目**；新增词另建扩展批次（`--questions` 参数指定）。

### 4.2 位次人工回填（豆包）
浏览器采样不自动判位次。把含 [EXPO] 的回答逐条判断「[EXPO] 在推荐列表第几名」，写入 `GEO采样_位次回填_YYYYMMDD.csv`（列：qid, rank），`geoanalyze.py` 自动合并。rank=1/2/3 计 TOP3。

### 4.3 限流 / 验证码处理
- Kimi 等引擎高峰限流：回答出现「Kimi 有点累了」「高峰时段算力不足」→ 脚本自动重试（`is_quality_answer` 已识别限流话术与思考阶段文本）
- 频繁触发验证码：放慢节奏，按组跑 + 批间休息，或手动过验证
- 回答末尾的「已切换至K2.6」提示行不判无效（正文完整即可）

### 4.4 profile 冲突
手动调试 Chrome 与脚本自动启动的 Chrome **不能同时存在**（同一 user-data-dir 锁）。冲突时：
```powershell
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*.geo-chrome-profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### 4.5 回答有效性判定
`is_quality_answer`：长度 ≥100、非纯追问句（"需要我帮你…吗？"）、非限流话术、非思考阶段文本（"搜索网页…用户询问…"且无展会实体）。有效回答才会被 `--resume` 计入已采。

## 5. 指标口径

| 指标 | 定义 |
|---|---|
| 提及率 | 提及 [EXPO]/[EXPO_NAME]的提问数 / 总提问数 |
| TOP3 推荐率 | [EXPO] 位次 1-3 的提问数 / 提及 [EXPO] 的提问数 |
| [BRAND]提及率 | 提及主办方（含股票代码/英文名）的占比 |
| 引用域名 | 回答引用的来源域名出现频次（DeepSeek API 轮有） |
| 竞争实体 | AI 常推荐的竞品展会（MTA/VIIF/VINAMAC/CMES 等），内部研判用 |

## 6. 参考资料

- `references/sampling.md` — 采样脚本详解（参数、输出、坑）
- `references/analysis.md` — 分析脚本与位次回填
- `references/brand-library.md` — 品牌实体标准表述（以品牌库为准）
- 项目根 `README.md` — 仓库总览与安装
