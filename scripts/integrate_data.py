# -*- coding: utf-8 -*-
"""
GEO 5 引擎数据整合器
===================
读取 5 个引擎（豆包/文心一言/通义千问/腾讯元宝/Kimi）的全部浏览器采样 CSV，
按「引擎 + 问题编号」去重，每题取回答最长的一条，导出整合文件：

    输出1: GEO采样_5引擎整合_YYYYMMDD.csv       （300 行：5引擎 × 60问）
    输出2: GEO采样_5引擎整合_YYYYMMDD.xlsx 需求说明 （如无 openpyxl 则仅 CSV）

用法：
    python integrate_data.py
"""

import os, sys, glob, csv, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
ENGINES = ["豆包", "文心一言", "通义千问", "腾讯元宝", "Kimi"]

CSV_HEADER = ["引擎", "问题编号", "问题原文", "回答全文", "回答长度", "采样文件", "原始状态"]


def load_all():
    """读取全部浏览器采样 CSV，按 (引擎, 问题编号) 去重取最长"""
    best = {}
    for f in sorted(glob.glob(os.path.join(BASE, "GEO采样_浏览器_*.csv"))):
        try:
            with open(f, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    eng = (row.get("引擎") or "").strip()
                    qid = (row.get("问题编号") or "").strip().upper()
                    qtext = (row.get("问题原文") or "").strip()
                    ans = (row.get("回答全文") or "").strip()
                    st = (row.get("原始状态") or "").strip()
                    if not eng or not qid or not ans:
                        continue
                    key = (eng, qid)
                    if key not in best or len(ans) > len(best[key]["ans"]):
                        best[key] = {
                            "eng": eng, "qid": qid, "qtext": qtext,
                            "ans": ans, "status": st, "file": os.path.basename(f),
                        }
        except Exception:
            continue
    return best


def main():
    data = load_all()
    ts = datetime.datetime.now().strftime("%Y%m%d")

    # 按引擎固定顺序 + 题号排序输出
    qid_order = lambda q: (q[0], int(q[1:]))
    rows = sorted(data.values(), key=lambda r: qid_order(r["qid"]))

    out_csv = os.path.join(BASE, f"GEO采样_5引擎整合_{ts}.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow([r["eng"], r["qid"], r["qtext"], r["ans"], len(r["ans"]), r["file"], r["status"]])

    # 统计
    per_eng = {}
    for r in rows:
        per_eng.setdefault(r["eng"], 0)
        per_eng[r["eng"]] += 1

    print(f"✅ 整合完成: {out_csv}")
    print(f"   总行数: {len(rows)}")
    for e in ENGINES:
        print(f"   {e}: {per_eng.get(e, 0)} 条")
    print(f"   文件大小: {os.path.getsize(out_csv) / 1024:.1f} KB")
    print("   说明: 每题取回答最长的一条（多次重试/分文件产生的短记录已剔除）")


if __name__ == "__main__":
    main()
