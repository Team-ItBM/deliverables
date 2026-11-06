"""화면용 폰트를 만든다. 결과물은 저장소에 넣고, 이 스크립트는 빌드나 CI에서 돌리지 않는다.

원본은 github.com/google/fonts의 ofl/ibmplexsanskr, ofl/notoserifkr이다(둘 다 SIL OFL 1.1).
글자 범위는 영문과 KS X 1001 한글 2,350자다. 화면 문구를 바꿔도 다시 만들 필요가 없다.
IBM Plex는 "Plex"가 예약 글꼴 이름이라, 줄인 파일의 글꼴 이름을 Dowon Sans로 바꾼다.

사용법: pip install fonttools brotli
       python scripts/build_fonts.py <원본 폴더> <출력 폴더>
"""

import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SYMBOLS = "·…‘’“”–—×→←ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ"
SANS = {400: "Regular", 500: "Medium", 600: "SemiBold"}


def charset():
    chars = [chr(c) for c in range(0x20, 0x7F)] + list(SYMBOLS)
    for lead in range(0xB0, 0xC9):
        for trail in range(0xA1, 0xFF):
            try:
                chars.append(bytes([lead, trail]).decode("euc-kr"))
            except UnicodeDecodeError:
                pass
    return "".join(chars)


def rename(font, family, style):
    names = {1: family, 2: "Regular", 3: f"{family} {style}", 4: f"{family} {style}",
             6: f"{family.replace(' ', '')}-{style}", 16: family, 17: style}
    table = font["name"]
    for record in list(table.names):
        if record.nameID in names:
            table.removeNames(nameID=record.nameID)
    for name_id, value in names.items():
        table.setName(value, name_id, 3, 1, 0x409)


def write(font, out):
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = subset.Options().layout_features + ["tnum"]
    options.name_IDs = ["*"]
    options.notdef_outline = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=charset())
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(out)
    print(out.name, round(out.stat().st_size / 1024), "KiB")


def main(source, target):
    target.mkdir(parents=True, exist_ok=True)
    for weight, style in SANS.items():
        font = TTFont(source / "plex" / f"IBMPlexSansKR-{style}.ttf")
        rename(font, "Dowon Sans", style)
        write(font, target / f"dowon-sans-{weight}.woff2")
    serif = instancer.instantiateVariableFont(TTFont(source / "noto" / "NotoSerifKR[wght].ttf"), {"wght": 600})
    write(serif, target / "noto-serif-kr-600.woff2")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
