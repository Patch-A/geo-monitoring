# 采样详解（Sampling）

## DeepSeek API 通道（geosample_deepseek.py）

走 **Responses API**（`POST https://api.deepseek.com/responses`），`tools: [{"type":"web_search"}]` 强制联网检索。

- 模型：默认 `deepseek-v4-flash`，可 `--model deepseek-v4-pro`
- system 提示注入当前日期，要求优先 2026 年最新信息（否则模型按训练期搜 2025）
- 引用 URL 从 `output[]` 的 `web_search_call.action.type=="open_page"` 提取（清洗 `#ws_call_id=` 后缀）
- 输出：`GEO采样_api快照_YYYYMMDD_HHMM.csv` + `.json`（原始响应）

常见问题：
- `enable_search` 参数已废弃（传了不生效），必须用 web_search 工具
- 回答若为「推理中间句」（"让我核实…"）自动重试 2 次

## 浏览器通道（geo_sample_browser.py）

Playwright `launch_persistent_context` 自动启动 Chrome，复用 `.geo-chrome-profile` 登录态（不需要调试端口）。

- 引擎适配：ENGINES 字典（输入框/回答容器选择器），新引擎先 `--debug` dump DOM 再精调
- 回答容器策略：豆包 `div.v_list_row`（取最后一个）；文心/通义 `div[class*='markdown']`（join_all 拼接+去重）；元宝 `div.agent-chat__bubble--ai`；Kimi `div.segment`（skip_thinking 跳过思考阶段）
- Locator API 抗 SPA 重渲染（避免 "Element is not attached to the DOM"）
- `--ids A1,B2` 精确补跑；`--resume` 跳过已有效回答；每题自动重试 3 次

## 人工采样（模板）

`templates/GEO采样_基线记录_模板.csv`：逐条粘贴回答，填 是否提及[EXPO] / 是否提及[BRAND] / 提及实体 / [EXPO]推荐位次 / 引用域名 / 信息准确度。文件名需以 `GEO采样_基线记录_` 开头才被 geoanalyze 识别。
