# -*- coding: utf-8 -*-
"""
GEO 浏览器采样脚本（Playwright + 已登录专用 Chrome）
=====================================================
用途：复用你登录好的专用 Chrome（调试模式，端口 9222），对 5 个国内 AI 引擎
      （豆包 / 文心 / Kimi / 通义 / 元宝）逐个提问、抓取回答，输出结构化 CSV，
      与 geoanalyze.py 兼容（可直接出基线报告）。不需要任何 API key。

前置步骤（README_监测.md 第三节）：
    1. 双击「启动_调试Chrome.bat」→ 在打开的 Chrome 里登录各引擎
    2. 保持该 Chrome 窗口开着
    3. pip install playwright   （首次）

用法：
    python geo_sample_browser.py --engine doubao --limit 3     # 豆包跑前 3 问
    python geo_sample_browser.py --engine doubao --group A     # 豆包跑 A 组
    python geo_sample_browser.py --engine doubao               # 豆包全量 60 问
    python geo_sample_browser.py --engine all --limit 3        # 全部已配置引擎各 3 问

输出：
    GEO采样_浏览器_<引擎>_YYYYMMDD_HHMM.csv

依赖：pip install playwright（无需 playwright install，走系统 Chrome 调试端口）。
"""

import os, sys, csv, time, argparse, datetime, re, json, glob

BASE = os.path.dirname(os.path.abspath(__file__))
CDP_URL = "http://127.0.0.1:9222"

CSV_HEADER = ["采样时间", "引擎", "问题编号", "问题原文", "回答全文",
              "引用URLs", "引用域名", "是否联网", "原始状态"]

# ---------------------------------------------------------------
# 引擎适配配置：每个引擎 = 打开地址 + 输入框候选选择器 + 回答容器候选选择器
# 说明：选择器是网页 DOM 结构，引擎改版可能失效；适配失败时把页面截图发给
#       「监测/浏览器截图/」目录，我会按新结构更新选择器。
# ---------------------------------------------------------------
ENGINES = {
    "deepseek": {
        "name": "DeepSeek网页版",
        "url": "https://chat.deepseek.com/",
        "input": [
            "textarea",                                    # 实测：DeepSeek 网页输入框是 textarea
            "div[contenteditable='true']",
            "[contenteditable]",
        ],
        "answer": [
            "div.ds-markdown.ds-assistant-message-main-content",  # 实测：AI 回答正文
            "div[class*='markdown']",
            "div.ds-message",
        ],
        "send_key": "Enter",
        "wait_sec": 15,           # DeepSeek 网页思考+联网较慢
        "settle_sec": 4,
        "skip_thinking": True,    # DeepSeek 网页有思考过程文本，识别后继续等正式回答
        "note": "网页版方案：零 API key、零 token，本地浏览器采样；需在专用 Chrome 登录 chat.deepseek.com",
    },
    "doubao": {
        "name": "豆包",
        "url": "https://www.doubao.com/chat/",
        "input": [
            "textarea",                                    # 实测：豆包输入框就是 textarea
            "div[data-testid='chat_input_input']",
            "div[contenteditable='true']",
        ],
        "answer": [
            "div.v_list_row",                              # 实测：AI 回答整行（v_list 组件，稳定命名）
            "div.list_items",                              # 消息列表容器（v_list 组件）
            "div.scroller_content",                        # 滚动容器
        ],
        "send_key": "Enter",          # 回车发送（豆包）
        "wait_sec": 8,                # 首次等待回答出现
        "settle_sec": 3,              # 长度不再增长的判定间隔
    },
    # 以下引擎：优先跑 --debug 拿真实 DOM 后再正式采样
    "yiyan": {
        "name": "文心一言",
        "url": "https://yiyan.baidu.com/",
        "input": ["textarea", "div[contenteditable='true']", "[contenteditable]"],
        "answer": [
            "div[class*='markdown']",                      # 实测：回答正文容器（可能分多个块）
            "div[class*='message']",
            "div[class*='answer']",
        ],
        "send_key": "Enter",
        "wait_sec": 8,
        "settle_sec": 3,
        "join_all": True,          # 文心回答分多块，拼接所有 markdown 块
    },
    "tongyi": {
        "name": "通义千问",
        "url": "https://tongyi.aliyun.com/qianwen/",
        "input": [
            "div[contenteditable='true']",                 # 实测：通义输入框是 contenteditable
            "[contenteditable]",
            "textarea",
        ],
        "answer": [
            "div[class*='markdown']",                      # 实测：回答正文容器
            "div[class*='message']",
            "div[class*='answer']",
        ],
        "send_key": "Enter",
        "wait_sec": 8,
        "settle_sec": 3,
        "join_all": True,          # 回答分多块，拼接
    },
    "yuanbao": {
        "name": "腾讯元宝",
        "url": "https://yuanbao.tencent.com/chat",
        "input": [
            "div[contenteditable='true']",                 # 实测：元宝输入框是 contenteditable
            "[contenteditable]",
            "textarea",
        ],
        "answer": [
            "div.agent-chat__bubble--ai",                  # 实测：AI 回答气泡
            "div.hyc-content-md",                          # 实测：回答 markdown 容器
            "div.agent-chat__list__item--ai",
            "div[class*='markdown']",
        ],
        "send_key": "Enter",
        "wait_sec": 8,
        "settle_sec": 3,
        "join_all": False,        # 取最后一个 AI 气泡即可（单块完整）
    },
    "kimi": {
        "name": "Kimi",
        "url": "https://kimi.moonshot.cn/",
        "input": ["div[contenteditable='true']", "textarea"],
        "answer": [
            "div.chat-content-item.chat-content-item-assistant",  # AI 回答消息块
            "div.segment.segment-assistant",                      # AI 回答段
            "div[class*='markdown']",
        ],
        "send_key": "Enter",
        "wait_sec": 15,           # Kimi 联网搜索慢，首等拉长
        "settle_sec": 4,
        "join_all": False,
        "skip_thinking": True,    # Kimi 有"思考/搜索"中间阶段，识别后继续等正式回答
    },
}


def load_questions(path):
    questions = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qid = (row.get("问题编号") or "").strip()
            qtext = (row.get("问题原文") or "").strip()
            if qid and qtext:
                questions.append({"id": qid, "text": qtext})
    return questions


def pick_selector(page, candidates, what):
    """依次尝试候选选择器，返回第一个命中的（供 debug_dump 使用）"""
    for sel in candidates:
        try:
            el = page.query_selector(sel)
            if el:
                return sel
        except Exception:
            continue
    return None


def pick_locator(page, candidates):
    """依次尝试候选选择器，返回第一个命中的 Locator。
    Locator 每次操作前自动重新解析 DOM，可避免 SPA 重渲染导致的 detached 元素错误。"""
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                return loc
        except Exception:
            continue
    return None


def wait_answer_settle(page, answer_cands, min_len=30, settle_sec=3, max_wait=150, join_all=False, skip_thinking=False):
    """等待回答出现且长度不再增长；每轮动态尝试所有候选选择器。
    join_all=False：取最后一个非空元素（豆包，单块回答）
    join_all=True ：拼接所有匹配块（文心等，回答可能分成多个 markdown 块）
    skip_thinking=True ：识别"思考/搜索阶段"中间文本（Kimi 等），此时继续等待不判完成
    返回 (回答文本, 是否完成)"""
    last_text, stable = "", 0
    start = time.time()
    while time.time() - start < max_wait:
        text = ""
        for sel in answer_cands:
            try:
                if join_all:
                    t = page.evaluate(
                        """(sel) => {
                            const els = document.querySelectorAll(sel);
                            const parts = [];
                            els.forEach(el => {
                                const t = (el && el.innerText) ? el.innerText.trim() : '';
                                if (t && !parts.includes(t)) parts.push(t);
                            });
                            return parts.join('\\n');
                        }""", sel)
                else:
                    t = page.evaluate(
                        """(sel) => {
                            const els = document.querySelectorAll(sel);
                            if (!els.length) return '';
                            const last = els[els.length - 1];
                            return (last && last.innerText) ? last.innerText.trim() : '';
                        }""", sel)
                if t:
                    text = t
                    break
            except Exception:
                continue
        if text != last_text:
            last_text, stable = text, 0
        else:
            stable += 1
            if stable * settle_sec >= settle_sec and len(text) >= min_len:
                if skip_thinking and is_thinking_phase(text):
                    # 仍处于"思考/搜索"中间阶段（Kimi），重置稳定计数继续等
                    stable = 0
                else:
                    return last_text, True
        time.sleep(settle_sec)
    return last_text, False


# Kimi 思考/搜索阶段特征词
THINKING_MARKS = ["搜索网页", "思考已完成", "用户询问", "用户问的是", "让我搜索",
                  "让我用web", "我来搜索", "我需要搜索", "正在思考", "正在搜索"]
# 正式回答内容标志（强实体标志：思考搜索词中几乎不会完整出现这些结构化信息）
SOLID_MARKS = ["MTA Vietnam", "MTA越南", "CMES", "IIW", "VINAMAC", "VILOG", "METALEX",
               "VIIF", "VIMF", "VME", "Vietnam", "西贡会展中心", "越南展览中心",
               "举办时间", "展览面积", "平方米", "㎡", "主办方", "年7月", "年8月",
               "年9月", "年10月", "年11月", "年5月", "年6月"]


def is_thinking_phase(text):
    """判断是否仍处于 Kimi 思考阶段（无正式回答）：
    短文本（<300字）且整段命中多个思考特征词、且无正式内容标志。
    注意：Kimi 回答块是"思考文本+正式回答"混排，只要出现正式内容标志即视为已回答。"""
    if not text or len(text) >= 300:
        return False
    hits = sum(1 for m in THINKING_MARKS if m in text)
    has_solid = any(s in text for s in SOLID_MARKS)
    return hits >= 2 and not has_solid


def debug_dump(page, engine_cfg, q):
    """调试模式：跑 1 问，dump 各候选选择器的真实命中情况（供精调选择器）"""
    page.goto(engine_cfg["url"], wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    print("=== 输入框候选命中 ===")
    for sel in engine_cfg["input"]:
        try:
            n = len(page.query_selector_all(sel))
            print(f"  [{n}] {sel}")
        except Exception as e:
            print(f"  [ERR] {sel}: {e}")
    in_sel = pick_selector(page, engine_cfg["input"], "输入框")
    if not in_sel:
        # 无输入框命中：dump 页面所有可交互输入元素，帮助定位
        print("⚠ 候选输入框全部未命中，dump 页面输入类元素：")
        try:
            info = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('textarea, input, [contenteditable], [role="textbox"]').forEach(el => {
                    out.push({
                        tag: el.tagName,
                        role: el.getAttribute('role') || '',
                        cls: (el.className || '').toString().slice(0, 80),
                        ph: el.getAttribute('placeholder') || '',
                        editable: el.isContentEditable
                    });
                });
                return out;
            }""")
            for it in info[:20]:
                print(f"    {it}")
        except Exception as e:
            print(f"    [ERR] {e}")
        # 再 dump 一下大文本 div，便于找回答容器
        try:
            info2 = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('div').forEach(el => {
                    const cls = (el.className || '').toString();
                    if (cls && cls.length < 120 && el.innerText && el.innerText.length > 50) {
                        out.push({cls: cls.slice(0,80), len: el.innerText.length, first: el.innerText.slice(0,50)});
                    }
                });
                return out.slice(-20);
            }""")
            print("=== 页面大文本 div ===")
            for it in info2:
                print(f"    div.{it['cls']} len={it['len']} 「{it['first']}」")
        except Exception as e:
            print(f"    [ERR] {e}")
        return
    box = page.query_selector(in_sel)
    box.click()
    time.sleep(0.5)
    try:
        box.fill(q["text"])
    except Exception:
        box.type(q["text"], delay=20)
    page.keyboard.press(engine_cfg["send_key"])
    print(f"已发送问题：{q['text']}")
    print("等待回答生成 12 秒…")
    time.sleep(12)
    print("=== 回答容器候选命中（取最后一个元素前 200 字） ===")
    for sel in engine_cfg["answer"]:
        try:
            els = page.query_selector_all(sel)
            if els:
                t = (els[-1].inner_text() or "").strip().replace("\n", " ")
                print(f"  [{len(els)}] {sel}\n      → {t[:200]}")
            else:
                print(f"  [0] {sel}")
        except Exception as e:
            print(f"  [ERR] {sel}: {e}")
    print("=== 页面所有带 class 的 div 数量（用于找更精准的选择器） ===")
    try:
        info = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div').forEach(el => {
                const cls = (el.className || '').toString();
                if (cls && cls.length < 120 && el.innerText && el.innerText.length > 100) {
                    out.push({cls, len: el.innerText.length, first: el.innerText.slice(0, 60)});
                }
            });
            return out.slice(-30);
        }""")
        for it in info:
            print(f"  div.{it['cls']}  len={it['len']}  「{it['first'].replace(chr(10),' ')}」")
    except Exception as e:
        print(f"  [ERR] {e}")


def sample_one(page, engine_cfg, q):
    """对单引擎单问执行：打开新标签 → 提问 → 抓回答"""
    page.goto(engine_cfg["url"], wait_until="domcontentloaded", timeout=45000)
    # 等待输入框出现（SPA 需要时间渲染；等不到就继续往下走，靠 locator 兜底）
    try:
        page.wait_for_selector(engine_cfg["input"][0], timeout=25000)
    except Exception:
        pass
    time.sleep(1)

    # 1) 定位输入框（Locator：每次操作自动重新解析，不怕页面重渲染）
    box = pick_locator(page, engine_cfg["input"])
    if not box:
        return f"[适配失败] 找不到输入框（{engine_cfg['name']}）", False
    try:
        box.click(timeout=5000)
    except Exception:
        pass
    time.sleep(0.5)
    # contenteditable 用 fill 不一定行，先尝试 click+type（超时缩短，失败交给上层重试）
    try:
        box.fill(q["text"], timeout=8000)
    except Exception:
        box.type(q["text"], delay=20, timeout=8000)
    time.sleep(0.8)

    # 2) 发送
    page.keyboard.press(engine_cfg["send_key"])
    time.sleep(1.5)

    # 3) 等待回答：动态尝试所有回答容器候选（不预先固定，防止"搜索中"状态误判）
    time.sleep(engine_cfg["wait_sec"])
    text, ok = wait_answer_settle(page, engine_cfg["answer"],
                                  settle_sec=engine_cfg["settle_sec"],
                                  join_all=engine_cfg.get("join_all", False),
                                  skip_thinking=engine_cfg.get("skip_thinking", False))
    if not text:
        # 兜底：把整个 body 文本当回答（含侧边栏，仅用于人工复核）
        body = page.evaluate("document.body.innerText")
        return body, len(body) > 50
    return text, ok


def main():
    ap = argparse.ArgumentParser(description="GEO 浏览器采样（登录态 Chrome）")
    ap.add_argument("--engine", default="doubao", help="doubao/kimi/all")
    ap.add_argument("--questions", default=os.path.join(BASE, "GEO采样_问题集.csv"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--group", default="")
    ap.add_argument("--ids", default="", help="只跑指定题号，逗号分隔，如 A7,A10,B1")
    ap.add_argument("--resume", action="store_true", help="断点续跑：跳过该引擎已有 CSV 里已采到回答的问题")
    ap.add_argument("--debug", action="store_true", help="调试模式：跑 1 问并 dump 真实 DOM 结构")
    args = ap.parse_args()

    # 1) 启动浏览器：优先复用登录态目录自动启动 Chrome（不需要调试端口、不需要手动开浏览器）
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 未安装 playwright：pip install playwright", file=sys.stderr)
        sys.exit(1)

    profile = os.path.join(BASE, ".geo-chrome-profile")
    os.makedirs(profile, exist_ok=True)
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=profile,
                channel="chrome",              # 用系统 Chrome（复用已登录的登录态）
                headless=False,
                args=["--no-first-run", "--no-default-browser-check",
                      "--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 900},
                timeout=60000,
            )
            engines = list(ENGINES.items()) if args.engine == "all" else [(args.engine, ENGINES[args.engine])]
            for key, cfg in engines:
                if args.debug:
                    run_debug(ctx, cfg, args)
                else:
                    run_engine(pw, ctx, cfg, args)
            ctx.close()
    except Exception as e:
        msg = str(e)
        if "user data directory is already in use" in msg or "ProcessSingleton" in msg or "Target browser" in msg:
            print("❌ 无法启动 Chrome：登录态目录被占用。", file=sys.stderr)
            print("   请先关闭所有 GEO 专用 Chrome 窗口（含任务管理器里的 chrome.exe），再重试。", file=sys.stderr)
            print("   ⚠️ 只关专用 Chrome：它是用独立 profile 启动的，关闭它不影响你日常浏览器。", file=sys.stderr)
        else:
            print(f"❌ 启动失败：{e}", file=sys.stderr)
        sys.exit(1)


def run_debug(ctx, cfg, args):
    """调试模式：跑 1 问，dump 真实 DOM，供精调选择器"""
    questions = load_questions(args.questions)
    if args.group:
        questions = [q for q in questions if q["id"].startswith(args.group.upper())]
    q = questions[:1][0]
    print(f"🔍 调试模式：引擎【{cfg['name']}】问题 {q['id']} {q['text']}")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        debug_dump(page, cfg, q)
    finally:
        page.close()


def run_engine(pw, ctx, cfg, args):
    questions = load_questions(args.questions)
    if args.group:
        questions = [q for q in questions if q["id"].startswith(args.group.upper())]
    if args.ids:
        want = {x.strip().upper() for x in args.ids.split(",") if x.strip()}
        questions = [q for q in questions if q["id"] in want]
    if args.limit:
        questions = questions[: args.limit]

    # 断点续跑：跳过该引擎已有 CSV 里已采到回答的问题
    done_ids = set()
    if args.resume:
        done_ids = load_done_ids(cfg["name"])
        if done_ids:
            print(f"  ♻ 发现 {len(done_ids)} 问已有回答，跳过")
    questions = [q for q in questions if q["id"] not in done_ids]

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = os.path.join(BASE, f"GEO采样_浏览器_{cfg['name']}_{ts}.csv")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    print(f"🌐 引擎【{cfg['name']}】开始采样 {len(questions)} 问")
    rows = []
    try:
        for i, q in enumerate(questions, 1):
            print(f"  [{i}/{len(questions)}] {q['id']} {q['text']}")
            # 每题最多重试 3 次（失败→刷新页面→重试），应对风控/页面异常
            text, status = "", ""
            for attempt in range(1, 4):
                try:
                    text, ok = sample_one(page, cfg, q)
                    if text and is_quality_answer(text):
                        status = "ok" if ok else "可能未完成"
                        print(f"    ✅ 回答 {len(text)} 字（{status}）")
                        break
                    reason = "限流/无实质内容" if text else "无回答"
                    status = f"{reason}"
                    print(f"    ⚠ 第{attempt}次{reason}，刷新重试…")
                    time.sleep(4)
                    try:
                        page.goto(cfg["url"], wait_until="domcontentloaded", timeout=45000)
                    except Exception:
                        pass
                    time.sleep(3)
                except Exception as e:
                    status = f"异常(第{attempt}次): {str(e)[:120]}"
                    print(f"    ⚠ {status}")
                    # 截图留证
                    try:
                        os.makedirs(os.path.join(BASE, "浏览器截图"), exist_ok=True)
                        page.screenshot(path=os.path.join(BASE, "浏览器截图", f"{cfg['name']}_{q['id']}_try{attempt}.png"))
                    except Exception:
                        pass
                    time.sleep(4)
                    try:
                        page.goto(cfg["url"], wait_until="domcontentloaded", timeout=45000)
                    except Exception:
                        pass
                    time.sleep(3)
            rows.append({
                "采样时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "引擎": cfg["name"],
                "问题编号": q["id"],
                "问题原文": q["text"],
                "回答全文": text,
                "引用URLs": "",
                "引用域名": "",
                "是否联网": "",
                "原始状态": status,
            })
            write_csv(out_csv, rows)   # 边跑边落盘
            time.sleep(3)              # 限速，防反爬
    finally:
        page.close()
    print(f"🎉 完成：{out_csv}")


def load_done_ids(engine_name):
    """扫描该引擎已有的浏览器采样 CSV，返回已采到"有效回答"的问题编号集合。
    有效回答判定：≥100 字，且不是"需要我帮你…吗？"式的纯结尾追问句
    （实测文心 A8/B2/D6/D10 曾只抓到 35–45 字的追问句，需重跑）"""
    done = set()
    for f in glob.glob(os.path.join(BASE, f"GEO采样_浏览器_{engine_name}_*.csv")):
        try:
            with open(f, "r", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    qid = (row.get("问题编号") or "").strip()
                    ans = (row.get("回答全文") or "").strip()
                    if qid and ans and is_quality_answer(ans):
                        done.add(qid)
        except Exception:
            continue
    return done


# 限流/未完成特征（Kimi 等引擎高峰限制时返回的占位话术）
# 注意：正式回答末尾可能带"高峰时段算力不足，已切换至K2.6"这类提示行，
# 不能仅凭子串命中判无效；须"限流文案占整段比例极高"才视为限流回答。
RATE_LIMIT_PATTERNS = [
    "Kimi 有点累了", "聊的人太多了", "换个话题再聊聊",
    "请耐心等待", "让我换个话题", "暂时无法回答",
    "已用完", "请稍后再试", "请稍后重试", "太忙了",
    "算力不足", "高峰期", "升级会员",
]


def is_quality_answer(ans):
    """有效回答判定：长度 ≥100、不是纯追问句、不是限流占位话术、不是只有思考过程"""
    if len(ans) < 100:
        return False
    stripped = ans.strip()
    # 排除"需要我帮你/需要我为你…吗？"式结尾追问（只有结尾没有正文）
    if stripped.startswith("需要我") and stripped.rstrip().endswith("吗？"):
        return False
    # 排除限流占位话术：整段主要是限流文案（命中限流特征 且 限流文案占比高）
    rate_hits = sum(1 for p in RATE_LIMIT_PATTERNS if p in stripped)
    if rate_hits >= 1:
        # 限流文案占比：从第一个限流特征位置到文末的长度 / 总长
        first_idx = min((stripped.find(p) for p in RATE_LIMIT_PATTERNS if p in stripped), default=-1)
        if first_idx >= 0:
            tail_ratio = (len(stripped) - first_idx) / len(stripped)
            # 占比 >60% 视为"整段基本是限流文案"（正文 + 末尾提示行的场景占比低，放行）
            if tail_ratio > 0.6:
                return False
    # 排除"只有思考过程、没有正式回答"：短文本且含思考特征、且无实质回答标志
    if len(ans) < 500:
        hits = sum(1 for m in THINKING_MARKS if m in stripped)
        has_solid = any(s in stripped for s in SOLID_MARKS)
        if hits >= 1 and not has_solid:
            return False
    return True


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
