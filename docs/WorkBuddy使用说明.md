# WorkBuddy 使用说明

本工具包的核心是一个**通用 Markdown skill**（`skills/geo-monitoring/SKILL.md`），不依赖 DSH 特有机制，可被 WorkBuddy 或其他 AI 工作台作为技能文件导入。

## 接入方式（三选一）

### 方式 A：直接引用 SKILL.md（推荐）
把 `skills/geo-monitoring/SKILL.md` 及其 `references/` 目录作为技能文件提供给 WorkBuddy 会话，然后在对话中说明：
> 「使用 geo-monitoring 技能，按五步工作流执行 GEO 监测」

### 方式 B：技能目录挂载
将整个 `geo-monitoring/` 目录放入 WorkBuddy 的技能/工具目录，AI 会自动发现 `SKILL.md` 并按其 frontmatter 描述触发。

### 方式 C：人工触发
在对话中直接描述需求（如「帮我跑一轮 5 引擎 GEO 采样并出报告」），并把 `SKILL.md` 内容作为上下文提供。

## WorkBuddy 会话内调用示例

```
用户：对 [EXPO] 越南工业周做一轮 AI 引擎提及率监测
AI（遵循 SKILL.md）：
1. 检查 scripts/ 目录与 templates/GEO采样_问题集.csv
2. 执行 python scripts/geosample_deepseek.py --limit 6 试跑
3. 执行 python scripts/geo_sample_browser.py --engine doubao --limit 3
4. 全量后 python scripts/geoanalyze.py && python scripts/generate_report.py
```

## 注意事项

- 脚本在**本机**运行（需 Python + Playwright + 专用 Chrome 登录态），WorkBuddy 若为远端需把目录同步到本地后执行
- `DEEPSEEK_API_KEY` 只在本地环境变量配置，不进入对话/文档
- 问题集与位次回填规则见 `SKILL.md` 第 4 节
