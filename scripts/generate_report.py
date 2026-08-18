# -*- coding: utf-8 -*-
"""
GEO 多引擎对比报告生成器
=======================
汇总 5 个引擎（豆包/文心一言/通义千问/腾讯元宝/Kimi）的浏览器采样数据，
每题取最长有效回答，统计提及率 / 米奥兰特提及 / 核心词矩阵 / 竞争格局 / 位次，
输出一份 HTML 多引擎对比报告。

用法：
    python generate_report.py

输出：
    GEO多引擎对比报告_YYYYMMDD.html
"""

import os, sys, glob, csv, re, datetime, collections, html
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))

# 引擎显示名 -> 采样文件关键字
ENGINES = ["豆包", "文心一言", "通义千问", "腾讯元宝", "Kimi"]

GROUP_MAP = {
    "A": "越南机床展参展", "B": "中国参展越南工业展推荐", "C": "越南工业自动化展会",
    "D": "越南建厂设备采购展会", "E": "越南物流设备展会", "F": "越南泵阀管件展会",
}
GROUP_ORDER = ["A", "B", "C", "D", "E", "F"]

IIW_VARIANTS = ["iiw", "国际工业周", "international industry week", "工业周"]
MIAO_VARIANTS = ["米奥兰特", "米奥", "meorient", "300795"]
COMPETITORS = ["mta vietnam", "mta", "viif", "vietnam manufacturing expo", "vme",
               "metalex", "越南国际工业博览会", "vinamac", "cmes", "vimp", "vimal", "automation world",
               "vietwater", "vilog", "vimat", "emidas", "fbc asean", "intermach", "manufacturing indonesia"]


def mention(text, variants):
    t = (text or "").lower()
    return any(v in t for v in variants)


def load_all():
    """读取 5 引擎全部 CSV，每题取最长回答"""
    best = {}  # (engine, qid) -> record
    for f in sorted(glob.glob(os.path.join(BASE, "GEO采样_浏览器_*.csv"))):
        try:
            with open(f, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    eng = (row.get("引擎") or "").strip()
                    qid = (row.get("问题编号") or "").strip().upper()
                    ans = (row.get("回答全文") or "").strip()
                    if not eng or not qid or not ans:
                        continue
                    key = (eng, qid)
                    if key not in best or len(ans) > len(best[key]["ans"]):
                        best[key] = {"ans": ans, "eng": eng, "qid": qid}
        except Exception:
            continue
    return best


def load_ranks():
    """读取人工位次回填（豆包）"""
    ranks = {}
    for f in sorted(glob.glob(os.path.join(BASE, "GEO采样_位次回填_*.csv"))):
        try:
            with open(f, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    qid = (row.get("qid") or "").strip().upper()
                    rk = (row.get("rank") or "").strip()
                    if qid and rk.isdigit():
                        ranks[qid] = int(rk)
        except Exception:
            continue
    return ranks


def main():
    data = load_all()
    ranks = load_ranks()

    # 每题每引擎的有效性（取 100 字以上视为有效；保留所有以供统计）
    by_eng = collections.OrderedDict((e, {}) for e in ENGINES)
    for (eng, qid), rec in data.items():
        if eng in by_eng:
            by_eng[eng][qid] = rec

    # 各引擎统计
    eng_stats = {}
    for eng in ENGINES:
        recs = by_eng[eng]
        n = len(recs)
        iiws = sum(1 for r in recs.values() if mention(r["ans"], IIW_VARIANTS))
        miaos = sum(1 for r in recs.values() if mention(r["ans"], MIAO_VARIANTS))
        # TOP3（仅豆包有位次）
        top3 = sum(1 for qid, r in recs.items() if ranks.get(qid) and 1 <= ranks[qid] <= 3)
        eng_stats[eng] = {"n": n, "iiw": iiws, "miao": miaos, "top3": top3}

    # 核心词矩阵
    kw_matrix = collections.OrderedDict()
    for g in GROUP_ORDER:
        kw_matrix[g] = {}
        for eng in ENGINES:
            recs = by_eng[eng]
            group_recs = {q: r for q, r in recs.items() if q.startswith(g)}
            n = len(group_recs)
            iiws = sum(1 for r in group_recs.values() if mention(r["ans"], IIW_VARIANTS))
            kw_matrix[g][eng] = (n, iiws)

    # 竞争格局（全引擎出现频次）
    comp_counter = collections.Counter()
    for rec in data.values():
        t = (rec["ans"] or "").lower()
        for c in COMPETITORS:
            if c in t:
                comp_counter[c] += 1

    # 位次分布（豆包）
    doubao_recs = by_eng["豆包"]
    rank_dist = collections.Counter()
    rank_detail = []
    for qid, r in sorted(doubao_recs.items()):
        if ranks.get(qid):
            rank_dist[ranks[qid]] += 1
            rank_detail.append((qid, ranks[qid]))

    # ---------- HTML ----------
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    L.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>IIW 越南工业周 · GEO 多引擎对比报告</title>
<style>
:root {{ --blue:#2563eb; --green:#059669; --red:#dc2626; --amber:#d97706; --bg:#f8fafc; --card:#ffffff; --line:#e2e8f0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"Microsoft YaHei", "PingFang SC", sans-serif; background:var(--bg); color:#1e293b; padding:24px; line-height:1.6; }}
.wrap {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:26px; color:#0f172a; margin-bottom:4px; }}
.sub {{ color:#64748b; font-size:13px; margin-bottom:24px; }}
h2 {{ font-size:19px; color:#0f172a; margin:32px 0 12px; padding-left:10px; border-left:4px solid var(--blue); }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:18px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ background:#f1f5f9; font-weight:600; white-space:nowrap; }}
tr:hover td {{ background:#f8fafc; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.rate {{ font-weight:700; }}
.high {{ color:var(--green); }} .mid {{ color:var(--amber); }} .low {{ color:var(--red); }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:600; }}
.b-green {{ background:#dcfce7; color:#166534; }} .b-red {{ background:#fee2e2; color:#991b1b; }} .b-gray {{ background:#f1f5f9; color:#475569; }}
.heat {{ color:#fff; border-radius:4px; padding:2px 6px; display:inline-block; min-width:46px; text-align:center; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; }}
.sum-card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; text-align:center; }}
.sum-num {{ font-size:30px; font-weight:700; color:var(--blue); }}
.sum-label {{ font-size:12px; color:#64748b; margin-top:4px; }}
.note {{ font-size:12px; color:#64748b; margin-top:6px; }}
.footer {{ margin-top:32px; padding-top:12px; border-top:1px solid var(--line); color:#94a3b8; font-size:12px; }}
</style>
</head>
<body><div class="wrap">
<h1>📊 IIW 越南工业周 · GEO 多引擎对比报告</h1>
<div class="sub">生成时间：{ts} ｜ 数据源：5 引擎 × 60 问（泛化意图提问，不含品牌名） ｜ 监测口径：提及率 / 米奥兰特提及 / 位次 / 竞争格局</div>
""")

    # ---- 摘要卡片 ----
    total_iiw = sum(eng_stats[e]["iiw"] for e in ENGINES)
    total_n = sum(eng_stats[e]["n"] for e in ENGINES)
    total_miao = sum(eng_stats[e]["miao"] for e in ENGINES)
    L.append(f"""<div class="summary-grid">
<div class="sum-card"><div class="sum-num">{total_iiw}/{total_n}</div><div class="sum-label">全引擎 IIW 提及（总提及率 {total_iiw/total_n*100:.1f}%）</div></div>
<div class="sum-card"><div class="sum-num">{total_miao}</div><div class="sum-label">全引擎米奥兰特提及</div></div>
<div class="sum-card"><div class="sum-num">{len(ranks)}</div><div class="sum-label">已人工判定位次（豆包）</div></div>
<div class="sum-card"><div class="sum-num">{rank_dist[1] + rank_dist[2] + rank_dist[3]}</div><div class="sum-label">豆包 TOP3 推荐数</div></div>
</div>""")

    # ---- 1. 引擎总览 ----
    L.append('<h2>一、各引擎总览</h2><div class="card"><table>')
    L.append('<tr><th>引擎</th><th class="num">提问数</th><th class="num">提及IIW</th><th class="num">提及率</th><th class="num">提及米奥兰特</th><th class="num">米奥提及率</th><th class="num">TOP3(豆包位次)</th></tr>')
    for eng in ENGINES:
        s = eng_stats[eng]
        n = s["n"] or 1
        rate = s["iiw"] / n * 100
        cls = "high" if rate >= 60 else ("mid" if rate >= 40 else "low")
        miao_rate = s["miao"] / n * 100
        top3_txt = str(s["top3"]) if eng == "豆包" else "—"
        L.append(f'<tr><td><b>{html.escape(eng)}</b></td><td class="num">{s["n"]}</td><td class="num">{s["iiw"]}</td><td class="num rate {cls}">{rate:.1f}%</td><td class="num">{s["miao"]}</td><td class="num">{miao_rate:.1f}%</td><td class="num">{top3_txt}</td></tr>')
    L.append(f'<tr style="font-weight:700"><td>合计</td><td class="num">{total_n}</td><td class="num">{total_iiw}</td><td class="num">{total_iiw/total_n*100:.1f}%</td><td class="num">{total_miao}</td><td class="num">{total_miao/total_n*100:.1f}%</td><td class="num">{rank_dist[1] + rank_dist[2] + rank_dist[3]}</td></tr>')
    L.append('</table><div class="note">⚠️ 豆包位次为人工回填（<code>GEO采样_位次回填_*.csv</code>）；其余引擎位次未判定，TOP3 列以「—」显示。</div></div>')

    # ---- 2. 核心词矩阵 ----
    L.append('<h2>二、核心词 × 引擎提及率矩阵</h2><div class="card"><table>')
    L.append('<tr><th>核心词</th>' + ''.join(f'<th class="num">{html.escape(e)}</th>' for e in ENGINES) + '</tr>')
    for g in GROUP_ORDER:
        L.append(f'<tr><td><b>{GROUP_MAP[g]}</b></td>')
        for eng in ENGINES:
            n, iiws = kw_matrix[g][eng]
            rate = iiws / n * 100 if n else 0
            if rate >= 60:
                color = "#059669"
            elif rate >= 40:
                color = "#d97706"
            elif rate >= 20:
                color = "#b45309"
            else:
                color = "#dc2626"
            L.append(f'<td class="num"><span class="heat" style="background:{color}">{iiws}/{n} ({rate:.0f}%)</span></td>')
        L.append('</tr>')
    L.append('</table><div class="note">🟢≥60% ｜ 🟠40–59% ｜ 🔴&lt;40%。数值为「该引擎该核心词 10 问中提及 IIW 的次数」。</div></div>')

    # ---- 3. 竞争格局 ----
    L.append('<h2>三、竞争格局（全引擎回答中被推荐的展会实体出现频次）</h2><div class="card"><table>')
    L.append('<tr><th>实体</th><th class="num">出现次数</th></tr>')
    for c, cnt in comp_counter.most_common(20):
        L.append(f'<tr><td>{html.escape(c)}</td><td class="num">{cnt}</td></tr>')
    L.append('</table><div class="note">仅统计回答文本中的实体名称出现频次，用于内部研判；写作内容中不点名竞品。</div></div>')

    # ---- 4. 位次分布（豆包）----
    L.append('<h2>四、豆包推荐位次分布（人工回填）</h2><div class="card">')
    if rank_detail:
        L.append('<table><tr><th>位次</th><th class="num">数量</th><th>对应问题</th></tr>')
        for rk in sorted(rank_dist.keys()):
            qids = [q for q, r in rank_detail if r == rk]
            L.append(f'<tr><td><b>第 {rk} 位</b></td><td class="num">{len(qids)}</td><td>{", ".join(qids)}</td></tr>')
        top3_cnt = sum(1 for qid, r in rank_detail if 1 <= r <= 3)
        iiws_cnt = sum(1 for r in doubao_recs.values() if mention(r["ans"], IIW_VARIANTS))
        denom = iiws_cnt or 1
        L.append(f'</table><div class="note">豆包提及 IIW 的 {iiws_cnt} 问中，进入 TOP3 的共 <b>{top3_cnt}</b> 问（TOP3 率 {top3_cnt/denom*100:.1f}%）。</div>')
    else:
        L.append('<div class="note">暂无位次数据。</div>')
    L.append('</div>')

    # ---- 5. 结论与建议 ----
    L.append('<h2>五、结论与下一步建议</h2><div class="card">')
    L.append('<ul>')
    # 引擎排序
    eng_rank = sorted(ENGINES, key=lambda e: -eng_stats[e]["iiw"] / max(eng_stats[e]["n"], 1) * 100)
    best = eng_rank[0]
    L.append(f'<li><b>最佳引擎</b>：{best}（提及率 {eng_stats[best]["iiw"]/max(eng_stats[best]["n"],1)*100:.1f}%）——该引擎对 IIW 的认知度最高。</li>')
    # 核心词排序
    kw_rank = sorted(GROUP_ORDER, key=lambda g: -sum(kw_matrix[g][e][1] for e in ENGINES))
    best_kw = GROUP_MAP[kw_rank[0]]
    worst_kw = GROUP_MAP[kw_rank[-1]]
    L.append(f'<li><b>最强核心词</b>：{best_kw}；<b>最弱核心词</b>：{worst_kw}——建议优先补强最弱词的检索覆盖。</li>')
    L.append(f'<li><b>已发布 vs 未发布</b>：01/02/03（机床/工业展推荐/自动化）已发布，04/05/06（建厂/物流/泵阀）未发布，可对比发布前后提及率变化。</li>')
    L.append('</ul></div>')

    L.append(f'<div class="footer">由 GEO 监测流水线自动生成 ｜ 数据文件见 <code>监测/</code> 目录 ｜ 问题集：60 问固定（A–F 六组）</div>')
    L.append('</div></body></html>')

    out_path = os.path.join(BASE, f"GEO多引擎对比报告_{datetime.datetime.now().strftime('%Y%m%d')}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"✅ 报告已生成: {out_path}")
    print(f"   总记录: {len(data)} | 引擎: {list(by_eng.keys())} | 各引擎题数: {[len(by_eng[e]) for e in ENGINES]}")


if __name__ == "__main__":
    main()
