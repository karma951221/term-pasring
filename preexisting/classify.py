"""대표담보 80개 트리거 분류 → 표 1 · TSV (§1~§3). 사용자 결정은 DECISIONS 에 반영."""
import json, os, re
D = os.path.dirname(os.path.abspath(__file__))
dig = {c["code"]: c for c in json.load(open(os.path.join(D, "work", "digest.json"), encoding="utf-8"))}
TN = {"T1": "질병 진단", "T2": "질병 원인 사망·입원·수술·치료", "T3": "공적 판정·결정", "T4": "검사 시행",
      "T5": "출생·신생아 상태", "T6": "상해 사고", "T7": "의료 이용 사건", "T8": "치아 치료", "T9": "기타"}
CARE = ["COV000054", "COV000059", "COV000061", "COV000085", "COV000086", "COV000088", "COV000089", "COV000093", "COV000094"]
EXAM = ["COV000018", "COV000262", "COV000380", "COV000381", "COV000382", "COV000383", "COV000385", "COV000396",
        "COV000397", "COV000420", "COV000713"]
LTC = ["COV000533", "COV000534", "COV000541", "COV000884", "COV000885", "COV000886", "COV000887", "COV000888", "COV000889"]
DENT = ["COV000230", "COV000363", "COV000364", "COV000425", "COV000426", "COV000430", "COV000681", "COV000683",
        "COV000685", "COV000686", "COV000688", "COV000689", "COV000690", "COV000691", "COV000709", "COV000710",
        "COV000840", "COV000891"]
INTEG = ["COV000299", "COV000620", "COV000722", "COV000854", "COV000858"]
BIRTH = ["COV000329", "COV000518", "COV000552", "COV000553", "COV000554"]
NEWBORN_DZ = ["COV000358", "COV000359", "COV000360"]
# code: (트리거코드, 짧은 설명, 분류, 근거 문장에서 찾을 열쇠말, 비고)
C = {}
for k in CARE: C[k] = ("T6", "상해로 입원", "B", "상해로", "")
for k in EXAM: C[k] = ("T4", "검사 시행(필요 소견 토대)", "B", "필요 소견을 토대로", "검사비 — 사용자 확정")
for k in LTC: C[k] = ("T3", "공적 판정(장기요양 수급대상 인정)", "B", "수급대상으로 인정", "장기요양 — 사용자 확정")
for k in DENT: C[k] = ("T8", "치아 치료", "C", "", "")
for k in INTEG: C[k] = ("T4+T2", "검사 + 수술·주요치료·재활치료 세부보장", "C", "필요 소견을 토대로", "트리거 복수(통합치료 항목별)")
for k in BIRTH: C[k] = ("T5", "출생·신생아 상태", "C", "출생", "")
C_EV_OVERRIDE = {"COV000329": "보험금은 사고발견기간"}
for k in NEWBORN_DZ: C[k] = ("T2", "출생전후기 질병 치료 목적 입원·수술", "A", "출생전후기 질병", "신생아 담보 — 출생 질문과 함께 확인")
C.update({
    "COV000208": ("T2", "질병(대장용종) 제거 수술", "A", "대장용종제거수술", "원인 질병 문구 없음, 수술명 자체가 질병(용종) 전제"),
    "COV000245": ("T2", "여성산과 특정질병으로 사망", "A", "사망한 때", ""),
    "COV000260": ("T1", "부정교합 판정·진단", "A", "부정교합", ""),
    "COV000323": ("T1+T2", "특정선천이상 진단확정 후 수술", "A", "진단확정되고", ""),
    "COV000325": ("T1+T2", "특정선천이상 진단확정 후 수술", "A", "진단확정되고", ""),
    "COV000341": ("T2", "질병 또는 상해로 수술(1-5종)", "A", "수술을 받은 경우", "수술분류표가 상해·질병 공통"),
    "COV000346": ("T1", "근시·원시 판정", "A", "판정되었을 경우", ""),
    "COV000347": ("T1", "고도근시·고도원시 판정", "A", "판정되었을 경우", ""),
    "COV000374": ("T3", "공적 결정(아동학대 검찰 처분결정)", "B", "처분결정", "T3 기본 분류"),
    "COV000422": ("T2", "심장병 치료 목적 개흉심장수술", "A", "개흉심장수술을 받은", "정의 조: 「심장병」의 치료를 직접적인 목적으로"),
    "COV000424": ("T2", "심장시술", "C", "심장시술", "지급사유에 원인 질병 문구 없음"),
    "COV000431": ("T9", "안경 처방·조제", "C", "안경을 처방받고", ""),
    "COV000464": ("T7", "응급실 내원(중증도 등급)", "C", "응급실", ""),
    "COV000465": ("T7", "응급환자 응급실 내원", "C", "응급실", ""),
    "COV000563": ("T2", "조혈모세포이식", "C", "조혈모세포이식", "지급사유에 원인 질병 문구 없음"),
    "COV000632": ("T2", "질병으로 사망", "A", "질병으로 사망", ""),
    "COV000673": ("T9", "질병으로 인한 학업중단 확정", "C", "학업중단상태", ""),
    "COV000769": ("T3", "공적 결정(학교폭력대책심의위원회)", "B", "결정된 경우", "T3 기본 분류"),
    "COV000829": ("T4+T1", "검사 후 치매 진단확정", "C", "진단확정 되지 않은 경우", "트리거 복수(검사 + 진단확정)"),
    "COV000862": ("T2", "질병 치료 목적 수술(연간 2회 이상)", "A", "질병의 치료를 직접적인 목적으로", ""),
})
DECISIONS = []  # (질문, 답, [코드]) — 사용자 답을 받으면 추가하고 분류를 바꾼다
DEC_PATH = os.path.join(D, "work", "decisions.json")
if os.path.exists(DEC_PATH):
    for q, a, codes, cls in json.load(open(DEC_PATH, encoding="utf-8")):
        if not any(k in C for k in codes):
            continue
        DECISIONS.append((q, a, codes))
        for k in codes:
            if k not in C:  # 10/31 신규 대표담보 결정은 final.py 에서 반영
                continue
            t = C[k]
            C[k] = (t[0], t[1], cls, t[3], (t[4] + " · " if t[4] else "") + f"사용자 결정: {a}")


def evidence(c, key):
    lines = [l for b in c["bundles"] for l in b["body"].splitlines() if not l.startswith("[")] + \
            [l for b in c["bundles"] for l in b["body"].splitlines() if l.startswith("[표]")]
    if key:
        for l in lines:
            if key in l:
                s = re.sub(r"^[①-⑳]\s*", "", l)
                i = s.find(key)
                # 열쇠말이 든 문장의 끝(지급합니다/드립니다)까지, 없으면 열쇠말 뒤 60자
                m = re.search(r"(지급합니다|드립니다)\.?", s[i:])
                e = i + (m.end() if m else 60)
                st = max(0, s.rfind(".", 0, i) + 1)
                q = s[st:e].strip()
                return (q[:260] + "…") if len(q) > 260 else q
    l = next((l for l in lines if re.match(r"^[①-⑳]", l)), lines[0] if lines else "")
    q = re.sub(r"^[①-⑳]\s*", "", l)
    return (q[:260] + "…") if len(q) > 260 else q


rows = []
for code, c in dig.items():
    t = C[code]
    note = [t[4]] if t[4] else []
    if len({tuple(b["sig"]) for b in c["bundles"]}) > 1 and t[2] != "C":
        note.append("원문 묶음별 문구 차이(트리거 같음)")
    if c["pre"] or re.search(r"보장개시일\s*(전|이전)", c["note"] or ""):
        note.append("지급사유 밖 보장개시일 전 발병 부지급")
    rows.append({"code": code, "name": c["name"], "n": c["n"], "tcode": t[0], "tdesc": t[1], "cls": t[2],
                 "ev": evidence(c, t[3]), "note": " · ".join(n for n in note if n)})
json.dump(rows, open(os.path.join(D, "work", "rows.json"), "w"), ensure_ascii=False)
CL = {"A": "A 검토대상", "B": "B 기왕증 무관", "C": "C 확인 필요"}
order = {"A": 0, "C": 1, "B": 2}
rows.sort(key=lambda r: (order[r["cls"]], r["code"]))
from collections import Counter
cc = Counter(r["cls"] for r in rows); cn = Counter(); 
for r in rows: cn[r["cls"]] += r["n"]
tc = Counter(r["tcode"] for r in rows)
L = ["# 기왕증 보상(3-1) 대표담보 트리거 분류", "",
     f"> 대상: 대표담보 {len(rows)} · 상품담보 {sum(r['n'] for r in rows)} (입력 `기왕증_보상_트리거분류_입력.md`, 원문 211묶음)", "",
     "| 분류 | 대표담보 | 상품담보 |", "|---|---:|---:|"] + \
    [f"| {CL[k]} | {cc[k]} | {cn[k]} |" for k in "ACB"] + ["",
     "| 트리거 | 대표담보 |", "|---|---:|"] + [f"| {k} {TN.get(k.split('+')[0], '')}{' 외' if '+' in k else ''} | {v} |" for k, v in sorted(tc.items())] + ["",
     "## 표 1 — 대표담보 단위", "",
     "| 대표담보코드 | 대표담보명 | 상품담보 수 | 트리거 | 분류 | 트리거 근거(원문 인용, 한 문장) | 비고 |",
     "|---|---|---:|---|---|---|---|"]
for r in rows:
    ev = r["ev"].replace("|", "\\|")
    L.append(f"| {r['code']} | {r['name']} | {r['n']} | {r['tcode']} {r['tdesc']} | {CL[r['cls']]} | 「{ev}」 | {r['note']} |")
L += ["", "## 표 2 — 사용자 결정 목록", "", "| 질문 | 답 | 적용한 대표담보 |", "|---|---|---|"]
L += [f"| {q} | {a} | {', '.join(cs)} |" for q, a, cs in DECISIONS] or ["| (아직 없음) | | |"]
open(os.path.join(D, "기왕증_보상_트리거분류.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
with open(os.path.join(D, "기왕증_보상_트리거분류.tsv"), "w", encoding="utf-8") as f:
    f.write("대표담보코드\t대표담보명\t분류(A/B/C)\t트리거코드\t트리거설명\t근거문장\t비고\n")
    for r in rows:
        f.write("\t".join([r["code"], r["name"], r["cls"], r["tcode"], r["tdesc"], r["ev"].replace("\t", " "), r["note"]]) + "\n")
print(dict(cc), "상품담보", dict(cn), "트리거", dict(tc))
