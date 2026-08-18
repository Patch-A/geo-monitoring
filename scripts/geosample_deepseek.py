# -*- coding: utf-8 -*-
"""
GEO 采样脚本 v2（DeepSeek Responses API + web_search 联网检索）
================================================================
用途：对「IIW 越南工业周 GEO 监测」的 60 问问题集，逐问调用 DeepSeek **Responses API**
      （tools 内置 web_search，服务器端执行联网检索），记录回答全文与引用链接。

为什么是 v2：
    v1 用的 Chat Completions + enable_search 参数 —— 官方已废弃该参数（no longer
    supported, will not take effect），实测回答为纯模型知识（"截至2025年5月"）。
    官方现支持联网检索的路径是 Responses API 的 web_search 工具。

用法：
    python geosample_deepseek.py                       # 全量 60 问（默认强制联网）
    python geosample_deepseek.py --limit 6            # 只跑前 6 问（试跑）
    python geosample_deepseek.py --group A            # 只跑 A 组
    python geosample_deepseek.py --resume             # 断点续跑
    python geosample_deepseek.py --model deepseek-v4-pro   # 换模型（默认 flash）
    python geosample_deepseek.py --probe              # 探测模式：只跑 1 问并打印完整原始响应结构

环境变量（必填）：
    DEEPSEEK_API_KEY    DeepSeek 开放平台 API key（不要把 key 写进任何文件）

输出：
    GEO采样_api快照_YYYYMMDD_HHMM.csv   结构化结果（每问一行）
    GEO采样_api快照_YYYYMMDD_HHMM.json   原始 API 响应（含 citations 明细，可复核）

依赖：仅 Python 标准库（urllib）。
"""

import os, sys, json, csv, time, argparse, datetime, re, urllib.request, urllib.parse

API_URL = "https://api.deepseek.com/responses"   # Responses API 端点
DEFAULT_MODEL = "deepseek-v4-flash"

CSV_HEADER = ["采样时间", "引擎", "问题编号", "问题原文", "回答全文", "引用URLs", "引用域名", "是否联网", "原始状态"]


def load_questions(path):
    questions = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qid = (row.get("问题编号") or "").strip()
            qtext = (row.get("问题原文") or "").strip()
            if qid and qtext:
                questions.append({"id": qid, "text": qtext})
    return questions


def call_responses(question, api_key, model, retries=4):
    """调用 Responses API，tools=[web_search]，强制联网检索。
    注入 system 提示：明确当前日期为 2026 年，要求优先检索 2026 年最新信息
    （实测发现模型默认按训练期 2025 年搜索，导致回答全是 2025 年资料）。"""
    today = datetime.date.today().isoformat()
    sys_prompt = (
        f"今天是 {today}。这是一个关于越南工业/机床/自动化等展会的检索问题。"
        "请务必通过联网搜索获取并优先引用 **2026 年** 的最新信息"
        "（2026 年的展会时间、地点、规模、档期、主办方），"
        "不要停留在 2025 年或更早的资料上；若 2026 年信息存在，请以 2026 年为准。"
        "回答时请列出你参考的信息来源。"
    )
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
        ],
        "tools": [{"type": "web_search"}],
        "tool_choice": {"type": "web_search"},   # 强制每次提问都联网搜索
        "max_output_tokens": 2500,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            wait = 5 * (2 ** attempt)
            print(f"    ⚠ 调用失败（{e}），{wait}s 后重试 {attempt+1}/{retries}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"DeepSeek Responses API 调用最终失败: {last_err}")


def extract_text(data):
    """Responses API：输出文本在 output[].content[].text 或顶层 output_text"""
    texts = []
    try:
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text" and part.get("text"):
                        texts.append(part["text"])
    except Exception:
        pass
    if not texts and data.get("output_text"):
        texts.append(data["output_text"])
    return "\n".join(texts)


def extract_urls(data, text):
    """防御性提取引用链接（DeepSeek Responses API 实测结构）：
    位置 1：output[] 里 web_search_call.action.type=='open_page' 的 action.url（模型实际浏览的引用页）
    位置 2：顶层 citations（OpenAI Responses 常见字段）
    位置 3：output 内 message content 的 annotations
    位置 4：从回答文本正则回退
    统一清洗 URL 尾部的 #ws_call_id=... 等参数。"""
    urls = []
    # 位置 1：open_page 的 url —— 这是 DeepSeek 联网检索返回的真实引用来源
    try:
        for item in data.get("output", []):
            if item.get("type") == "web_search_call":
                act = item.get("action") or {}
                if act.get("type") == "open_page" and act.get("url"):
                    urls.append(act["url"])
    except Exception:
        pass
    # 位置 2：顶层 citations
    if not urls:
        try:
            for c in (data.get("citations") or []):
                if isinstance(c, dict) and c.get("url"):
                    urls.append(c["url"])
        except Exception:
            pass
    # 位置 3：output 内 message content 的 annotations
    if not urls:
        try:
            for item in data.get("output", []):
                for part in (item.get("content") or []):
                    for ann in (part.get("annotations") or []):
                        if ann.get("url"):
                            urls.append(ann["url"])
        except Exception:
            pass
    # 位置 4：从回答文本正则
    if not urls:
        urls = re.findall(r"https?://[^\s\)\]\}，。；、\"']+", text)
    # 清洗：去掉 #ws_call_id= 及 #1 等锚点后缀，去重保序
    cleaned = []
    for u in urls:
        u = re.sub(r"#(ws_call_id=[A-Za-z0-9_-]+|\d+)$", "", u).strip()
        if u and u not in cleaned:
            cleaned.append(u)
    return cleaned


def had_search(data):
    """是否真的执行了联网搜索：output 里出现 web_search_call"""
    try:
        for item in data.get("output", []):
            if item.get("type") == "web_search_call":
                return True
    except Exception:
        pass
    return False


def domain_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


# 推理中间句特征（A1 曾出现：message 里全是"让我核实/让我打开…"，没有最终答案）
REASONING_HEADS = ["让我", "我已", "我需要", "已找到", "接下来", "正在", "再核实",
                   "让我继续", "我来为您核实", "我找到了", "我已完成"]


def is_reasoning_noise(text):
    """判断回答是否为纯推理中间句（无实质内容）"""
    lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
    if not lines:
        return True
    if len(text) < 300:
        non_noise = [ln for ln in lines if not any(ln.startswith(h) for h in REASONING_HEADS)]
        return len(non_noise) == 0
    return False


def main():
    ap = argparse.ArgumentParser(description="DeepSeek Responses API GEO 采样")
    ap.add_argument("--questions", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "GEO采样_问题集.csv"))
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--group", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--probe", action="store_true", help="探测模式：只跑 1 问并打印完整原始响应")
    args = ap.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("❌ 未设置环境变量 DEEPSEEK_API_KEY", file=sys.stderr)
        print("   PowerShell 示例: $env:DEEPSEEK_API_KEY='sk-xxxx'", file=sys.stderr)
        sys.exit(1)

    questions = load_questions(args.questions)
    if args.group:
        questions = [q for q in questions if q["id"].startswith(args.group.upper())]
    if args.probe:
        questions = questions[:1]

    if args.probe:
        print(f"🔍 探测模式：跑 1 问（{questions[0]['id']}）并打印完整响应")
        data = call_responses(questions[0]["text"], api_key, args.model)
        print("=== 完整原始响应 ===")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        text = extract_text(data)
        urls = extract_urls(data, text)
        print(f"\n=== 解析结果 ===\n文本 {len(text)} 字\n联网: {had_search(data)}\nURLs: {urls}")
        return

    if args.limit:
        questions = questions[: args.limit]
    print(f"📋 待采样 {len(questions)} 问（模型 {args.model}，强制联网搜索）")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = os.path.join(args.out, f"GEO采样_api快照_{ts}.csv")
    json_path = os.path.join(args.out, f"GEO采样_api快照_{ts}.json")

    done_ids = set()
    if args.resume:
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                done_ids = {r["问题编号"] for r in csv.DictReader(f)}

    rows, raw_all = [], []
    for i, q in enumerate(questions, 1):
        if q["id"] in done_ids:
            print(f"  [{i}/{len(questions)}] {q['id']} 已存在，跳过")
            continue
        print(f"  [{i}/{len(questions)}] {q['id']} {q['text']}")
        data = call_responses(q["text"], api_key, args.model)
        content = extract_text(data)
        retries_ans = 0
        while is_reasoning_noise(content) and retries_ans < 2:
            retries_ans += 1
            print(f"    ⚠ 回答疑似推理中间句（无最终答案），自动重试 {retries_ans}/2")
            time.sleep(3)
            data = call_responses(q["text"], api_key, args.model)
            content = extract_text(data)
        urls = extract_urls(data, content)
        domains = list(dict.fromkeys(domain_of(u) for u in urls))
        searched = had_search(data)
        rows.append({
            "采样时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "引擎": "DeepSeek",
            "问题编号": q["id"],
            "问题原文": q["text"],
            "回答全文": content,
            "引用URLs": "; ".join(urls),
            "引用域名": "; ".join(domains),
            "是否联网": "是" if searched else "否",
            "原始状态": str(data.get("status", "")) + (f"；回答重试{retries_ans}次" if retries_ans else ""),
        })
        raw_all.append({"id": q["id"], "question": q["text"], "response": data})
        write_csv(csv_path, rows)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(raw_all, f, ensure_ascii=False, indent=1)
        print(f"    ✅ 回答 {len(content)} 字，引用 {len(urls)} 条，联网={'是' if searched else '否'}")
        time.sleep(args.delay)

    print(f"\n🎉 完成。CSV: {csv_path}")
    print(f"   JSON: {json_path}")


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
