"""엑셀 → preexisting/work/xlsx.json (3-1 대표담보 · DATA · 담보목록)"""
import json, os, re, sys, openpyxl
U = sys.argv[1]  # 업로드 폴더
OUTD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
os.makedirs(OUTD, exist_ok=True)
fs = [os.path.join(U, f) for f in os.listdir(U) if f.endswith(".xlsx")]
cur = next(f for f in fs if "DATA" in openpyxl.load_workbook(f, read_only=True).sheetnames)
ref = next(f for f in fs if f != cur)
wb = openpyxl.load_workbook(cur, read_only=True, data_only=True)
data = []
for r in wb["DATA"].iter_rows(min_row=2, values_only=True):
    m = re.match(r"^\[(\w+)\]\s*(.*)$", r[3] or "")
    data.append({"prod": r[0], "cov": r[1], "gubun": r[2], "code": m.group(1) if m else None,
                 "rep": m.group(2) if m else None, "notice": r[4], "text": r[5], "note": r[6]})
hr = list(wb["기왕증 보상 현황"].iter_rows(values_only=True))
target = [{"code": r[1], "name": r[2]} for r in hr[3:] if r[0] == "2.기왕증 보상"]
codes = list(wb["대표담보코드"].iter_rows(min_row=2, values_only=True))
wb2 = openpyxl.load_workbook(ref, read_only=True, data_only=True)
covlist = [{"code": a, "name": b} for a, b in wb2["담보목록"].iter_rows(min_row=2, values_only=True) if a]
prods = [list(r) for r in wb2["상품목록"].iter_rows(min_row=2, values_only=True)]
json.dump({"data": data, "target": target, "codes": codes, "covlist": covlist, "prods": prods},
          open(os.path.join(OUTD, "xlsx.json"), "w"), ensure_ascii=False)
tc = {t["code"] for t in target}
rows = [d for d in data if d["code"] in tc]
print("3-1 대표담보", len(target), "· DATA 상품담보", len(rows), "· 구분", {g: sum(1 for d in rows if d["gubun"] == g) for g in {d["gubun"] for d in rows}})
print("담보목록", len(covlist), "· 상품목록", len(prods))
