# -*- coding: utf-8 -*-
"""
GEO 基线分析脚本
================
用途：汇总「人工基线记录 CSV」与「DeepSeek API 快照 CSV」，计算 IIW 越南工业周的
      提及率 / TOP3 推荐率 / 答案份额 / 引用域名 / 准确率，输出基线报告 Markdown。

用法：
    python geoanalyze.py                       # 分析 监测/ 目录下全部采样 CSV
    python geoanalyze.py --only 豆包,DeepSeek  # 只看指定引擎
    python geoanalyze.py --out 报告.md         # 自定义输出文件

输入（放同一目录，自动匹配）：
    GEO采样_基线记录_*.csv   人工采样记录（模板见 GEO采样_基线记录_模板.csv）
    GEO采样_api快照_*.csv    DeepSeek API 快照（geosample_deepseek.py 输出）

输出：
    GEO采样_基线报告_YYYYMMDD.md   基线报告
    GEO采样_合并明细_YYYYMMDD.csv   标准化后的全部记录（可回填/复核）

依赖：仅 Python 标准库。
"""

import os, sys, csv, glob, re, argparse, datetime, collections

# Windows 控制台默认 GBK，重配置 stdout 为 UTF-8，避免 emoji/中文打印报错
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))

# IIW / 米奥兰特 实体变体（识别用，全部小写比较）
IIW_VARIANTS = ["iiw", "国际工业周", "international industry week", "工业周", "iww"]
MIAO_VARIANTS = ["米奥兰特", "米奥", "meorient", "300795", "米奥兰"]
# 竞争/其他展会实体（仅中性统计，供内部研判）
COMPETITORS = ["mta vietnam", "mta", "viif", "vietnam manufacturing expo", "vme",
               "metalex", "越南国际工业博览会", "胡志明机床展"]

GROUP_MAP = {
    "A": "越南机床展参展", "B": "中国参展越南工业展推荐", "C": "越南工业自动化展会",
    "D": "越南建厂设备采购展会", "E": "越南物流设备展会", "F": "越南泵阀管件展会",
}


def norm(s):
    return (s or "").strip().lower()


def mention(text, variants):
    t = norm(text)
    return any(v in t for v in variants)


def parse_rank(raw):
    """人工位次字段 -> 整数（1-5）或 None"""
    if raw is None:
        return None
    s = norm(raw)
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return None


def load_manual(path):
    """人工记录：直接读取标记字段 + 从回答文本二次识别做交叉验证"""
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            text = (r.get("回答全文或摘录") or "")
            manual_iiw = norm(r.get("是否提及IIW") or "") in ("是", "true", "1", "yes")
            rows.append({
                "date": (r.get("采样日期") or "").strip(),
                "engine": (r.get("引擎") or "未知").strip(),
                "qid": (r.get("问题编号") or "").strip().upper(),
                "question": (r.get("问题原文") or "").strip(),
                "answer": text,
                "iiw": manual_iiw or mention(text, IIW_VARIANTS),
                "miao": norm(r.get("是否提及米奥兰特") or "") in ("是", "true", "1", "yes")
                        or mention(text, MIAO_VARIANTS),
                "rank": parse_rank(r.get("IIW推荐位次")),
                "accuracy": (r.get("信息准确度") or "").strip(),
                "domains": (r.get("引用域名") or ""),
                "src": "人工",
            })
    return rows


def load_api(path):
    """API 快照：从回答文本识别提及，位次留待人工判定"""
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            text = (r.get("回答全文") or "")
            rows.append({
                "date": (r.get("采样时间") or "")[:10],
                "engine": (r.get("引擎") or "DeepSeek").strip(),
                "qid": (r.get("问题编号") or "").strip().upper(),
                "question": (r.get("问题原文") or "").strip(),
                "answer": text,
                "iiw": mention(text, IIW_VARIANTS),
                "miao": mention(text, MIAO_VARIANTS),
                "rank": None,
                "accuracy": "",
                "domains": (r.get("引用域名") or ""),
                "src": "API",
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description="GEO 基线分析")
    ap.add_argument("--dir", default=BASE)
    ap.add_argument("--only", default="", help="只看指定引擎，逗号分隔")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    all_rows = []
    for p in sorted(glob.glob(os.path.join(args.dir, "GEO采样_基线记录_*.csv"))):
        all_rows += load_manual(p)
    for p in sorted(glob.glob(os.path.join(args.dir, "GEO采样_api快照_*.csv"))):
        all_rows += load_api(p)
    for p in sorted(glob.glob(os.path.join(args.dir, "GEO采样_浏览器_*.csv"))):
        all_rows += load_api(p)   # 浏览器采样 CSV 列结构与 api 快照一致

    if not all_rows:
        print("❌ 未找到任何采样 CSV（GEO采样_基线记录 / api快照 / 浏览器）", file=sys.stderr)
        sys.exit(1)

    if args.only:
        keep = {e.strip() for e in args.only.split(",")}
        all_rows = [r for r in all_rows if r["engine"] in keep]

    # 去重：同一 (引擎, 问题编号) 只保留回答最长的一条（多次采样/重试产生重复记录）
    best = {}
    for r in all_rows:
        key = (r["engine"], r["qid"])
        if key not in best or len(r["answer"]) > len(best[key]["answer"]):
            best[key] = r
    all_rows = list(best.values())

    # 合并人工回填的位次（rank）：读取专用位次回填文件 GEO采样_位次回填_*.csv
    # （人工判定过 IIW 在回答推荐列表中的名次；分析脚本不覆盖此文件）
    rank_map = {}
    for p in sorted(glob.glob(os.path.join(args.dir, "GEO采样_位次回填_*.csv"))):
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    rk = (row.get("rank") or "").strip()
                    qid = (row.get("qid") or "").strip()
                    if rk and rk.isdigit() and qid:
                        for r in all_rows:
                            if r["qid"] == qid:
                                rank_map[(r["engine"], qid)] = int(rk)
        except Exception:
            continue
    for r in all_rows:
        key = (r["engine"], r["qid"])
        if key in rank_map:
            r["rank"] = rank_map[key]
    print(f"📊 有效记录：{len(all_rows)} 条（已去重，含人工位次 {len(rank_map)} 条）")

    # 标准化记录落盘（可回填）
    ts = datetime.datetime.now().strftime("%Y%m%d")
    detail_path = os.path.join(args.dir, f"GEO采样_合并明细_{ts}.csv")
    with open(detail_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)

    # ---- 统计 ----
    engines = collections.OrderedDict()
    for r in all_rows:
        engines.setdefault(r["engine"], []).append(r)

    groups = collections.OrderedDict()
    for r in all_rows:
        g = GROUP_MAP.get(r["qid"][:1], "其他")
        groups.setdefault(g, []).append(r)

    dom_counter = collections.Counter()
    comp_counter = collections.Counter()
    acc_issues = []
    pending_rank = []
    for r in all_rows:
        for d in re.split(r"[;；,，]", r["domains"]):
            d = d.strip()
            if d:
                dom_counter[d] += 1
        if r["answer"]:
            for c in COMPETITORS:
                if c in norm(r["answer"]):
                    comp_counter[c] += 1
        if r["accuracy"] and "正确" not in r["accuracy"]:
            acc_issues.append(r)
        if r["rank"] is None and r["iiw"]:
            pending_rank.append(r)

    # ---- 报告 ----
    L = []
    L.append(f"# GEO 基线采样报告 {ts}\n")
    L.append(f"- 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append(f"- 记录来源：{len(all_rows)} 条（人工 {sum(1 for r in all_rows if r['src']=='人工')} / API {sum(1 for r in all_rows if r['src']=='API')}）")
    L.append("")

    L.append("## 一、按引擎总览\n")
    L.append("| 引擎 | 提问数 | 提及IIW | 提及率 | TOP3 | TOP3率(占提及) | 提及米奥兰特 |")
    L.append("|---|---|---|---|---|---|---|")
    tot = {"n": 0, "iiw": 0, "top3": 0, "miao": 0}
    for eng, rs in engines.items():
        n = len(rs); iiws = sum(1 for r in rs if r["iiw"])
        top3 = sum(1 for r in rs if r["rank"] is not None and 1 <= r["rank"] <= 3)
        miao = sum(1 for r in rs if r["miao"])
        tot["n"] += n; tot["iiw"] += iiws; tot["top3"] += top3; tot["miao"] += miao
        L.append(f"| {eng} | {n} | {iiws} | {iiws/n*100:.1f}% | {top3} | {top3/iiws*100:.1f}%" if iiws else f"| {eng} | {n} | {iiws} | 0% | 0 | — | {miao} |")
        if iiws:
            L[-1] = f"| {eng} | {n} | {iiws} | {iiws/n*100:.1f}% | {top3} | {top3/iiws*100:.1f}% | {miao} |"
    n = tot["n"]
    L.append(f"| **合计** | {n} | {tot['iiw']} | {tot['iiw']/n*100:.1f}% | {tot['top3']} | {tot['top3']/tot['iiw']*100:.1f}%" if tot["iiw"] else f"| **合计** | {n} | 0 | 0% | 0 | — | {tot['miao']} |")
    L.append("")

    L.append("## 二、按核心词（全引擎合计）\n")
    L.append("| 核心词 | 提问数 | 提及IIW | 提及率 |")
    L.append("|---|---|---|---|")
    for g, rs in groups.items():
        iiws = sum(1 for r in rs if r["iiw"])
        L.append(f"| {g} | {len(rs)} | {iiws} | {iiws/len(rs)*100:.1f}% |")
    L.append("")

    L.append("## 三、引用域名 Top15\n")
    L.append("| 域名 | 出现次数 |")
    L.append("|---|---|")
    for d, c in dom_counter.most_common(15):
        L.append(f"| {d} | {c} |")
    L.append("")

    L.append("## 四、竞争/其他展会实体出现频次（内部研判用）\n")
    L.append("| 实体 | 出现次数 |")
    L.append("|---|---|")
    for c, cnt in comp_counter.most_common(20):
        L.append(f"| {c} | {cnt} |")
    L.append("")

    if acc_issues:
        L.append("## 五、信息准确性问题（提及 IIW 但信息有误）\n")
        for r in acc_issues[:30]:
            L.append(f"- {r['date']} {r['engine']} {r['qid']}：{r['accuracy']}")
        L.append("")

    if pending_rank:
        L.append("## 六、提及但位次待人工判定（API 轮）\n")
        L.append("> 按以下格式回填到合并明细 CSV 的 rank 列：1=回答中第一个推荐位，2/3 依此类推；未进前五填 5 以外任意 >5 值。")
        for r in pending_rank[:40]:
            L.append(f"- {r['engine']} {r['qid']}（{r['question']}）")
        L.append("")

    out_path = args.out or os.path.join(args.dir, f"GEO采样_基线报告_{ts}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"📊 报告已生成: {out_path}")
    print(f"📄 合并明细: {detail_path}")


if __name__ == "__main__":
    main()
