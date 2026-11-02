"""공통: 경로 · 정규화 · 정규식 · 담보 그룹 (매뉴얼 §8)."""
import hashlib, os, re, unicodedata, warnings

warnings.filterwarnings("ignore")
import pymupdf as fitz  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.environ.get("TERMS_SRC", os.path.join(ROOT, "input"))
OUT = os.environ.get("TERMS_OUT", os.path.join(ROOT, "out"))
WORK = os.path.join(OUT, "work")
WEB = os.path.join(OUT, "web")
ITEMS = os.path.join(WEB, "items")
PLAN = os.path.join(WORK, "plan.json")

TOP = 34.0
FOOT = 0.934

_JO_HEAD = r"^\s*(제\s*\d+\s*조(?:\s*의\s*\d+)?)\s*[(（]"
_GWAN = r"^\s*제\s*\d+\s*관(\s|$)"
_JEOL = r"^\s*제\s*\d+\s*절(\s|$)"
_HO = r"^\s*(\d{1,2})\s*\.\s*(?=\S)"
_MOKL = "가나다라마바사아자차카타파하"
_MOK = rf"^\s*([{_MOKL}])\s*\.\s*(?=\S)"
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
# 항 기호: 원문자 + 전용 글꼴(PUA). 줄머리 '-'는 글머리표(_SUB)로 본다.
_HANG = rf"^\s*([{_CIRCLED}-])\s*"
_MOK2 = rf"^\s*(\d{{1,2}}\)|\(\d{{1,2}}\)|\([{_MOKL}]\)|[{_MOKL}]\)(?=\s)|[㉠-㉭]|[㉮-㉻])\s*(?=\S)"
_SUB = r"^\s*([-ㆍ·•○□■▶◆◇※]|【|\[)"
_PUA_START = r"^\s*[-]"
_PARTICLE = r"^((에서|에게|에|의|을|를|과|와|으로|로|부터|까지)(\s|,|$)|및\s|에\s*따라|\))"
_NOTE = r"^\s*(※|\(주\)|주\s*\d*\))"
_FOOTNUM = r"^\d{1,4}$"

ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ"
_GARBLED = r"[㐀-䶿一-鿿]"
_DOTS = r"[.·…]{3,}"
_NUM_ITEM = r"^(\d{1,3}(?:-\d{1,2})?)\s*\.\s*(.+)$"
_DAEBUN = rf"^([{ROMAN}]+)\s*\.\s*(.+)$"
_INFO = ("가입자유의사항", "주요내용요약서", "보험용어해설", "■색인", "색인")

_SALES = r"\s*\((?:[^()]*?)(?:가입|고지형|심사형)\)"
_RENEW = r"^\s*갱신형\s*"
_ADD = r"\s*추가(?=\s*(?:보장|특별약관))"
_TAIL = r"\s*(?:특별약관|추가특별약관)\s*$"

KIND_LABEL = {"보통약관": "보통약관(일반조항)", "보장조항": "보통약관(보장조항)",
              "특별약관": "특별약관", "일반조항": "관련 특별약관 하위 일반조항"}


def norm_key(s):
    s = unicodedata.normalize("NFKC", s or "").replace("ㆍ", "·").replace("•", "·").replace("∙", "·")
    return re.sub(r"\s+", "", s).lower()


def match_key(s):
    return re.sub(r"[·ㆍ•∙․‧・.\s]", "", norm_key(s))


def sha8(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def pdf_id(fname):
    return "p" + sha8(os.path.basename(fname))


def bundle_id(bkey):
    return "b" + sha8(bkey)


def product_name(fname):
    n = os.path.splitext(os.path.basename(fname))[0]
    return re.sub(r"\s*약관(\s*\(\d+\))?$", "", n).strip()


def is_pet(name):
    return norm_key(name).startswith(norm_key("무배당 펫퍼민트"))


def kind_label(kind, bundle):
    if bundle:
        return "보통약관(일반조항)" if kind == "일반조항" else "보통약관(보장조항)"
    return KIND_LABEL.get(kind, kind)


def balanced_title(text):
    m = re.match(_JO_HEAD, text)
    if not m:
        return None
    sub = text[m.start(1):]
    i = m.start(1) + (sub.index("(") if "(" in sub else sub.index("（"))
    depth = 0
    for j in range(i, len(text)):
        if text[j] in "(（":
            depth += 1
        elif text[j] in ")）":
            depth -= 1
            if depth == 0:
                return re.sub(r"\s+", "", m.group(1)), text[i + 1:j], text[j + 1:]
    return re.sub(r"\s+", "", m.group(1)), None, ""


def group_name(name):
    """담보 그룹: 판매형태·갱신형·추가·전환용·끝 특별약관 제거 (매뉴얼 §5.1)."""
    s = re.sub(r"^\s*\d{1,3}(?:-\d{1,2})?\s*\.\s*", "", name or "")
    s = re.sub(_RENEW, "", s)
    s = re.sub(_SALES, "", s)
    s = re.sub(_ADD, "", s)
    s = re.sub(r"\s*\(?전환용\)?", "", s)
    s = re.sub(_TAIL, "", s).strip()
    return s, match_key(s)


def nchars(s):
    return len(re.sub(r"\s+", "", s or ""))


def list_pdfs():
    return sorted(f for f in os.listdir(SRC_DIR) if f.lower().endswith(".pdf"))
