"""근로계약서 양식집(.hwpx) 생성기
사용: python3 make_contracts.py [출력 폴더]
hwpx-writer 스킬의 template.hwpx를 바탕으로, 칸 너비·칸 안 정렬을 직접 지정한 표로 만든다.
"""
import os, re, sys, zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

TEMPLATE = os.path.expanduser(
    "~/.claude/skills/synced/1a06487a-4297-45a1-8aa6-e00842ebfa88_0b44d024-af0b-4188-aa01-a8fb5d95d0e9/hwpx-writer/assets/template.hwpx")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
W = 48190                      # 본문 폭
MAIN = [8600, 8400, 14200, 7600, 9390]   # 본표 5칸

# ── 글자 모양 (id: 높이, 글꼴 0=돋움 1=바탕, 굵게, 색) ──
CHARS = {
    9: (2000, 0, True, "#000000"),   # 제목
    10: (1150, 0, False, "#333333"), # 부제
    11: (1100, 1, False, "#000000"), # 본문
    12: (1000, 1, False, "#000000"), # 표 내용
    13: (1000, 0, True, "#000000"),  # 표 항목명
    14: (1150, 0, True, "#000000"),  # 소제목
    15: (900, 1, False, "#444444"),  # ※ 안내
    16: (1100, 1, True, "#000000"),  # 본문 굵게
}
# ── 문단 모양 (id: 정렬, 왼쪽, 들여, 위, 아래, 줄간격, 다음과 함께) ──
PARAS = {
    22: ("CENTER", 0, 0, 0, 200, 160, 1),
    23: ("CENTER", 0, 0, 0, 1100, 160, 1),
    24: ("JUSTIFY", 0, 0, 0, 700, 160, 0),
    25: ("CENTER", 0, 0, 0, 0, 135, 0),
    26: ("LEFT", 0, 0, 0, 0, 135, 0),
    27: ("JUSTIFY", 0, 0, 0, 0, 135, 0),
    28: ("LEFT", 0, 0, 900, 350, 160, 1),
    29: ("CENTER", 0, 0, 900, 700, 160, 1),
    30: ("RIGHT", 0, 0, 0, 0, 135, 0),
    31: ("LEFT", 0, 0, 0, 0, 100, 0),
}
ALIGN = {"c": 25, "l": 26, "j": 27, "r": 30}


def char_pr(i, h, font, bold, color):
    f = ' '.join(f'{k}="{font}"' for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user"))
    s = lambda v: ' '.join(f'{k}="{v}"' for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user"))
    return (f'<hh:charPr id="{i}" height="{h}" textColor="{color}" shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
            f'<hh:fontRef {f}/><hh:ratio {s(100)}/><hh:spacing {s(0)}/><hh:relSz {s(100)}/><hh:offset {s(0)}/>'
            + ('<hh:bold/>' if bold else '') +
            '<hh:underline type="NONE" shape="SOLID" color="#000000"/><hh:strikeout shape="NONE" color="#000000"/>'
            '<hh:outline type="NONE"/><hh:shadow type="NONE" color="#B2B2B2" offsetX="10" offsetY="10"/></hh:charPr>')


def para_pr(i, align, left, intent, prev, nxt, ls, kwn):
    m = lambda k: (f'<hh:margin><hc:intent value="{intent*k}" unit="HWPUNIT"/><hc:left value="{left*k}" unit="HWPUNIT"/>'
                   f'<hc:right value="0" unit="HWPUNIT"/><hc:prev value="{prev*k}" unit="HWPUNIT"/><hc:next value="{nxt*k}" unit="HWPUNIT"/></hh:margin>'
                   f'<hh:lineSpacing type="PERCENT" value="{ls}" unit="HWPUNIT"/>')
    return (f'<hh:paraPr id="{i}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">'
            f'<hh:align horizontal="{align}" vertical="CENTER"/><hh:heading type="NONE" idRef="0" level="0"/>'
            f'<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" lineWrap="BREAK" keepWithNext="{kwn}" keepLines="0" pageBreakBefore="0" widowOrphan="0"/>'
            '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
            f'{m(1)}</hp:case><hp:default>{m(2)}</hp:default></hp:switch>'
            '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>')


SHADE = ('<hh:borderFill id="4" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
         '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
         '<hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/><hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>'
         '<hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/><hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>'
         '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
         '<hc:fillBrush><hc:winBrush faceColor="#EDF1F7" hatchColor="#999999" alpha="0"/></hc:fillBrush></hh:borderFill>')


# ── 칸 넘침 검사: 함초롬 글자 폭 근사(한글 1em, 빈칸·숫자·영문 0.55em, 문장부호 0.4em) ──
WARN = []


def text_em(t):
    e = 0
    for ch in t:
        if ord(ch) >= 0x1100 and ch not in "·「」": e += 1.0
        elif ch == " " or ch.isalnum(): e += 0.55
        else: e += 0.4
    return e


# ── 표 ──
def C(t="", cs=1, rs=1, a="l", h=False):
    """표 칸: t=글(줄 목록 또는 \\n), cs/rs=합치기, a=정렬(c/l/j/r), h=항목명(음영·굵게)"""
    return dict(t=t, cs=cs, rs=rs, a=a, h=h)


class Doc:
    def __init__(self):
        self.ps, self.tid, self.sid, self.prv = [], 0, 1000, []

    def p(self, text, pid, cid, page_break=False):
        self.prv.append(text)
        self.ps.append(f'<hp:p id="0" paraPrIDRef="{pid}" styleIDRef="0" pageBreak="{1 if page_break else 0}" columnBreak="0" merged="0">'
                       f'<hp:run charPrIDRef="{cid}"><hp:t>{escape(text)}</hp:t></hp:run></hp:p>')

    def table(self, cols, rows, border=True):
        assert sum(cols) == W, (cols, sum(cols))
        n = len(cols)
        occ, cells = set(), []
        for r, row in enumerate(rows):
            c = 0
            for cell in row:
                while (r, c) in occ:
                    c += 1
                for rr in range(r, r + cell["rs"]):
                    for cc in range(c, c + cell["cs"]):
                        occ.add((rr, cc))
                cells.append((r, c, cell))
                c += cell["cs"]
            assert c <= n, f"칸 수 초과: {row}"
        for r in range(len(rows)):
            for c in range(n):
                assert (r, c) in occ, f"빈 칸 {r},{c}: {rows[r]}"
        self.tid += 1
        RH = 1700
        out = [f'<hp:tbl id="{1000 + self.tid}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" rowCnt="{len(rows)}" colCnt="{n}" cellSpacing="0" borderFillIDRef="{3 if border else 1}" noAdjust="0">'
               f'<hp:sz width="{W}" widthRelTo="ABSOLUTE" height="{RH*len(rows)}" heightRelTo="ABSOLUTE" protect="0"/>'
               '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               '<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:inMargin left="510" right="510" top="200" bottom="200"/>']
        for r in range(len(rows)):
            out.append('<hp:tr>')
            for (rr, c, cell) in cells:
                if rr != r:
                    continue
                w = sum(cols[c:c + cell["cs"]])
                ml = 510 if border else 0
                bf = (4 if cell["h"] else 3) if border else 1
                lines = cell["t"] if isinstance(cell["t"], list) else str(cell["t"]).split("\n")
                for ln in lines:
                    em = 0.9 if ln.startswith("※") else 1.0
                    need = text_em(ln) * 1000 * em
                    if border and need > (w - 2*ml) * 0.97 and ("  " in ln or cell["h"] or len(ln) < 40):
                        WARN.append(f"{need/(w-2*ml):.2f} | {ln}")
                pid = ALIGN[cell["a"]]
                paras = []
                for ln in lines:
                    self.prv.append(ln)
                    cid = 13 if cell["h"] else (15 if ln.startswith("※") else 12)
                    paras.append(f'<hp:p id="0" paraPrIDRef="{pid}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                                 f'<hp:run charPrIDRef="{cid}"><hp:t>{escape(ln)}</hp:t></hp:run></hp:p>')
                self.sid += 1
                out.append(f'<hp:tc name="" header="0" hasMargin="1" protect="0" editable="0" dirty="0" borderFillIDRef="{bf}">'
                           f'<hp:subList id="{self.sid}" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="{"TOP" if not border else "CENTER"}" linkListIDRef="0" linkListNextIDRef="0" textWidth="{w - 2*ml}" textHeight="0" hasTextRef="0" hasNumRef="0">'
                           + "".join(paras) + '</hp:subList>'
                           f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="{cell["cs"]}" rowSpan="{cell["rs"]}"/>'
                           f'<hp:cellSz width="{w}" height="{RH*cell["rs"] if border else 600}"/>'
                           f'<hp:cellMargin left="{ml}" right="{ml}" top="{200 if border else 60}" bottom="{200 if border else 60}"/></hp:tc>')
            out.append('</hp:tr>')
        out.append('</hp:tbl>')
        self.ps.append('<hp:p id="0" paraPrIDRef="31" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                       f'<hp:run charPrIDRef="12">{"".join(out)}<hp:t/></hp:run></hp:p>')

    def clauses(self, items, num=True):
        """번호 붙은 조항: 번호 칸과 본문 칸을 나눈 테두리 없는 표 → 둘째 줄도 본문 첫 글자에 정확히 맞음"""
        rows = []
        for i, t in enumerate(items, 1):
            mark = "※" if t.startswith("※") else (f"{i}." if num else "·")
            body = t[1:].strip() if t.startswith("※") else t
            rows.append([C(mark, a="l"), C(body, a="j")])
        self.table([2000, W - 2000], rows, border=False)

    def save(self, path, title):
        with zipfile.ZipFile(TEMPLATE) as z:
            parts = {n: z.read(n) for n in ("version.xml", "META-INF/container.xml", "META-INF/manifest.xml", "META-INF/container.rdf")}
            header = z.read("Contents/header.xml").decode()
            hpf = z.read("Contents/content.hpf").decode()
        header = header.replace('<hh:borderFills itemCnt="3">', '<hh:borderFills itemCnt="4">').replace('</hh:borderFills>', SHADE + '</hh:borderFills>')
        assert '<hh:charProperties itemCnt="9">' in header and '<hh:paraProperties itemCnt="22">' in header
        header = header.replace('<hh:charProperties itemCnt="9">', f'<hh:charProperties itemCnt="{9+len(CHARS)}">')
        header = header.replace('</hh:charProperties>', "".join(char_pr(i, *v) for i, v in CHARS.items()) + '</hh:charProperties>')
        header = header.replace('<hh:paraProperties itemCnt="22">', f'<hh:paraProperties itemCnt="{22+len(PARAS)}">')
        header = header.replace('</hh:paraProperties>', "".join(para_pr(i, *v) for i, v in PARAS.items()) + '</hh:paraProperties>')
        first, rest = self.ps[0], self.ps[1:]
        # 첫 문단(제목)에 구역 정의·쪽 번호를 붙인다
        secpr = ('<hp:run charPrIDRef="9"><hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">'
                 '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/><hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
                 '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
                 '<hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>'
                 '<hp:pagePr landscape="WIDELY" width="59528" height="84188" gutterType="LEFT_ONLY"><hp:margin header="2835" footer="2835" gutter="0" left="5669" right="5669" top="4252" bottom="4252"/></hp:pagePr>'
                 '<hp:footNotePr><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/><hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/><hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/><hp:numbering type="CONTINUOUS" newNum="1"/><hp:placement place="EACH_COLUMN" beneathText="0"/></hp:footNotePr>'
                 '<hp:endNotePr><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/><hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/><hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/><hp:numbering type="CONTINUOUS" newNum="1"/><hp:placement place="END_OF_DOCUMENT" beneathText="0"/></hp:endNotePr>'
                 '<hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER"><hp:offset top="1417" left="1417" right="1417" bottom="1417"/></hp:pageBorderFill>'
                 '<hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER"><hp:offset top="1417" left="1417" right="1417" bottom="1417"/></hp:pageBorderFill>'
                 '<hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER"><hp:offset top="1417" left="1417" right="1417" bottom="1417"/></hp:pageBorderFill>'
                 '</hp:secPr><hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/></hp:ctrl></hp:run>'
                 '<hp:run charPrIDRef="11"><hp:ctrl><hp:pageNum pos="BOTTOM_CENTER" formatType="DIGIT" sideChar="-"/></hp:ctrl><hp:t/></hp:run>')
        first = re.sub(r'(<hp:p [^>]*>)', lambda m: m.group(1) + secpr, first, count=1)
        ns = ('xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
              'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
              'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
              'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf/" xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
              'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" xmlns:epub="http://www.idpf.org/2007/ops" xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"')
        sec = f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {ns}>{first}{"".join(rest)}</hs:sec>'
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        hpf = re.sub(r'<opf:title>.*?</opf:title>', f'<opf:title>{escape(title)}</opf:title>', hpf)
        hpf = re.sub(r'(<opf:meta name="(?:Created|Modified)Date" content="text">).*?(</opf:meta>)', rf'\g<1>{now}\g<2>', hpf)
        settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
                    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"><ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/></ha:HWPApplicationSetting>')
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", b"application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr("version.xml", parts["version.xml"], compress_type=zipfile.ZIP_STORED)
            for n in ("META-INF/container.xml", "META-INF/manifest.xml", "META-INF/container.rdf"):
                z.writestr(n, parts[n], compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("settings.xml", settings, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("Contents/content.hpf", hpf.encode(), compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("Contents/header.xml", header.encode(), compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("Contents/section0.xml", sec.encode(), compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("Preview/PrvText.txt", "\n".join(self.prv).encode(), compress_type=zipfile.ZIP_DEFLATED)


# ── 공통 문구 ──
DATE = "     년     월     일"
FROM_TO = f"{DATE}부터 {DATE}까지"
TIME = "    시    분부터    시    분까지"
WON = "              원"
WON4 = "          원"
NOTE_5 = "※ 상시 근로자 5명 미만 사업장은 연장·야간·휴일근로 가산수당(근로기준법 제56조), 연차유급휴가(제60조), 해고 제한(제23조), 휴업수당(제46조) 등과 기간제법(초과근로 제한·가산 포함)이 적용되지 않습니다."


def L(label, content, a="l"):
    return [C(label, a="c", h=True), C(content, cs=4, a=a)]


def G(label, items):
    """여러 줄 묶음: items = (항목, 내용) 또는 (항목, 내용, 항목, 내용)"""
    rows = []
    for i, it in enumerate(items):
        row = [C(label, rs=len(items), a="c", h=True)] if i == 0 else []
        row.append(C(it[0], a="c", h=True))
        if len(it) == 2:
            row.append(C(it[1], cs=3))
        else:
            row += [C(it[1]), C(it[2], a="c", h=True), C(it[3])]
        rows.append(row)
    return rows


def hours_rows(days="매주     일 (     요일 ~     요일)", weekly="1주     시간"):
    return [L("소정근로시간", [f"{TIME}  (1일     시간, {weekly})"]),
            L("휴게시간", [f"{TIME}  (     분)", "※ 근로시간 4시간에 30분 이상, 8시간에 1시간 이상 (근로기준법 제54조)"]),
            L("근무일·휴일", [f"근무일 : {days}", "주휴일 : 매주     요일 (유급, 1주 소정근로일 개근 시)"])]


PERIOD = ["□ 기간의 정함이 없음        □ 기간의 정함이 있음", FROM_TO, "※ 기간의 정함이 없으면 시작일만 적습니다."]
PAYDAY = ("지 급 일", "매월     일 (휴일이면 그 전날 지급)")
PAYWAY = ("지급 방법", "□ 근로자 명의 통장 입금      □ 직접 지급")
OVER = ("가산수당", ["연장·야간·휴일근로 : 통상임금의 50% 가산", "휴일근로 중 8시간 초과분 : 100% 가산"])
BONUS = ("상 여 금", "□ 있음 (                    )      □ 없음")

PAY_MONTH = G("임  금", [
    ("월 급여", f"월{WON} (세전, 기본급 + 고정수당)"),
    ("기 본 급", f"월{WON}", "고정수당", f"월{WON4}"),
    ("수당 내역", f"        수당{WON4},         수당{WON4}"),
    BONUS, OVER, PAYDAY, PAYWAY])
PAY_HOUR = G("임  금", [
    ("시간급", f"시간당{WON}"),
    ("주휴수당", "1주 소정근로일 개근 시 1일 소정근로시간분 지급"),
    ("기타 수당", f"        수당{WON4},         수당{WON4}"),
    BONUS, OVER, PAYDAY, PAYWAY])

PAY_HOUR_PT = G("임  금", [
    ("시간급", f"시간당{WON}"),
    ("주휴수당", ["1주 소정근로일 개근 시 지급", "(1주 소정근로시간 ÷ 40 × 8시간분, 시행령 별표 2)"]),
    ("기타 수당", f"        수당{WON4},         수당{WON4}"),
    BONUS, OVER, PAYDAY, PAYWAY])

COMMON_TAIL = [
    L("연차유급휴가", "근로기준법에서 정하는 바에 따라 부여함"),
    L("사회보험", "□ 고용보험      □ 산재보험      □ 국민연금      □ 건강보험"),
    L("계약서 교부", "사업주는 근로계약을 체결함과 동시에 이 계약서를 사본하여 근로자의 교부 요구와 관계없이 근로자에게 교부함 (근로기준법 제17조)"),
]
GEN_CLAUSES = [
    "사업주는 임금을 지급할 때 임금의 구성항목·계산방법·공제내역 등을 적은 임금명세서를 서면(전자문서 포함)으로 교부한다(근로기준법 제48조 제2항).",
    "사업주와 근로자는 각자가 근로계약, 취업규칙, 단체협약을 지키고 성실하게 이행하여야 한다.",
    "이 계약에 정함이 없는 사항은 근로기준법령, 취업규칙 및 단체협약에 따른다.",
]


def sign_rows(worker_extra=None, who=("사업주", "근로자"), birth="생년월일"):
    rows = [
        [C(who[0], rs=3, a="c", h=True), C("사업체명", a="c", h=True), C(""), C("전화번호", a="c", h=True), C("")],
        [C("주  소", a="c", h=True), C("", cs=3)],
        [C("대 표 자", a="c", h=True), C("(서명 또는 인)", cs=3, a="r")],
        [C(who[1], rs=3, a="c", h=True), C("주  소", a="c", h=True), C("", cs=3)],
        [C("연 락 처", a="c", h=True), C(""), C(birth, a="c", h=True), C("")],
        [C("성  명", a="c", h=True), C("(서명 또는 인)", cs=3, a="r")],
    ]
    if worker_extra:
        rows[3][0]["rs"] += len(worker_extra)
        rows[5:5] = worker_extra
    return rows


def build(f):
    d = Doc()
    d.p(f["title"], 22, 9)
    d.p(f"( {f['sub']} )", 23, 10)
    d.p(f.get("intro", "              (이하 \"사업주\")과(와)              (이하 \"근로자\")은 다음과 같이 근로계약을 체결한다."), 24, 11)
    for blk in f.get("pre", []):
        blk(d)
    rows = []
    for r in f["rows"]:
        rows += r if isinstance(r[0], list) else [r]
    d.table(MAIN, rows)
    for blk in f.get("post", []):
        blk(d)
    d.p(f.get("clause_title", "기타 약정 사항"), 28, 14)
    d.clauses(f.get("clauses", []) + f.get("gen", GEN_CLAUSES))
    if f.get("notes"):
        d.clauses(f["notes"])
    d.p("20      년      월      일", 29, 11)
    d.table(MAIN, sign_rows(f.get("worker_extra"), f.get("who", ("사업주", "근로자")), f.get("birth", "생년월일")))
    for blk in f.get("after", []):
        blk(d)
    d.save(os.path.join(OUT, f["file"] + ".hwpx"), f["title"] + " " + f["sub"])
    return d


# ── 표 덩어리 ──
def week_table(title="근로일 및 근로일별 근로시간"):
    days = ["월", "화", "수", "목", "금", "토", "일"]
    cols = [7002] + [5884] * 7
    T = "   :   "

    def blk(d):
        d.p(title, 28, 14)
        d.table(cols, [
            [C("구  분", a="c", h=True)] + [C(x, a="c", h=True) for x in days],
            [C("근로 여부", a="c", h=True)] + [C("□", a="c") for _ in days],
            [C("시업 시각", a="c", h=True)] + [C(T, a="c") for _ in days],
            [C("종업 시각", a="c", h=True)] + [C(T, a="c") for _ in days],
            [C("휴게시간", a="c", h=True)] + [C("   분", a="c") for _ in days],
            [C("근로시간", a="c", h=True)] + [C("   시간", a="c") for _ in days],
            [C("1주 합계", a="c", h=True), C("1주 소정근로시간 합계     시간  /  주휴일 매주     요일", cs=7, a="c")],
        ])
    return blk


def info_table(title, items):
    """2쌍(항목·내용 ×2) 정보표"""
    def blk(d):
        d.p(title, 28, 14)
        rows = []
        for i in range(0, len(items), 2):
            a, b = items[i], items[i + 1] if i + 1 < len(items) else None
            if b:
                rows.append([C(a, a="c", h=True), C("", cs=2), C(b, a="c", h=True), C("")])
            else:
                rows.append([C(a, a="c", h=True), C("", cs=4)])
        d.table(MAIN, rows)
    return blk


def shift_table(names=("주 간 조", "야 간 조", "        조", "        조"), title="교대조별 근로시간", tail=True):
    cols = [9190, 9750, 9750, 9750, 9750]

    def blk(d):
        d.p(title, 28, 14)
        rows = [[C(x, a="c", h=True) for x in ("근 무 조", "시업 시각", "종업 시각", "휴게시간", "1회 근로시간")]]
        for s in names:
            rows.append([C(s, a="c", h=True), C("     :     ", a="c"), C("     :     ", a="c"), C("     분", a="c"), C("     시간", a="c")])
        if tail:
            rows.append([C("교대 형태", a="c", h=True), C(["□ 2조 2교대    □ 3조 2교대    □ 3조 3교대", "□ 4조 3교대    □ 기타(                    )"], cs=4)])
            rows.append([C("교대 주기", a="c", h=True), C("     일마다 교대  /  근무표는 적용 전월     일까지 근로자에게 알림", cs=4)])
        d.table(cols, rows)
    return blk


def consent_page():
    def blk(d):
        d.p("친권자(후견인) 동의서", 22, 9, page_break=True)
        d.p("( 근로기준법 제66조 )", 23, 10)
        cols = [8600, 8400, 14200, 7600, 9390]
        d.table(cols, [
            [C("친권자\n(후견인)", rs=3, a="c", h=True), C("성  명", a="c", h=True), C(""), C("생년월일", a="c", h=True), C("")],
            [C("주  소", a="c", h=True), C("", cs=3)],
            [C("연 락 처", a="c", h=True), C(""), C("관    계", a="c", h=True), C("")],
            [C("연소근로자", rs=2, a="c", h=True), C("성  명", a="c", h=True), C(""), C("생년월일", a="c", h=True), C("")],
            [C("주  소", a="c", h=True), C("", cs=3)],
            [C("사업장", rs=2, a="c", h=True), C("회 사 명", a="c", h=True), C(""), C("대 표 자", a="c", h=True), C("")],
            [C("소 재 지", a="c", h=True), C("", cs=3)],
        ])
        d.p("본인은 위 연소근로자              이(가) 위 사업장에서 근로를 하는 것에 대하여 동의합니다.", 29, 11)
        d.p("20      년      월      일", 29, 11)
        d.table(MAIN, [[C("친권자(후견인)", a="c", h=True), C("(서명 또는 인)", cs=4, a="r")]])
        d.clauses(["※ 첨부: 가족관계증명서 1부", "※ 사업주는 이 동의서와 가족관계증명서를 사업장에 갖추어 두어야 합니다(근로기준법 제66조)."], num=False)
    return blk


# ── 양식 목록 ──
BASE = [L("근무장소", ""), L("업무내용", "")]
F = []

F.append(dict(file="01_정규직_월급제_근로계약서", title="근 로 계 약 서", sub="정규직 · 월급제",
    rows=[L("근로계약기간", f"{DATE}부터 근로를 시작함 (기간의 정함이 없음)")] + BASE + hours_rows() + [PAY_MONTH] + COMMON_TAIL,
    notes=[NOTE_5]))

F.append(dict(file="02_정규직_연봉제_근로계약서", title="근 로 계 약 서", sub="정규직 · 연봉제",
    rows=[L("근로계약기간", f"{DATE}부터 근로를 시작함 (기간의 정함이 없음)")] + BASE + hours_rows() + [G("임  금", [
        ("연봉 총액", [f"연{WON}", f"(적용 기간 :{DATE} ~{DATE})"]),
        ("월 지급액", f"연봉의 12분의 1인 월{WON}"),
        ("구성 항목", f"기본급 월{WON},  고정수당 월{WON}"),
        ("퇴 직 금", ["연봉에 포함하지 않으며, 계속근로 1년 이상·4주 평균 1주 15시간 이상이면", "퇴직 시 근로자퇴직급여 보장법에 따라 별도 지급 (퇴직연금 가입 시 그 규약에 따름)"]),
        OVER, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["연봉은 매년        월에 사업주와 근로자가 협의하여 다시 정하며, 새 연봉이 정해지기 전까지는 종전 연봉을 지급한다.",
             "연봉에는 퇴직금을 포함하지 않는다. 퇴직금을 연봉에 나누어 미리 지급하는 약정은 효력이 없다."],
    notes=[NOTE_5]))

F.append(dict(file="03_포괄임금_고정연장수당_근로계약서", title="근 로 계 약 서", sub="월급제 · 고정 연장근로수당 포함",
    rows=[L("근로계약기간", f"{DATE}부터 근로를 시작함 (기간의 정함이 없음)")] + BASE + hours_rows() + [G("임  금", [
        ("월 급여", f"월{WON} (세전, 아래 항목의 합계)"),
        ("기본급", f"월{WON}", "통상시급", f"{WON4}"),
        ("고정연장", f"월     시간분{WON}  (통상시급 × 1.5 × 시간)"),
        ("고정야간", f"월     시간분{WON}  (통상시급 × 0.5 × 시간)"),
        ("고정휴일", f"월     시간분{WON}  (통상시급 × 1.5 × 시간)"),
        BONUS, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["통상시급은 기본급과 고정적으로 지급되는 수당 등 통상임금 전체를 월 통상임금 산정 기준시간으로 나누어 계산한다.",
             "고정 연장·야간·휴일근로수당은 위 약정 시간분을 미리 정하여 지급하는 것이며, 실제 근로시간이 약정 시간보다 적더라도 감액하지 않는다.",
             "실제 연장·야간·휴일근로시간이 약정 시간을 넘으면, 넘은 시간에 대한 가산수당을 그 달 임금 지급일에 추가로 지급한다.",
             "사업주는 근로자의 실제 근로시간을 기록·관리한다."],
    notes=["※ 근로시간을 실제로 산정할 수 있는 경우에는 고정수당 약정이 있어도 실제 근로시간에 따른 법정수당 이상을 지급해야 합니다.", NOTE_5]))

F.append(dict(file="04_시급제_통상근로자_근로계약서", title="근 로 계 약 서", sub="시급제 · 전일제(통상근로자)",
    rows=[L("근로계약기간", PERIOD)] + BASE + hours_rows() + [PAY_HOUR] + COMMON_TAIL,
    clauses=["월 임금은 해당 월의 실제 근로시간과 유급 주휴시간에 시간급을 곱하여 계산한다."],
    notes=["※ 시간급은 해당 연도 최저임금 이상이어야 합니다.", NOTE_5]))

F.append(dict(file="05_기간제_계약직_근로계약서", title="기간제 근로계약서", sub="계약직 · 기간의 정함이 있는 근로자",
    rows=[L("근로계약기간", [FROM_TO + "  (     개월)"]),
          L("계약 갱신", ["□ 갱신하지 않음      □ 갱신할 수 있음", "판단 기준 : □ 근무성적  □ 업무량  □ 경영상황  □ 기타(          )"])]
        + BASE + hours_rows() + [PAY_MONTH] + COMMON_TAIL,
    clauses=["근로관계는 계약기간이 끝나면 종료되며, 사업주는 계약 갱신 여부를 계약기간 만료     일 전까지 근로자에게 알린다.",
             "기간제근로자의 사용기간이 2년을 넘으면 기간의 정함이 없는 근로자로 본다(기간제법 제4조 제2항, 같은 조 제1항 각 호의 예외는 제외).",
             "사업주는 같은 사업장에서 같은 종류 또는 비슷한 업무를 하는 정규직 근로자에 비하여 기간제근로자라는 이유로 차별하지 않는다."],
    notes=[NOTE_5]))

F.append(dict(file="06_수습_시용근로자_근로계약서", title="근 로 계 약 서", sub="수습(시용)기간 포함",
    rows=[L("근로계약기간", PERIOD),
          L("수습기간", [FROM_TO + "  (     개월)"])]
        + BASE + hours_rows() + [PAY_MONTH,
          L("수습 중 임금", ["□ 정상 임금의 100%", "□ 정상 임금의     % (최저임금의 90% 이상)",
                          "※ 감액은 1년 이상 계약한 근로자의 수습 시작일부터 3개월까지만 가능하며, 단순노무업무 종사자(최저임금법 제5조 제2항 단서, 고용노동부 고시)는 감액 불가"])] + COMMON_TAIL,
    clauses=["수습기간 중 업무 적격성을 평가하여, 평가 결과가 현저히 낮은 등 정당한 사유가 있으면 본채용을 거부할 수 있다. 평가 항목:                              ",
             "본채용을 거부하는 경우 그 사유와 시기를 서면으로 알린다(근로기준법 제27조).",
             "수습기간은 계속근로기간에 포함한다."],
    notes=["※ 계속 근로한 기간이 3개월 미만인 근로자는 해고예고 적용이 제외되지만(근로기준법 제26조 제1호), 본채용 거부에는 정당한 사유가 필요합니다.", NOTE_5]))

F.append(dict(file="07_단시간근로자_파트타임_근로계약서", title="단시간근로자 근로계약서", sub="파트타임 · 1주 15시간 이상",
    rows=[L("근로계약기간", PERIOD), *BASE,
          L("근로일·시간", "아래 「근로일 및 근로일별 근로시간」 표에 적은 대로 함"),
          L("휴게시간", ["근로일별 근로시간 표에 적은 대로 함", "※ 근로시간 4시간에 30분 이상, 8시간에 1시간 이상 (4시간 근로자가 명시적으로 요청하면 2026. 12. 10.부터 생략 가능)"]),
          L("주휴일", "매주     요일(유급)    ※ 1주 소정근로일을 개근한 경우"), PAY_HOUR_PT,
          L("연차유급휴가", "통상근로자의 근로시간에 비례하여 부여함 (근로기준법 제18조, 시행령 별표 2)")] + COMMON_TAIL[1:],
    post=[week_table()],
    clauses=["소정근로시간을 넘는 근로는 근로자의 동의를 받아야 하며 1주 12시간을 넘을 수 없다(기간제법 제6조).",
             "소정근로시간을 넘는 근로에는 통상임금의 50% 이상을 가산하여 지급한다.",
             "근로일·근로시간을 바꿀 때에는 근로자와 협의하여 서면으로 다시 정한다."],
    notes=[NOTE_5]))

F.append(dict(file="08_초단시간근로자_근로계약서", title="초단시간근로자 근로계약서", sub="4주 평균 1주 소정근로시간 15시간 미만",
    rows=[L("근로계약기간", PERIOD), *BASE,
          L("근로일·시간", "아래 「근로일 및 근로일별 근로시간」 표에 적은 대로 함 (1주 15시간 미만)"),
          L("휴게시간", ["근로일별 근로시간 표에 적은 대로 함", "※ 근로시간 4시간에 30분 이상 (2026. 12. 10.부터 4시간 근로자가 명시적으로 요청하면 생략 가능, 근로기준법 제54조)"]),
          G("임  금", [("시간급", f"시간당{WON}"), ("기타 수당", f"        수당{WON4},         수당{WON4}"),
                      ("초과근로", "소정근로시간 초과분 : 통상임금의 50% 이상 가산"), PAYDAY, PAYWAY]),
          L("휴일 · 휴가", ["주휴일과 연차유급휴가는 적용하지 않음 (근로기준법 제18조 제3항)"]),
          L("사회보험", ["□ 산재보험      □ 고용보험      □ 국민연금      □ 건강보험",
                       "※ 국민연금·건강보험 : 월 소정근로시간 60시간 미만이면 법령이 정한 경우를 제외하고 적용 제외", "※ 고용보험 : 2026. 12. 31.까지는 월 60시간 미만 적용 제외, 2027. 1. 1.부터는 보수가 소득기준(대통령령) 미만이면 적용 제외 (일용근로자·3개월 이상 계속근로자 등은 적용)"]),
          COMMON_TAIL[2]],
    post=[week_table()],
    clauses=["4주 동안을 평균하여 1주 소정근로시간이 15시간 이상이 되면 주휴일·연차유급휴가·퇴직급여 등은 법에 따라 적용한다.",
             "소정근로시간을 넘는 근로는 근로자의 동의를 받아야 하며 1주 12시간을 넘을 수 없다(기간제법 제6조)."],
    notes=["※ 초단시간근로자에게는 퇴직급여(퇴직급여법 제4조 제1항 단서)가 적용되지 않습니다.", NOTE_5]))

F.append(dict(file="09_아르바이트_단기근로자_근로계약서", title="아르바이트 근로계약서", sub="단기 · 시급제",
    rows=[L("근로계약기간", [FROM_TO]), *BASE,
          L("근로 형태", ["□ 전일제 (1일 8시간·1주 40시간)      □ 단시간 (아래 표 기재)", "□ 주말·특정일 근무"]),
          L("소정근로시간", [f"{TIME}  (1일     시간)", "※ 요일별로 다르면 아래 표에 적습니다."]),
          L("휴게시간", f"{TIME}  (     분)"),
          L("주휴일", "매주     요일 (유급, 1주 15시간 이상 근로·개근 시)"), PAY_HOUR_PT,
          L("연차유급휴가", "근로기준법에서 정하는 바에 따라 부여함 (1주 15시간 이상인 경우)")] + COMMON_TAIL[1:],
    post=[week_table("근로일 및 근로일별 근로시간 (요일별로 다른 경우)")],
    clauses=["근로자가 만 18세 미만이면 친권자(후견인) 동의서와 가족관계증명서를 제출하며, 「연소근로자 근로계약서」를 사용한다.",
             "계약기간 중 근로자가 그만두려는 경우에는 인수인계를 위하여 가능한 한 미리 사업주에게 알린다.",
             "사업주는 계약기간이 끝나면 임금 등 모든 금품을 14일 이내에 지급한다(근로기준법 제36조)."],
    notes=["※ 시간급은 해당 연도 최저임금 이상이어야 합니다.", NOTE_5]))

F.append(dict(file="10_일용근로자_일당제_근로계약서", title="일용근로자 근로계약서", sub="일당제",
    rows=[L("근로계약기간", ["□ 1일 :" + DATE, "□ 기간 :" + FROM_TO, "※ 기간 중 사업주가 정한 날에 근로하며, 근로관계는 근로일 단위로 끝남"]), *BASE,
          L("소정근로시간", f"{TIME}  (1일     시간)"),
          L("휴게시간", f"{TIME}  (     분)"),
          L("휴  일", "주휴일: 매주     요일    ※ 1주 소정근로일을 개근한 경우 유급"),
          G("임  금", [("일  급", f"1일{WON} (1일 소정근로시간분)"),
                      ("구성 항목", f"기본일급{WON},  기타 수당{WON}"),
                      ("주휴수당", "1주 15시간 이상 근로·소정근로일 개근 시 지급"), OVER,
                      ("지급일", "□ 매일      □ 매주     요일      □ 매월     일"), PAYWAY])] + COMMON_TAIL,
    clauses=["일급에는 주휴수당·연차수당 등 법정수당을 포함하지 않으며, 해당하는 경우 별도로 지급한다.",
             "사업주는 일용근로소득 지급명세서와 근로내용확인신고서를 법령에 따라 신고한다."],
    notes=[NOTE_5]))

F.append(dict(file="11_건설일용근로자_근로계약서", title="건설일용근로자 근로계약서", sub="건설현장 · 일당제",
    pre=[info_table("공사 개요", ["공 사 명", "현 장 명", "현장 소재지", "공사 기간"])],
    rows=[L("근로계약기간", ["□ 1일 :" + DATE, "□ 기간 :" + FROM_TO, "□ 해당 공정 종료 시까지 (공정명:                    )"]),
          L("근무장소", "위 공사 현장"), L("업무(직종)", "직종:                        작업 내용:                          "),
          L("소정근로시간", f"{TIME}  (1일     시간)"),
          L("휴게시간", f"{TIME}  (     분)"),
          L("휴  일", ["주휴일: 매주     요일    ※ 1주 소정근로일을 개근한 경우 유급", "우천 등 기상 악화로 작업이 중지된 날은 사업주와 협의하여 정함"]),
          G("임  금", [("일  급", f"1일{WON} (1일 소정근로시간분)"),
                      ("구성 항목", f"기본일급{WON},  기타 수당{WON}"),
                      ("주휴수당", "1주 15시간 이상 근로·소정근로일 개근 시 지급"), OVER,
                      ("지급일", "□ 매일      □ 매주     요일      □ 매월     일"), PAYWAY]),
          L("퇴직공제", "□ 건설근로자 퇴직공제 가입 대상 (건설근로자법 제10조)      □ 비대상")] + COMMON_TAIL,
    clauses=["사업주는 작업 전 안전보건교육을 하고 보호구를 지급하며, 근로자는 안전수칙을 지킨다.",
             "사업주는 근로일수를 건설근로자공제회에 신고하고 퇴직공제부금을 납부한다(가입 대상인 경우).",
             "임금은 직접 근로자에게 전액 지급하며, 하수급인이 지급하지 못하면 법에 따라 직상 수급인이 연대하여 책임진다(근로기준법 제44조의2)."],
    notes=[NOTE_5]))

F.append(dict(file="12_연소근로자_18세미만_근로계약서", title="연소근로자 근로계약서", sub="만 18세 미만",
    rows=[L("근로계약기간", PERIOD), *BASE,
          L("소정근로시간", [f"{TIME}  (1일     시간, 1주     시간)", "※ 1일 7시간, 1주 35시간을 넘을 수 없음 (근로기준법 제69조)"]),
          L("휴게시간", f"{TIME}  (     분)"),
          L("근무일 · 휴일", ["근무일: 매주       일(     요일 ~     요일)", "주휴일: 매주     요일(유급)"]), PAY_HOUR] + COMMON_TAIL
        + [L("가족관계증명서\n· 동의서", "□ 가족관계증명서 제출      □ 친권자(후견인) 동의서 제출"),
           L("교부 방법", "근로조건을 서면(전자문서 포함)으로 명시하여 교부함 (근로기준법 제67조 제3항)")],
    clauses=["연장근로는 근로자와 합의한 경우 1일 1시간, 1주 5시간 한도에서만 할 수 있다.",
             "오후 10시부터 오전 6시까지의 야간근로와 휴일근로는 근로자의 동의와 고용노동부장관의 인가 없이 시키지 않는다(근로기준법 제70조).",
             "사업주는 도덕상 또는 보건상 유해·위험한 사업에 근로자를 사용하지 않는다(근로기준법 제65조).",
             "친권자나 후견인은 근로자를 대리하여 근로계약을 체결할 수 없으며, 임금은 근로자 본인에게 지급한다(근로기준법 제67조, 제68조)."],
    notes=["※ 만 15세 미만(중학교 재학 중인 18세 미만 포함)은 고용노동부장관이 발급한 취직인허증이 있어야 합니다(근로기준법 제64조).", NOTE_5],
    after=[consent_page()]))

F.append(dict(file="13_외국인근로자_근로계약서", title="외국인근로자 근로계약서", sub="고용허가제 등 외국인 근로자",
    pre=[info_table("근로자 인적사항", ["성명(영문)", "국    적", "생년월일", "성    별", "여권번호", "등록번호", "체류자격", "체류만료일"])],
    rows=[L("근로계약기간", [FROM_TO + "  (     개월)", "※ 입국 후 근로 시작 시: 입국일부터 기산    □ 해당    □ 해당 없음"]),
          L("수습기간", ["□ 없음      □ 근로 시작일부터     개월", "수습 중 임금 : 정상 임금의     % (최저임금의 90% 이상)", "※ 감액은 1년 이상 계약·수습 3개월 이내만 가능, 단순노무업무는 감액 불가"])]
        + BASE + hours_rows() + [PAY_MONTH,
          G("숙식 제공", [("숙  소", ["□ 제공 : □ 아파트  □ 단독·다세대  □ 기숙사  □ 기타", "□ 제공 안 함"]),
                         ("식  사", "□ 제공 : □ 조식  □ 중식  □ 석식        □ 제공 안 함"),
                         ("근로자 부담", [f"숙소 월{WON},   식사 월{WON}", "※ 근로자의 사전 서면 동의를 받아 임금에서 공제"])])] + COMMON_TAIL,
    clauses=["사업주는 국적·인종 등을 이유로 근로조건을 차별하지 않는다.",
             "사업주는 근로자의 여권·외국인등록증을 보관하지 않으며, 근로자가 요구하면 즉시 돌려준다.",
             "숙식비를 임금에서 공제하려면 근로자의 사전 서면 동의를 받아야 하며, 공제액은 고용노동부 지침이 정한 한도를 넘지 않는다.",
             "이 계약서는 근로자가 이해할 수 있는 언어로 된 번역본을 함께 교부한다."],
    notes=["※ 고용허가제(E-9·H-2) 근로자는 「외국인근로자의 고용 등에 관한 법률」의 표준근로계약서 서식으로 체결해야 하며, 이 양식은 그 밖의 외국인 근로자용 또는 부속 참고용으로 씁니다.", NOTE_5]))

F.append(dict(file="14_촉탁직_정년후재고용_근로계약서", title="촉탁직 근로계약서", sub="정년 후 재고용 · 기간제",
    rows=[L("근로계약기간", [FROM_TO + "  (     개월)"]),
          L("정년퇴직일", DATE + "  (퇴직금 정산:  □ 완료   □ 미완료)"),
          L("계약 갱신", ["□ 갱신하지 않음      □ 갱신할 수 있음", "판단 기준 : □ 건강상태  □ 근무성적  □ 업무량  □ 기타(          )"])]
        + BASE + hours_rows() + [PAY_MONTH] + COMMON_TAIL,
    clauses=["이 계약은 정년퇴직 후 새로 체결하는 기간제 근로계약이며, 계속근로기간은 재고용일부터 새로 계산한다.",
             "55세 이상 고령자와의 근로계약은 기간제법 제4조 제1항 제4호에 따라 2년을 넘더라도 기간의 정함이 없는 근로자로 보지 않는다.",
             "사업주는 계약 갱신 여부를 계약기간 만료     일 전까지 근로자에게 알린다."],
    notes=[NOTE_5]))

F.append(dict(file="15_감시단속적근로자_근로계약서", title="감시·단속적 근로자 근로계약서", sub="경비 · 시설관리 등",
    rows=[L("근로계약기간", PERIOD), *BASE,
          L("근무 형태", ["□ 감시적 근로(경비 등)      □ 단속적 근로(시설관리·운전 등)", "□ 격일제(24시간 교대)      □ 기타(                    )"]),
          L("근무시간", [f"{TIME}  (1회 근무     시간)", "근무 주기: □ 매일  □ 격일  □ 기타(                )"]),
          L("휴게·수면", [f"휴  게 :{TIME}", f"수  면 :{TIME}",
                             "※ 휴게·수면시간에는 근로에서 벗어나 자유롭게 쉴 수 있도록 별도의 장소를 제공함"]),
          L("적용 제외 승인", ["□ 승인 받음 (승인일 :" + DATE + ")        □ 승인 받지 않음",
                           "※ 승인을 받은 경우에만 근로시간·휴게·휴일 규정이 적용 제외됨 (근로기준법 제63조 제3호)"]),
          G("임  금", [("월 급여", f"월{WON} (세전)"), ("기본급", f"월{WON}", "야간수당", f"월{WON4}"),
                      ("기타 수당", f"        수당{WON4},         수당{WON4}"), BONUS, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["승인을 받은 경우에도 오후 10시부터 오전 6시까지의 야간근로에는 통상임금의 50% 이상을 가산하여 지급하며, 연차유급휴가는 근로기준법에 따라 부여한다.",
             "승인을 받지 않은 경우에는 근로시간·휴게·휴일·연장근로에 관한 근로기준법 규정을 모두 적용한다.",
             "휴게·수면시간 중 실제로 업무 지시를 받거나 근로를 한 시간은 근로시간으로 본다."],
    notes=[NOTE_5]))

F.append(dict(file="16_교대제근로자_근로계약서", title="교대제 근로계약서", sub="교대근무 근로자",
    rows=[L("근로계약기간", PERIOD), *BASE,
          L("근로시간", "아래 「교대조별 근로시간」 표와 사업주가 미리 알린 근무표에 따름"),
          L("휴  일", ["주휴일: 근무표에 따라 1주에 평균 1회 이상 유급 휴일 부여", "※ 1주 소정근로일을 개근한 경우"]),
          G("임  금", [("월 급여", f"월{WON} (세전)"), ("기본급", f"월{WON}", "교대수당", f"월{WON4}"),
                      ("야간수당", "오후 10시~오전 6시 근로 : 통상임금의 50% 가산"), OVER, BONUS, PAYDAY, PAYWAY])] + COMMON_TAIL,
    post=[shift_table()],
    clauses=["근무표는 적용 전월에 미리 알리며, 바꿀 때에는 근로자와 협의한다.",
             "교대 근무 사이에는 근로자의 건강을 위하여 충분한 휴식시간(     시간 이상)을 보장한다.",
             "탄력적 근로시간제를 운영하는 경우에는 근로자대표와의 서면 합의 등 근로기준법 제51조, 제51조의2의 요건을 갖춘다."],
    notes=[NOTE_5]))

F.append(dict(file="17_재택_원격근무자_근로계약서", title="재택·원격근무 근로계약서", sub="재택근무 · 원격근무",
    rows=[L("근로계약기간", PERIOD),
          L("근무장소", ["□ 근로자의 주거지 (주소:                                    )", "□ 원격근무 장소 (                                    )", "□ 사무실 출근 : 매주     회"]),
          L("업무내용", "")] + hours_rows() + [
          L("근태 관리", ["□ 근태관리 프로그램 접속 기록      □ 업무 시작·종료 보고", "□ 기타(                    )"]),
          PAY_MONTH,
          L("비용 지원", [f"통 신 비 : 월{WON}", "장    비 : □ 회사 지급(                )      □ 근로자 소유 사용"])] + COMMON_TAIL,
    clauses=["연장·야간·휴일근로는 사업주의 사전 승인을 받아 하며, 승인 받은 근로에는 가산수당을 지급한다.",
             "근로자는 업무 자료와 회사 정보를 안전하게 관리하고, 회사가 정한 보안 수칙을 지킨다.",
             "회사가 지급한 장비는 근로관계가 끝나면 반납한다.",
             "재택근무 중 업무 수행으로 발생한 재해는 산업재해보상보험법에 따라 처리한다."],
    notes=[NOTE_5]))

F.append(dict(file="18_파견근로자_근로계약서", title="파견근로자 근로계약서", sub="파견사업주와 파견근로자",
    pre=[info_table("파견 내용", ["사용사업체", "소 재 지", "파견 업무", "업무 장소", "파견 기간", "지휘·명령자"])],
    rows=[L("근로계약기간", [FROM_TO]), L("근무장소", "위 사용사업체 업무 장소"), L("업무내용", "위 파견 업무")] + hours_rows() + [PAY_MONTH] + COMMON_TAIL,
    clauses=["파견사업주는 근로자를 파견근로자로 고용한다는 사실과 파견 내용을 서면으로 알린다(파견법 제24조, 제26조).",
             "파견 기간은 1년을 넘지 않으며, 당사자 합의로 연장하더라도 총 2년을 넘지 않는다(파견법 제6조, 고령자 등 예외 제외). 일시·간헐적 파견(제5조 제2항)은 3개월 이내로 하고, 합의하면 3개월 범위에서 한 번 연장할 수 있다.",
             "파견 업무는 파견법 제5조 제1항, 같은 법 시행령 별표 1에 정한 대상 업무에 한한다.",
             "파견사업주와 사용사업주는 같은 업무를 하는 사용사업주의 근로자에 비하여 파견근로자라는 이유로 차별하지 않는다(파견법 제21조).",
             "근로시간·휴게·휴일 등은 사용사업주가, 임금·연차유급휴가 등은 파견사업주가 근로기준법상 사용자 책임을 진다(파견법 제34조)."],
    notes=["※ 이 계약서의 \"사업주\"는 파견사업주(파견업체)를 말합니다.", NOTE_5]))

F.append(dict(file="19_병동근로자_교대근무_근로계약서", title="병동근로자 근로계약서", sub="병동 간호사 · 간호조무사 · 간호·간병 인력 등 교대근무",
    rows=[L("근로계약기간", PERIOD), L("근무장소", "                    병원                    병동"),
          L("직종·업무", ["□ 간호사  □ 간호조무사  □ 요양보호사  □ 간병인력  □ 기타(       )", "담당 업무 :                                        "]),
          L("근로시간", "아래 「근무조별 근로시간」 표와 사업주가 미리 알린 근무표에 따름"),
          L("휴  일", ["주휴일 : 근무표에 따라 1주 평균 1회 이상 유급 휴일 부여", "근무표상 휴무일(오프) : 월     일 이상"]),
          G("임  금", [("월 급여", f"월{WON} (세전)"), ("기 본 급", f"월{WON}", "교대수당", f"월{WON4}"),
                      ("야간수당", "오후 10시~오전 6시 근로 : 통상임금의 50% 가산"),
                      ("나이트수당", f"나이트 근무 1회당{WON4} (야간 가산수당과 별도)"), OVER, BONUS, PAYDAY, PAYWAY])] + COMMON_TAIL,
    post=[shift_table(("데이(D)", "이브닝(E)", "나이트(N)", "        "), "근무조별 근로시간")],
    clauses=["근무표는 적용 전월     일까지 알리며, 바꿀 때에는 근로자와 협의한다.",
             "나이트 근무를 마친 뒤에는 다음 근무 시작 전까지 연속하여 11시간 이상의 휴식시간을 준다.",
             "보건업은 근로시간 특례 사업(근로기준법 제59조)이므로, 근로자대표와 서면 합의한 경우에만 1주 12시간을 넘는 연장근로를 시킬 수 있다. 이때도 근로일 종료 후 다음 근로일 시작 전까지 연속 11시간 이상 휴식을 준다.",
             "근무 교대 시 인수인계에 드는 시간과 교육·회의 참석 시간은 근로시간에 포함한다.",
             "여성 근로자의 야간·휴일근로는 본인 동의를 받아야 하며, 임산부·산후 1년 미만 근로자는 근로기준법 제70조, 제71조, 제74조에 따른다."],
    notes=["※ 6개월간 밤 12시~오전 5시를 포함하여 계속되는 8시간 작업을 월평균 4회 이상 하거나, 오후 10시~오전 6시 사이 작업을 월평균 60시간 이상 하는 근로자는 야간작업 특수건강진단 대상입니다(산업안전보건법 제130조, 시행규칙 별표 22).", NOTE_5]))

F.append(dict(file="20_나이트킵_야간전담_근로계약서", title="야간전담(나이트킵) 근로계약서", sub="나이트 근무 전담 간호사 · 간호조무사 등",
    rows=[L("근로계약기간", PERIOD), L("근무장소", "                    병원                    병동"),
          L("직종·업무", ["□ 간호사   □ 간호조무사   □ 기타(          )", "담당 업무 :                                        "]),
          L("근무 형태", ["야간(나이트) 근무만 전담함", "※ 데이·이브닝 근무 배정은 근로자의 동의가 있을 때만 함"]),
          L("근무시간", [f"{TIME}  (1회 근무     시간)", "휴게 :     시    분부터    시    분까지  (     분)"]),
          L("근무일수", ["월     회 이내 나이트 근무 (연속 나이트 근무는     회 이내)", "※ 근무표는 적용 전월     일까지 알림"]),
          L("휴  일", ["주휴일 : 1주 평균 1회 이상 유급 휴일", "나이트 근무 후 휴무 : 연속 나이트 근무를 마친 뒤     일 연속 휴무"]),
          G("임  금", [("월 급여", f"월{WON} (세전)"), ("기 본 급", f"월{WON}", "나이트수당", f"회당{WON4[3:]}"),
                      ("야간수당", "오후 10시~오전 6시 근로 : 통상임금의 50% 가산"),
                      ("근무 미달", "사업주 사정으로 약정 근무일 미달 시 휴업수당 이상"), OVER, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["나이트 근무를 마친 뒤에는 다음 근무 시작 전까지 연속하여 11시간 이상의 휴식시간을 준다.",
             "야간 근무 중 휴게시간은 실제로 업무에서 벗어날 수 있도록 보장하며, 휴게 중 호출로 근무한 시간은 근로시간으로 본다.",
             "사업주는 근로자에게 야간작업 특수건강진단을 받게 하고(산업안전보건법 제130조), 건강상 이유로 야간 근무가 어려우면 주간 근무 전환을 협의한다.",
             "여성 근로자의 야간근로는 본인 동의를 받아야 한다. 임산부는 야간근로를 시키지 않으며, 다만 산후 1년 미만은 본인 동의, 임신 중은 본인의 명시적 청구가 있고 고용노동부장관의 인가를 받은 경우는 예외로 한다(근로기준법 제70조 제2항·제3항)."],
    notes=["※ 나이트수당·야간전담 수당을 따로 정하더라도 법정 야간 가산수당(근로기준법 제56조 제3항)보다 적으면 그 차액을 지급해야 합니다.", NOTE_5]))

F.append(dict(file="21_경비원_근로계약서", title="경비원 근로계약서", sub="공동주택 · 건물 경비",
    rows=[L("근로계약기간", [FROM_TO + "  (     개월)", "※ 1년 미만으로 계약할 때에는 그 사유를 적습니다 : "]),
          L("근무장소", "                    아파트(건물)               동 경비실"),
          L("업무내용", ["경비(순찰·출입 관리·방범)", "□ 청소·미화 보조      □ 재활용품 분리배출 감시·정리", "□ 안내문 게시·우편수취함 투입      □ 주차 관리·택배 보관(위험 방지 범위)", "※ 공동주택은 공동주택관리법 시행령 제69조의2에 허용된 업무만 함 (일반 건물은 해당 없음)"]),
          L("근무 형태", ["□ 격일제(24시간 교대)    □ 3교대    □ 주간    □ 기타(          )"]),
          L("근무시간", [f"{TIME}  (1회 근무     시간)"]),
          L("휴게 · 수면", [f"휴  게 :{TIME}", f"수  면 :{TIME}",
                         "※ 휴게·수면 중에는 경비실을 떠나 휴게시설에서 쉴 수 있도록 보장함"]),
          L("적용제외\n승인", ["□ 승인 받음 (승인일 :" + DATE + ")        □ 승인 받지 않음",
                          "※ 승인을 받은 경우에만 근로시간·휴게·휴일 규정이 적용 제외됨 (근로기준법 제63조 제3호)"]),
          G("임  금", [("월 급여", f"월{WON} (세전)"), ("기 본 급", f"월{WON}", "야간수당", f"월{WON4}"),
                      ("기타 수당", f"        수당{WON4},         수당{WON4}"), BONUS, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["입주자·입주자대표회의·관리주체 등은 경비원에게 위 업무 외의 일(개인 심부름, 대리주차 등)을 시키거나 부당한 지시를 하지 않는다(공동주택관리법 제65조의2 제3항, 공동주택인 경우).",
             "사업주는 휴게시설을 갖추고(산업안전보건법 제128조의2), 냉난방 등 쉴 수 있는 환경을 제공한다.",
             "휴게·수면시간 중 실제로 업무 지시를 받거나 근로를 한 시간은 근로시간으로 보아 임금을 지급한다.",
             "감시적 근로자 승인을 받은 경우에도 야간근로에는 통상임금의 50% 이상을 가산하며, 연차유급휴가는 근로기준법에 따라 부여한다.",
             "관리업체(위탁업체)가 바뀌어도 사업주는 고용 승계 여부를 미리 근로자에게 알린다."],
    notes=["※ 감시적 근로자 승인을 받지 않으면 근로시간·휴게·휴일·연장근로 규정이 모두 적용됩니다.", NOTE_5]))

F.append(dict(file="22_미화원_청소원_근로계약서", title="미화원 근로계약서", sub="청소 · 미화 근로자",
    rows=[L("근로계약기간", PERIOD), L("근무장소", "                    (건물·시설명)               (담당 구역)"),
          L("업무내용", ["□ 실내 청소   □ 화장실 청소   □ 외곽·주차장 청소", "□ 분리수거·폐기물 처리   □ 기타(                              )"])]
        + hours_rows() + [PAY_MONTH,
          L("수습기간", ["□ 없음      □ 있음 (     개월)", "※ 청소원은 단순노무업무로 수습 중에도 최저임금을 감액할 수 없음 (최저임금법 제5조 제2항 단서, 고용노동부 고시)"])] + COMMON_TAIL,
    clauses=["사업주는 근로자에게 장갑·마스크·안전화 등 보호구와 청소 도구를 무상으로 지급한다.",
             "사업주는 근로자가 쉴 수 있는 휴게시설을 갖춘다(산업안전보건법 제128조의2). 계단 밑·창고 등 업무 공간을 휴게실로 쓰게 하지 않는다.",
             "세제·소독제 등 화학물질을 쓸 때에는 사용 방법과 위험성을 미리 교육한다.",
             "오후 10시부터 오전 6시까지 근무하면 통상임금의 50% 이상을 가산하여 지급한다.",
             "용역(도급)업체 소속인 경우, 원청 사업장의 교육·회의 참석 시간도 근로시간에 포함한다."],
    notes=[NOTE_5]))

F.append(dict(file="23_프리랜서_3.3_용역계약서", title="프리랜서 용역계약서", sub="사업소득 3.3% 원천징수 · 근로계약이 아님",
    intro="              (이하 \"발주자\")과(와)              (이하 \"수행자\")은 다음과 같이 용역계약을 체결한다.",
    who=("발주자", "수행자"), birth="주민번호", clause_title="계약 조건",
    rows=[L("용 역 명", ""),
          L("업무 범위", ["", "※ 구체적 업무와 결과물은 별지 과업내용서로 정할 수 있음"]),
          L("결 과 물", ["납품물 :", "납품 기한 :" + DATE]),
          L("계약기간", [FROM_TO]),
          L("수행 방식", ["업무 수행 시간·장소·방법은 수행자가 스스로 정함",
                       "발주자는 결과물의 요구사항만 제시하고, 출퇴근·근무시간을 정하지 않음"]),
          G("용역대금", [("산정 방식", ["□ 총액 :" + WON + " (계약 전체)", "□ 건당 :" + WON + " (결과물 1건)", "□ 월액 :" + WON + " (매월 정액)"]),
                        ("지급 시기", "□ 검수 완료 후     일 이내      □ 매월     일 (전월분)"),
                        ("원천징수", "사업소득세 3% + 지방소득세 0.3% (합계 3.3%) 원천징수 후 지급"),
                        ("비용 부담", "장비·교통비 등 :  □ 수행자 부담      □ 발주자 실비 정산"),
                        ("지급 방법", "수행자 명의 통장 입금")]),
          L("검수 · 보완", ["검수 : 결과물을 받은 날부터     일 이내 결과 통지", "보완 : 하자가 있으면 통지받은 날부터     일 이내"]),
          L("사회보험", ["근로자가 아니므로 4대보험 근로자 가입 대상이 아님",
                       "※ 노무제공자 고용·산재보험 적용 직종(고용보험법 제77조의6, 산재보험법 제91조의15)이면 그에 따름"])],
    clauses=["수행자는 독립된 사업자로서 업무를 수행하며, 발주자는 업무 수행 과정에서 구체적인 지휘·감독을 하지 않는다.",
             "수행자는 이 계약 이행에 지장이 없는 범위에서 다른 발주자와도 자유롭게 계약할 수 있다.",
             "결과물의 저작재산권은 용역대금을 모두 지급한 때 발주자에게 양도된다. 2차적저작물작성권은 □ 함께 양도함 □ 양도하지 않음 (저작권법 제45조 제2항).",
             "양 당사자는 계약 이행 중 알게 된 상대방의 영업비밀과 개인정보를 계약이 끝난 뒤에도 누설하지 않는다.",
             "어느 한쪽이 계약을 위반하면 상대방은     일 이상의 기간을 정하여 시정을 요구하고, 시정되지 않으면 계약을 해지할 수 있다. 해지 시 이미 수행한 부분의 대금은 정산하여 지급한다.",
             "고의 또는 과실로 상대방에게 손해를 입힌 당사자는 그 손해를 배상한다."],
    gen=["이 계약에 정함이 없는 사항은 민법 등 관계 법령과 일반 상관례에 따른다.",
         "이 계약서는 2부를 작성하여 서명 후 각 1부씩 보관한다."],
    notes=["※ 계약서 이름과 관계없이 발주자가 출퇴근 시간·장소를 정하고 업무를 지휘·감독하면 근로자로 인정되어(대법원 2006. 12. 7. 선고 2004다29736 판결) 퇴직금·4대보험·연차수당 등을 부담할 수 있습니다."]))

F.append(dict(file="24_임원_위임계약서", title="임원 위임계약서", sub="근로자가 아닌 등기 임원(이사·감사)",
    intro="주식회사              (이하 \"회사\")과(와)              (이하 \"임원\")은 다음과 같이 위임계약을 체결한다.",
    who=("회  사", "임  원"), clause_title="계약 조건",
    rows=[L("직  위", "□ 대표이사      □ 사내이사      □ 감사      □ 기타(            )"),
          L("선  임", ["    년    월    일  □ 주주총회  □ 이사회 결의로 선임", "등기일 :" + DATE]),
          L("임  기", [FROM_TO, "※ 이사 임기는 3년을 넘지 못함 (상법 제383조)"]),
          L("담당 업무", ""),
          L("업무 수행", ["상법·정관·이사회 결의에 따라 독립적으로 업무를 집행함",
                       "근로기준법상 근로시간·휴게·휴일 규정은 적용하지 않음"]),
          G("보  수", [("보수 총액", f"연{WON}"), ("월 지급액", f"월{WON}"),
                      ("결정 근거", "정관·주주총회 결의로 정한 한도 안 (상법 제388조)"),
                      ("지 급 일", "매월     일"), ("지급 방법", "임원 명의 통장 입금")]),
          L("퇴 직 금", ["□ 정관 또는 주주총회에서 정한 임원퇴직금 지급규정에 따라 지급", "□ 지급하지 않음"]),
          L("사회보험", ["국민연금·건강보험 : 보수를 받는 경우 직장가입자로 적용",
                       "고용보험·산재보험 : 근로자가 아니므로 원칙적으로 적용 제외"])],
    clauses=["이 계약은 회사와 임원 사이의 위임계약이며, 임원은 회사에 대하여 선량한 관리자의 주의의무와 충실의무를 진다(상법 제382조 제2항, 제382조의3).",
             "임원은 이사회 승인 없이 회사와 같은 종류의 영업을 하거나 회사와 거래하지 않는다(상법 제397조, 제398조).",
             "회사는 주주총회 특별결의로 임원을 해임할 수 있으며, 정당한 이유 없이 임기 만료 전에 해임하면 임원은 손해배상을 청구할 수 있다(상법 제385조 제1항).",
             "임원은 언제든지 사임할 수 있으나, 부득이한 사유 없이 회사에 불리한 시기에 사임하여 손해가 생기면 배상한다(민법 제689조).",
             "임원은 재임 중 및 퇴임 후에도 회사의 영업비밀을 누설하지 않는다."],
    gen=["이 계약에 정함이 없는 사항은 상법, 민법, 정관 및 이사회 규정에 따른다.",
         "이 계약서는 2부를 작성하여 서명 후 각 1부씩 보관한다."],
    notes=["※ 임원이라는 명칭이 있어도 실제로는 대표이사 등의 지휘·감독 아래 일정한 노무를 제공하고 그 대가로 보수를 받는다면 근로자로 인정될 수 있습니다(대법원 2003. 9. 26. 선고 2002다64681 판결). 이 경우 근로계약서를 써야 합니다."]))

F.append(dict(file="25_시급제_주휴수당포함_근로계약서", title="근 로 계 약 서", sub="시급제 · 주휴수당 포함 시급",
    rows=[L("근로계약기간", PERIOD)] + BASE + hours_rows() + [G("임  금", [
        ("시 간 급", f"시간당{WON} (기본시급 + 주휴수당분)"),
        ("기본시급", f"{WON4}", "주휴수당분", f"{WON4}"),
        ("산정 방법", ["주휴수당분 = 기본시급 × 1주 주휴시간 ÷ 1주 소정근로시간",
                      "예) 1주 40시간 근무 : 기본시급 × 8 ÷ 40 = 기본시급의 20%"]),
        ("가산수당", ["연장·야간·휴일근로 : 기본시급의 50% 가산", "휴일근로 중 8시간 초과분 : 100% 가산"]),
        PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["기본시급은 해당 연도 최저임금 이상으로 한다.",
             "실제 근로시간에 위 시간급을 곱하여 지급하며, 이로써 유급 주휴일 수당을 함께 지급한 것으로 한다.",
             "1주 소정근로시간이 바뀌면 주휴수당분을 다시 계산하여 서면으로 정한다."],
    notes=["※ 기본시급과 주휴수당분을 나누어 적지 않으면 시간급 전체를 기본시급으로 보아 주휴수당을 따로 지급해야 할 수 있습니다.", NOTE_5]))

F.append(dict(file="26_일당제_상용근로자_근로계약서", title="근 로 계 약 서", sub="일당제 · 계속 근무하는 근로자",
    rows=[L("근로계약기간", PERIOD)] + BASE + hours_rows() + [G("임  금", [
        ("일    급", f"1일{WON} (1일 소정근로시간분)"),
        ("구성 항목", f"기본일급{WON},  고정수당{WON4}"),
        ("월 임금", "일급 × (그 달 근로일수 + 유급 주휴일수)"),
        ("주휴수당", "1주 소정근로일 개근 시 1일분 일급 지급"),
        OVER, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["이 계약은 근로일마다 근로관계가 끝나는 일용근로계약이 아니라 계속 근로하는 근로계약이며, 1년 이상 계속 근로하면 퇴직급여를 지급한다.",
             "일급에 주휴수당·연장근로수당 등을 포함하려면 그 금액을 따로 나누어 적는다.",
             "사업주의 사정으로 쉬게 한 날에는 평균임금의 70% 이상을 휴업수당으로 지급한다(근로기준법 제46조)."],
    notes=[NOTE_5]))


def probation_pages():
    def blk(d):
        d.p("수습기간 평가표", 22, 9, page_break=True)
        d.p("( 수습근로계약서 별지 )", 23, 10)
        d.table(MAIN, [
            [C("성  명", a="c", h=True), C("", cs=2), C("부  서", a="c", h=True), C("")],
            [C("수습기간", a="c", h=True), C(FROM_TO, cs=4, a="c")],
            [C("평 가 자", a="c", h=True), C("(직위)              (성명)              (서명)", cs=4, a="c")],
        ])
        d.p("평가 내용", 28, 14)
        cols = [10000, 22190, 5000, 5500, 5500]
        rows = [[C(x, a="c", h=True) for x in ("평가 항목", "평가 기준", "배  점", "점  수", "비  고")]]
        for item, crit, pt in [("업무 능력", "맡은 업무의 이해도·정확성·처리 속도", "30"),
                               ("업무 태도", "책임감·성실성·적극성", "20"),
                               ("협조·소통", "동료·상사와의 협조, 보고·소통", "20"),
                               ("근태 상황", "출근·지각·조퇴·결근 상황", "15"),
                               ("규정 준수", "안전수칙·취업규칙 등 준수", "15")]:
            rows.append([C(item, a="c", h=True), C(crit), C(pt, a="c"), C(""), C("")])
        rows.append([C("합  계", cs=2, a="c", h=True), C("100", a="c"), C(""), C("")])
        rows.append([C("종합 의견", a="c", h=True), C(["", "", ""], cs=4)])
        rows.append([C("평가 결과", a="c", h=True), C("□ 본채용        □ 수습기간 연장(근로자 동의)        □ 본채용 거부", cs=4, a="c")])
        d.table(cols, rows)
        d.clauses(["※ 평가 기준과 배점은 사업장 사정에 맞게 바꾸어 쓸 수 있으며, 수습 시작 전에 근로자에게 알려 주는 것이 좋습니다.",
                   "※ 본채용 거부는 객관적이고 합리적인 평가 결과에 근거해야 하며, 평가 기록은 보관합니다."], num=False)

        d.p("수습기간 평가 결과 통지서", 22, 9, page_break=True)
        d.p("( 근로기준법 제27조 )", 23, 10)
        d.table(MAIN, [
            [C("근 로 자", a="c", h=True), C("", cs=2), C("생년월일", a="c", h=True), C("")],
            [C("부서·직위", a="c", h=True), C("", cs=4)],
            [C("수습기간", a="c", h=True), C(FROM_TO, cs=4, a="c")],
            [C("평가 결과", a="c", h=True), C(["□ 본채용 :" + DATE + "부터 정식 근로자로 채용함",
                                             "□ 수습기간 연장 :" + DATE + "까지 (근로자 동의 :  □ 있음)",
                                             "□ 본채용 거부 :" + DATE + "자로 근로관계 종료"], cs=4)],
            [C("본채용 거부\n사유", a="c", h=True), C(["(구체적인 사유와 평가 결과를 적습니다)", "", "", ""], cs=4)],
        ])
        d.p("위와 같이 수습기간 평가 결과를 통지합니다.", 29, 11)
        d.p("20      년      월      일", 29, 11)
        d.table(MAIN, [[C("사 업 주", a="c", h=True), C("사업체명 :", cs=2), C("대 표 자", a="c", h=True), C("(서명 또는 인)", a="r")],
                       [C("수 령 인", a="c", h=True), C("수령일 :" + DATE, cs=2), C("근 로 자", a="c", h=True), C("(서명 또는 인)", a="r")]])
        d.clauses(["※ 본채용 거부는 해고에 해당하므로 그 사유와 시기를 서면으로 알려야 효력이 있습니다(근로기준법 제27조).",
                   "※ 계속 근로한 기간이 3개월 이상이면 30일 전에 예고하거나 30일분 이상의 통상임금을 지급해야 합니다(근로기준법 제26조)."], num=False)
    return blk


F.append(dict(file="27_수습근로계약서_평가표포함", title="수습근로계약서", sub="수습(시용) 근로자 · 평가표와 결과 통지서 포함",
    rows=[L("근로계약기간", PERIOD),
          L("수습기간", [FROM_TO + "  (     개월)", "※ 수습기간이 끝나면 평가를 거쳐 본채용 여부를 정함"])]
        + BASE + hours_rows() + [G("임  금", [
            ("정상 임금", [f"□ 월  급 : 월{WON}", f"□ 시  급 : 시간당{WON4}"]),
            ("수습 중 임금", ["□ 정상 임금의 100%", "□ 정상 임금의     % (최저임금의 90% 이상)",
                            "※ 감액은 1년 이상 계약·수습 시작일부터 3개월 이내만 가능, 단순노무업무 종사자는 감액 불가 (최저임금법 제5조 제2항)"]),
            ("기타 수당", f"        수당{WON4},         수당{WON4}"),
            OVER, PAYDAY, PAYWAY])] + COMMON_TAIL,
    clauses=["사업주는 별지 「수습기간 평가표」의 항목과 기준에 따라 근로자를 평가하며, 평가 기준은 수습 시작 시 근로자에게 알린다.",
             "사업주는 수습기간 만료     일 전까지 평가 결과를 서면으로 알리며, 알리지 않으면 수습기간 만료 다음 날 본채용된 것으로 본다.",
             "평가 결과가 현저히 낮은 등 정당한 사유가 있으면 본채용을 거부할 수 있으며, 그 사유와 시기를 서면으로 알린다(근로기준법 제27조).",
             "수습기간은 근로자의 동의를 받아 한 번,     개월 이내에서 연장할 수 있다.",
             "수습기간은 계속근로기간에 포함하며, 본채용 후의 연차유급휴가·퇴직급여 산정에도 포함한다."],
    notes=["※ 계속 근로한 기간이 3개월 미만인 근로자는 해고예고 적용이 제외되지만(근로기준법 제26조 제1호), 본채용 거부에는 정당한 사유가 필요합니다.", NOTE_5],
    after=[probation_pages()]))

if __name__ == "__main__":
    for f in F:
        d = build(f)
        print("✓", f["file"])
    for w in sorted(set(WARN), reverse=True):
        print("넘침?", w)
