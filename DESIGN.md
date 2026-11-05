---
version: alpha
name: 도원결의
description: 여행 전에 같은 가상 상황에 각자 답하고 추천 협약서를 받는 모바일 웹의 UI 디자인 시스템
colors:
  primary: "#3E3833"
  primary-pressed: "#57504A"
  on-primary: "#F7F5F1"
  secondary: "#5E5750"
  tertiary: "#8A5B33"
  tertiary-mark: "#9A6F42"
  neutral: "#F7F5F1"
  surface: "#EFECE7"
  surface-pressed: "#E4DED5"
  paper: "#FAF8F5"
  muted: "#6E675F"
  outline: "#8C847C"
  outline-variant: "#D9CFC4"
  hairline: "#3E38331A"
  stamp: "#B3362C"
  error: "#9E2F26"
  blossom: "#EBB8B1"
  bark: "#8A6A4A"
typography:
  display-pact:
    fontFamily: Noto Serif KR
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0.02em
  headline-lg:
    fontFamily: Noto Serif KR
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.35
  headline-md:
    fontFamily: IBM Plex Sans KR
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.45
  clause-number:
    fontFamily: Noto Serif KR
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.5
  scene-lead:
    fontFamily: IBM Plex Sans KR
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.5
  scene-detail:
    fontFamily: IBM Plex Sans KR
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.5
  body-md:
    fontFamily: IBM Plex Sans KR
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.65
  body-sm:
    fontFamily: IBM Plex Sans KR
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
  label-lg:
    fontFamily: IBM Plex Sans KR
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.25
  label-md:
    fontFamily: IBM Plex Sans KR
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
  label-sm:
    fontFamily: IBM Plex Sans KR
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
  numeral:
    fontFamily: IBM Plex Sans KR
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    fontFeature: '"tnum" 1'
  caption:
    fontFamily: IBM Plex Sans KR
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
  stamp:
    fontFamily: Noto Serif KR
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.15
  wordmark:
    fontFamily: Noto Serif KR
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.25
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
  2xl: 24px
  3xl: 32px
  4xl: 48px
  gutter: 20px
  content-max: 480px
  touch-min: 48px
rounded:
  paper: 4px
  sm: 6px
  md: 10px
  lg: 14px
  xl: 20px
  full: 9999px
motion:
  easing: "cubic-bezier(0.2, 0, 0, 1)"
  feedback: 150ms
  enter: 320ms
  paper: 1100ms
  clause: 640ms
  stamp: 420ms
  stagger: 220ms
  branch: 500ms
  petal-fall: 12s
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    height: 52px
    padding: 16px
  button-primary-pressed:
    backgroundColor: "{colors.primary-pressed}"
    textColor: "{colors.on-primary}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    height: 52px
    padding: 16px
  button-secondary-pressed:
    backgroundColor: "{colors.surface-pressed}"
    textColor: "{colors.primary}"
  button-secondary-on-surface:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    height: 52px
    padding: 16px
  button-secondary-on-surface-pressed:
    backgroundColor: "{colors.surface-pressed}"
    textColor: "{colors.primary}"
  button-text:
    textColor: "{colors.tertiary}"
    typography: "{typography.label-md}"
    height: 48px
    padding: 12px
  option-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 16px
    height: 56px
  option-card-selected:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
  scene-lead:
    textColor: "{colors.primary}"
    typography: "{typography.scene-lead}"
  scene-detail:
    textColor: "{colors.secondary}"
    typography: "{typography.scene-detail}"
    padding: 32px
  input-text:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
    height: 48px
  input-memo:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
    height: 96px
  progress-track:
    backgroundColor: "{colors.surface-pressed}"
    rounded: "{rounded.full}"
    height: 4px
  progress-fill:
    backgroundColor: "{colors.tertiary-mark}"
    rounded: "{rounded.full}"
    height: 4px
  notice-privacy:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  notice-duplicate-name:
    textColor: "{colors.error}"
    typography: "{typography.body-sm}"
  message-error:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.error}"
    typography: "{typography.body-sm}"
  count-label:
    textColor: "{colors.muted}"
    typography: "{typography.numeral}"
  tab-result:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    height: 40px
  tab-result-selected:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
  pact-paper:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.paper}"
    padding: 24px
  wordmark:
    textColor: "{colors.primary}"
    typography: "{typography.wordmark}"
  pact-title:
    textColor: "{colors.primary}"
    typography: "{typography.display-pact}"
  pact-clause-number:
    textColor: "{colors.tertiary}"
    typography: "{typography.clause-number}"
  pact-meta:
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
  host-edit-label:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.tertiary}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 4px
  stamp:
    textColor: "{colors.stamp}"
    typography: "{typography.stamp}"
    rounded: "{rounded.full}"
    size: 88px
  pact-branch:
    textColor: "{colors.bark}"
    size: 172px
  petal-drift:
    backgroundColor: "{colors.blossom}"
    size: 14px
  unresolved-panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 20px
  divider:
    backgroundColor: "{colors.hairline}"
    height: 1px
  input-outline:
    backgroundColor: "{colors.outline}"
    height: 1px
  card-outline:
    backgroundColor: "{colors.outline-variant}"
    height: 1px
---
# 도원결의 UI 디자인

> 상태: 2026-11-04 작성.
> 근거 자료: [README 배너](docs/assets/readme-banner.png) · [1차 중간발표](docs/presentations/midterm-1/도원결의_중간발표_1차.pdf) · [9/23 회의 협약서 목업](docs/meetings/assets/2026-09-23-pact.png)

이 문서는 화면이 **어떻게 보이는지**만 정한다. 화면에 **무엇을, 언제** 보여 줄지, 문구, 권한, 공개 범위, 상태 판정은 [SPEC](docs/SPEC.md)이 정하며, 이 문서는 그 항목을 `AC3`처럼 식별자로만 가리키고 내용을 옮겨 적지 않는다. 두 문서가 어긋나면 SPEC과 [AGENTS](AGENTS.md)를 따르고 이 문서를 고친다.

형식은 Google Labs의 [DESIGN.md 형식(alpha)](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md)을 따른다. 맨 위 YAML 토큰이 정확한 값이고, 본문은 그 값을 언제·왜 쓰는지 설명한다. 본문의 `{colors.paper}` 같은 표기는 토큰 참조다.

## Overview

도원결의는 여행을 떠나기 전, 동행이 같은 가상 상황에 각자 답하면 서로의 바람과 한계를 반영한 **추천 협약서 한 장**을 돌려주는 모바일 웹이다.

화면은 **떠나기 전날 밤 식탁에 펼쳐 둔 서약서 한 장**을 닮는다. 미색 종이, 먹색 글자, 놋쇠빛 밑줄, 마지막에 찍는 붉은 인주 도장이 이 세계의 재료다. 배너와 발표자료가 이미 이 재료로 만들어져 있으므로 새 스타일을 만들지 않고 그 결을 앱 화면으로 옮긴다. 서비스 이름의 도원(복숭아 동산)에서 온 복숭아꽃은 협약서가 발급되는 순간에만 피운다.

- **성격**: 다정하고, 정확하고, 조금 장난스럽다. 묻고 안내하는 화면은 조용하고 친절하게, 결과의 제목·도장·짧은 문구에서만 재미를 준다([9/23 회의](docs/meetings/2026-09-23.md#결과-화면과-공유)).
- **풍부한 한 순간**: 결과 화면의 협약서 종이, 도장, 복숭아나무 가지. 색·질감·연출은 여기에 모으고, 나머지 화면은 같은 중립색 위에서 읽고 고르는 일에만 집중한다.
- **시그니처**: 인주 도장. 협약서 종이에만 찍으며 로고·버튼·로딩·빈 화면에는 쓰지 않는다.
- **사용 환경**: 아이폰 Safari와 안드로이드 Chrome의 세로 화면(AC14). 한 손 엄지로 조작하고, 답하는 동안 문장을 끝까지 읽을 수 있어야 한다.

## Colors

먹 한 가지와 종이 세 단계, 놋쇠 강조 한 가지, 인주 한 가지로 이루어진다. 색상값은 발표자료의 실제 사용 색에서 가져왔고, 작은 글자에 쓰기에 대비가 모자란 두 색만 같은 계열에서 어둡게 조정했다.

- **먹** {colors.primary}: 본문·제목·주 버튼 배경. 순수한 검정을 쓰지 않는다.
- **먹 눌림** {colors.primary-pressed}: 주 버튼을 누른 상태.
- **종이 위 글자** {colors.on-primary}: 먹 배경 위 글자.
- **보조 글자** {colors.secondary}: 설명문, 안내 카드 본문.
- **흐린 글자** {colors.muted}: 메타 정보, 개수, 날짜. 발표자료의 `#8C847C`는 작은 글자에서 대비가 3.38:1이라 이 색으로 바꿨다.
- **놋쇠** {colors.tertiary}: 강조가 필요한 **글자**(조항 번호, 텍스트 버튼, ‘방장 수정’ 표시). 발표자료의 `#9A6F42`는 바탕 위 작은 글자에서 4.08:1이라 한 단계 어둡게 했다.
- **놋쇠 표시** {colors.tertiary-mark}: 글자가 아닌 표시(선택한 라디오 점, 진행 막대, 제목 아래 짧은 밑줄, 포커스 링).
- **바탕** {colors.neutral}: 모든 화면의 기본 배경.
- **표면** {colors.surface}, **표면 눌림** {colors.surface-pressed}: 카드·선택지·보조 버튼. 결과 화면에서는 이 색을 배경으로 써서 종이가 한 단계 떠 보이게 한다.
- **종이** {colors.paper}: 협약서 종이, 입력란, 선택한 선택지.
- **윤곽선** {colors.outline}: 입력란 테두리처럼 경계가 조작 단서인 곳. 바탕 대비 3.38:1로 WCAG의 비텍스트 대비 3:1을 넘는다.
- **옅은 윤곽선** {colors.outline-variant}, **헤어라인** {colors.hairline}: 장식이 아닌 구분선. 조작 단서로 쓰지 않는다.
- **인주** {colors.stamp}: 도장 전용. 다른 곳에 쓰지 않는다.
- **복숭아꽃** {colors.blossom}, **가지** {colors.bark}: 협약서 화면의 가지와 꽃잎 전용. 버튼·글자·선 같은 크롬에는 쓰지 않는다.
- **오류** {colors.error}: 오류 문구와 같은 이름 안내(AC16). 인주와 같은 붉은 계열이지만 더 어두워 역할이 섞이지 않는다.

대비(WCAG 상대 휘도 공식으로 계산, 바탕 {colors.neutral} 기준): 먹 10.61:1, 보조 글자 6.53:1, 흐린 글자 5.12:1, 놋쇠 5.32:1, 오류 6.68:1, 주 버튼 글자 10.61:1. 표면 {colors.surface} 위에서는 흐린 글자 4.73:1, 놋쇠 4.92:1로 모두 4.5:1 이상이다.

배너의 큰 원(`#C5A783`)과 둥근 배경면은 마케팅 그림의 구성 요소다. 앱 화면 배경에는 옮기지 않는다. 9/23 목업의 노란 파피루스 바탕(`#F2E6C8`)은 이후 배너·발표자료의 미색으로 바뀌었으므로 이 문서는 미색을 따른다.

## Typography

본문과 조작은 **IBM Plex Sans KR**, 문서의 목소리는 **Noto Serif KR**이 맡는다. 두 서체 모두 발표자료에서 본문과 제목에 쓴 서체다.

- **Noto Serif KR**은 워드마크 {typography.wordmark}, 화면 제목 {typography.headline-lg}, 협약서 제목 {typography.display-pact}, 조항 번호 {typography.clause-number}, 도장 {typography.stamp}에만 쓴다. 버튼·라벨·입력란에는 쓰지 않는다.
- **워드마크** ‘도원결의’는 앱 머리와 협약서 머리 모두 Noto Serif KR 600이다. 발표자료 표지와 같은 서체이고, 협약서 제목·도장과 한 목소리로 읽힌다. 배너의 굵은 산세리프 표기는 README 표지에만 쓴다.
- **IBM Plex Sans KR**은 나머지 전부다. 문항의 장면은 첫 줄을 {typography.scene-lead}, 나머지 줄을 {typography.scene-detail}로 두고, 질문은 {typography.headline-md}로 장면보다 앞에 읽히게 한다.
- 굵기는 400·500·600만 쓴다. 발표자료는 굵은 제목을 많이 쓰지만 작은 화면에서는 크기와 색으로 위계를 만든다.
- 개수·회차·날짜처럼 바뀌는 숫자는 {typography.numeral}(고정폭 숫자)로 쓴다. 예: `제출 3 / 4`, `2 / 8`.
- 한국어 줄바꿈은 `word-break: keep-all`로 어절 단위로 끊고, 긴 별명은 `overflow-wrap: anywhere`로 넘치지 않게 한다.
- 작은 글자에 음수 자간을 주지 않는다. 자간을 넓히는 것은 협약서 제목 하나뿐이다.
- 발표자료 표지의 ‘도 원 결 의’처럼 글자를 띄운 표기, 배너의 영문 대문자 머리말(`TRAVEL COMPANION PACT`)은 앱 화면에 쓰지 않는다.
- 기울임체로 강조하지 않는다.

## Layout

모바일 세로 화면 하나를 기준으로 한 단 레이아웃을 쓴다. 데스크톱에서 열어도 본문 폭은 {spacing.content-max}에서 멈추고 가운데 놓인다. 이 서비스는 모바일 웹이므로 좁은 단이 정상이다.

- 모든 간격은 4px 격자다. 토큰은 {spacing.xs}부터 {spacing.4xl}까지이며, 토큰 사이 값이 필요하면 4의 배수를 쓴다.
- 화면 좌우 여백은 {spacing.gutter}, 카드 안쪽은 {spacing.lg}~{spacing.xl}, 협약서 종이 안쪽은 {spacing.2xl}이다.
- 묶음 안은 좁게, 묶음 사이는 넓게 둔다. 질문과 선택지 목록 사이 {spacing.xl}, 선택지끼리 {spacing.sm}, 선택지 목록과 메모 사이 {spacing.2xl}.
- 화면당 주 동작은 하나이며 화면 아래에 고정한다. 고정 영역은 `env(safe-area-inset-bottom)`만큼 아래 여백을 더해 홈 표시줄과 겹치지 않게 한다. 보조 동작은 주 동작 위에 하나까지 둔다. 답 확인 화면은 예외로 고정 영역에 주 버튼만 둔다. 고정 영역이 커지면 마지막 문항을 가리기 때문이다.
- 손가락으로 누르는 모든 대상은 {spacing.touch-min} 이상이다. 아이콘만 있는 버튼도 보이는 크기와 상관없이 누르는 영역을 이만큼 둔다.
- 응답 화면은 문항 하나를 한 화면에 담는다. 위에서부터 진행 표시, 장면, 질문, 선택지, 메모, 아래 고정 버튼 순이다.
- 필수 입력과 선택 입력이 섞인 폼은 선택 입력을 접힌 영역에 묶는다. 폼의 묶음 사이는 {spacing.3xl}이다. 방 만들기는 단계별 입력이라 선택 입력을 마지막 단계에 따로 둔다.
- 글자 크기를 200%로 키워도(Apple HIG 권고) 가로 스크롤 없이 세로로 늘어나야 한다. 높이를 고정한 카드는 `min-height`로 둔다.

## Elevation &amp; Depth

평면에서 **면의 단계와 헤어라인**으로 위계를 만든다. 바탕 {colors.neutral} → 표면 {colors.surface} → 종이 {colors.paper}가 한 단계씩 앞으로 나온다.

그림자는 협약서 종이 하나에만 준다. 배너의 종이처럼 아래로 부드럽게 떨어지는 무채색 그림자다: `0 1px 2px rgb(62 56 51 / 6%), 0 12px 32px rgb(62 56 51 / 10%)`. 카드·버튼·선택지에는 그림자를 주지 않는다. 색 있는 그림자와 빛 번짐은 쓰지 않는다.

## Shapes

조작 요소는 부드럽게, 문서는 반듯하게 다룬다.

- 버튼·입력란 {rounded.md}, 선택지·안내 카드 {rounded.lg}, 아래에서 올라오는 시트 {rounded.xl}.
- 협약서 종이는 {rounded.paper}로 거의 직각이다. 실제 종이처럼 보여야 하기 때문이다. 종이 안쪽 테두리는 8px 들어간 위치에 놋쇠 표시색 30% 불투명도의 1px 선을 둔다(9/23 목업의 서류 테두리).
- 안쪽 모서리는 바깥 모서리에서 안쪽 여백을 뺀 값이며 4px보다 작게 하지 않는다.
- 완전한 원 {rounded.full}은 도장, 라디오 점, 진행 막대에만 쓴다. 버튼을 알약 모양으로 만들지 않는다.
- 제목 아래 짧은 밑줄(폭 40px, 높이 2px, {colors.tertiary-mark})은 배너·발표자료의 표시다. 앱에서는 협약서 제목 아래에만 둔다.

## Iconography

발표자료가 쓰는 선 아이콘과 같은 계열인 [Lucide](https://lucide.dev)를 쓴다.

- 크기 20px, 선 굵기 1.5 한 가지로 통일한다.
- 아이콘 색은 옆 글자의 색을 따른다. 아이콘에 별도 색을 입히지 않는다.
- 아이콘은 뜻을 더할 때만 쓴다. 예: 공개 안내의 자물쇠(`lock`), 오류의 경고(`circle-alert`), 링크 복사(`copy`), 이미지 저장(`download`), 방장 수정(`pencil-line`).
- 이모지는 화면 어디에도 쓰지 않는다.
- 도장은 아이콘이 아니라 그림이다. 아이콘 세트로 대체하지 않는다.

## Motion

움직임은 짧고 기계적이다. 화면 전환과 피드백은 {motion.easing} 곡선 하나만 쓴다.

- 누름·선택·토글: {motion.feedback}. 색과 면만 바뀌고 크기는 누를 때 98%로 줄었다 돌아오는 정도까지만.
- 시트·안내 카드 등장: {motion.enter}, 아래에서 8px 떠오르며 나타난다.
- **협약서 발급 연출**: 종이가 {motion.paper} 동안 위에서 펼쳐지고(높이가 아닌 `clip-path`·`transform`으로), 조항이 {motion.clause} 동안 {motion.stagger} 간격으로 이어 나타난 뒤 도장이 {motion.stamp} 동안 108%에서 100%로 줄며 불투명도가 0에서 올라와 종이에 찍힌다. 찍히는 동안에도 그림자는 없다. 도장 애니메이션이 시작하는 순간 복숭아나무 가지가 함께 뻗는다(`pact-branch`). 결과를 처음 열 때 한 번만 재생하고 다시 열면 바로 완성 상태를 보여 준다. 연출은 9/23 회의의 ‘종이가 펼쳐진 뒤 마지막에 도장’ 방향을 따른다.
- 협약서 생성을 기다리는 동안에는 실제로 진행 중인 작업이므로 얇은 진행 막대가 천천히 흐르는 것을 허용한다. 결과 화면의 흩날리는 꽃잎(`petal-drift`)도 예외로 허용한다. 그 밖에 반복하는 움직임(깜빡임, 숨쉬기, 반짝임)은 쓰지 않는다.
- `prefers-reduced-motion: reduce`이면 모든 시간을 0으로 두고 완성 상태를 바로 보여 준다. 흩날리는 꽃잎은 보여 주지 않는다.
- `transition: all`을 쓰지 않는다. `color`, `background-color`, `border-color`, `opacity`, `transform`만 지정해 전환한다.

## Sound

효과음은 협약서 발급 연출에만 쓴다. 종이가 펼쳐질 때, 조항이 놓일 때, 도장이 찍힐 때, 가지가 뻗고 꽃이 필 때 짧고 작게 난다.

- 기본값은 꺼짐이다. 사용자가 연출을 직접 시작했을 때만 재생하고 자동 재생하지 않는다.
- 기기의 무음·음소거 설정을 따른다.
- 소리가 없어도 연출의 의미는 같아야 한다. 소리로만 알리는 정보는 없다.

## Components

토큰에 없는 테두리 값은 이 절의 설명을 따른다. 상태 이름은 토큰의 `-pressed`, `-selected` 접미사와 맞춘다.

### 버튼

- **주 버튼** `button-primary`: 화면당 하나. 너비는 본문 폭 전체, 높이 52px. 비활성 상태는 {colors.surface-pressed} 바탕에 {colors.muted} 글자다. 비활성 사유를 글로 둘 때는 버튼 바로 위에 {typography.body-sm}로 놓는다. 답 확인 화면에서는 비활성 사유와 오류를 본문 끝에 둔다.
- **보조 버튼** `button-secondary`: 주 버튼과 같은 크기, 표면 바탕. 주 동작 위에 두는 선택 동작.
- **표면 위 보조 버튼** `button-secondary-on-surface`: 카드처럼 표면 위에 놓는 보조 버튼. 종이 바탕에 {colors.outline} 1px 테두리를 둔다.
- **텍스트 버튼** `button-text`: 놋쇠 글자, 밑줄 없음. 본문 흐름 안의 가벼운 동작.
- 모든 버튼에 키보드 포커스 링을 둔다: {colors.tertiary-mark} 2px, 2px 바깥 간격.

### 선택지 `option-card`

- 세로 목록, 한 줄에 하나. 최소 높이 56px, 글이 길면 늘어난다.
- 왼쪽에 20px 라디오 원, 오른쪽에 선택지 문구(`ScenarioOption.label`)를 둔다.
- 선택하면 바탕이 {colors.paper}로 바뀌고 {colors.tertiary-mark} 2px 테두리와 채워진 라디오 점이 생긴다. 색만으로 선택을 표시하지 않으며 `role="radio"`와 `aria-checked`를 함께 둔다.

### 장면 개요 `scene-lead`, `scene-detail`

- 장면의 첫 줄은 점 없이 `scene-lead`로 둔다. 둘째 줄부터는 `scene-detail`로 {spacing.3xl} 들여 쓰고, 줄 앞에 {colors.outline} 4px 점을 둔다.
- 첫 줄과 조건 줄 사이는 {spacing.sm}, 조건 줄끼리는 {spacing.xs}다. 장면 묶음과 질문 사이는 {spacing.2xl}이다.
- 한 줄이 길어 줄바꿈되면 다음 줄은 점이 아니라 글자 시작 위치에 맞춘다.

### 입력란 `input-text`, `input-memo`

- 종이 바탕에 {colors.outline} 1px 테두리, 포커스 시 {colors.primary} 2px 테두리.
- 글자 크기는 16px 이상이다. iOS Safari는 이보다 작은 입력란에 포커스하면 화면을 확대한다.
- 라벨은 입력란 위에 항상 보이게 둔다. 자리표시 글자를 라벨 대신 쓰지 않는다.
- 입력란 아래 보조 글자는 {colors.muted} {typography.body-sm}이고, 글자 수를 보여 줄 때는 오른쪽에 {typography.numeral}로 둔다.
- 입력 오류는 해당 입력란 바로 아래에 경고 아이콘과 {colors.error} {typography.body-sm} 글자로 둔다. 입력란 테두리도 {colors.error}로 바꾼다.

### 진행 표시 `progress-track`, `progress-fill`

- 응답 화면 맨 위, 4px 막대와 오른쪽 `3 / 8` 숫자. 막대는 문항을 마칠 때마다 {motion.feedback}로 늘어난다.

### 안내와 오류

- **공개 안내** `notice-privacy`: 자물쇠 아이콘과 안내문을 담은 카드. 안내가 표시되는 화면에서 주 버튼 바로 위에 둔다(AC3). 답 확인 화면에서는 본문 끝, 마지막 문항 아래에 둔다.
- **같은 이름 안내** `notice-duplicate-name`: 이름 선택 목록 바로 아래 {colors.error} 글자와 경고 아이콘(AC16).
- **오류** `message-error`: 경고 아이콘 뒤에 글자를 두고, 재시도 버튼이 있으면 바로 아래 둔다. 색이나 아이콘만으로 오류를 표시하지 않는다(AC14).
- **개수 표시** `count-label`: 흐린 글자와 고정폭 숫자.

### 결과 전환 `tab-result`

- 결과가 두 개일 때(AC17) 협약서 위에 두는 두 칸짜리 분할 버튼. 선택한 칸은 종이 바탕에 먹 글자.

### 협약서 종이 `pact-paper` (풍부한 한 순간)

결과 화면의 주인공이다. 화면과 저장 이미지가 같은 모양이 되도록 하나의 컴포넌트로 만든다(AC13). 저장 이미지는 종이 폭 360px를 3배로 그려 1080px 폭으로 만든다. 종이에 담을 항목은 SPEC이 정하고, 이 절은 각 자리의 모양만 정한다. 위에서부터:

1. **머리**: 왼쪽에 워드마크 `wordmark`.
2. **제목**: 가운데 `pact-title`, 아래 짧은 놋쇠 밑줄.
3. **여행 정보**: 항목을 가운데점(·)으로 잇는 한 줄 `pact-meta`.
4. **조항**: `제1조`부터 번호를 붙인다 `pact-clause-number`. 번호 아래 조항 문장, 그 아래 적용 대상 이름을 둔다. 제안 조건(`proposed_conditions`)은 한 단계 들여 쓰고 앞에 {colors.tertiary} {typography.label-sm} 라벨을 둬 조항 문장과 구분한다(AC7).
5. **조건부 대안**: 조항 아래 헤어라인으로 구분한 묶음. 대안 문장 아래 필요한 변경을 한 단계 들여 쓴다. 표시하는 필드는 AC3·AC8을 따른다.
6. **미해결 조건**: 조건부 대안과 같은 모양의 묶음.
7. **바닥글**: 헤어라인 아래 {typography.caption} 글자 영역. 추천안 안내 문장만 {typography.body-sm}, {colors.secondary}로 둔다. 오른쪽 아래에 바닥글 글자와 테두리선에 걸쳐 찍힌 도장.

### 방장 수정 표시 `host-edit-label`

- 수정한 조항의 번호 오른쪽에 두는 작은 라벨(AC12).
- 편집 모드에서 수정할 수 있는 문구는 `input-memo`와 같은 모양의 입력란으로 바뀌고, 나머지는 종이 위 모양 그대로 둔다.

### 도장 `stamp` (시그니처)

- 지름 88px 원, {colors.stamp} 3px 선, 안에 두 줄 글자({typography.stamp}). -12° 기울인다.
- 종이 위에 따로 놓인 스티커가 아니라 종이에 찍힌 인주로 보이게 한다. `mix-blend-mode: multiply`로 종이 결과 아래 글자·선이 도장 사이로 비치게 하고, 불투명도는 90% 안팎으로 둔다.
- 인주가 고르게 묻지 않은 것처럼 선과 글자의 가장자리는 아주 조금 번지고, 옅은 곳이 드물게 약하게 있다. 얼룩이 눈에 띄면 과한 것이다. 질감은 SVG 노이즈 필터 하나로 만들고 도장 밖에는 쓰지 않는다.
- 그림자, 배경색, 테두리 상자를 주지 않는다. 떠 있는 것처럼 보이는 요소는 모두 뺀다.
- 위치는 종이 바닥글 오른쪽이다. 바닥글의 헤어라인, 종이 안쪽 테두리선, 바닥글 글자 끝에 걸쳐 찍는다. 조항 문장 위에는 찍지 않는다.
- 저장 이미지에서도 혼합 모드와 질감이 화면과 같게 그려져야 한다(AC13).
- 도장은 협약서 종이의 일부다. 종이가 표시되는 결과에는 `proposed`·`conditional_only` 구분 없이 찍고, 종이가 없는 화면에는 두지 않는다.
- 도장 애니메이션이 시작하는 순간 `pact-branch`도 함께 시작한다.

### 복숭아나무 가지 `pact-branch`

- 종이의 오른쪽 위와 왼쪽 아래 구석, 글자 뒤에 둔다. 왼쪽 아래 가지는 오른쪽 위 가지를 180° 돌린 모양이다. 가로 크기는 172px다.
- 가지는 {colors.bark} 불투명도 30% 안팎이며, 굵은 줄기에서 잔가지로 갈수록 가늘어진다. 꽃은 {colors.blossom} 계열 불투명도 45% 안팎이며, 활짝 핀 꽃·반쯤 핀 꽃·꽃봉오리를 섞는다.
- 도장 애니메이션과 같은 순간 시작해 {motion.branch} 안에 가지가 뻗고, 줄기 쪽부터 가지 끝 쪽으로 꽃이 차례로 핀다.
- 글자는 항상 가지 위에 그린다. 저장 이미지에는 다 핀 상태로 들어간다(AC13).

### 흩날리는 꽃잎 `petal-drift`

- 결과 화면에서만 쓴다. 화면 양옆 가장자리에서 생겨 아래로 내려오다 화면 높이의 절반쯤에서 흐려지며 사라진다. 가운데 본문 영역은 지나지 않는다.
- 꽃잎은 5~6장, 한 장이 내려오는 데 {motion.petal-fall} 안팎이 걸리며, 불투명도는 50~80%다.
- 저장 이미지에는 넣지 않는다.

### 미해결 안내 `unresolved-panel`

- 미해결 결과(AC9)를 담는 카드. 협약서 종이가 아니므로 도장이 없다.
- 첫 줄에 유머 문구를 {typography.headline-md}로 두고, 바로 아래 같은 카드 안에 설명 문장과 막힌 조건 목록을 {typography.body-md}로 붙인다. 세 요소의 문구와 표시 조건은 SPEC [상태별 처리](docs/SPEC.md#상태별-처리)를 따른다.
- 유머 문구는 먹색이다. 오류처럼 보이게 붉은색을 쓰지 않는다.

## 글자 배치

문구의 내용과 문체는 이 문서에서 다루지 않는다. 이 절은 정해진 글자를 화면에 놓는 방식만 정한다. 줄바꿈과 자간은 [Typography](#typography)를 따른다.

- 본문·안내·조항은 왼쪽 정렬이다. 가운데 정렬은 협약서 제목, 여행 정보 줄, 도장 안 글자, 버튼 글자에만 쓴다.
- 글자를 말줄임표(…)로 자르지 않는다. 길면 줄을 바꾸고 담은 상자가 세로로 늘어난다.
- 버튼 글자는 한 줄을 기본으로 하되, 글자 확대로 넘치면 두 줄로 바꾸고 버튼 높이도 따라 늘린다.
- 개수 표시는 무엇을 세는지 나타내는 글자 뒤에 숫자를 두고, 숫자에만 {typography.numeral}을 쓴다.
- 문장 안의 이름, ‘당신’, 숫자를 굵기나 색으로 따로 강조하지 않는다.

## 접근성

SPEC AC14가 요구하는 ‘읽고 조작할 수 있음’을 화면 단위로 옮긴 기준이다.

- 누르는 대상 {spacing.touch-min} 이상. Android의 48dp 권고를 기준으로 했으며 Apple HIG의 44×44pt, WCAG 2.2의 24×24px보다 크다.
- 본문 글자 대비 4.5:1 이상, 입력란 테두리·포커스 링 같은 비텍스트 요소 3:1 이상. 본문 16px, 가장 작은 글자는 {typography.caption}의 12px다.
- 모든 입력에 보이는 라벨이 있고, 선택지는 라디오 그룹으로 읽힌다. 문서 언어는 `lang="ko"`.
- 화면 위아래 고정 영역은 `env(safe-area-inset-*)`를 더한다.

## Do's and Don'ts

- **Do** 협약서 종이를 실제 서류처럼 다룬다. 종이에 그라데이션, 유리 효과, 빛 번짐을 넣지 않는다.
- **Do** 인주는 도장에만 둔다. 다른 곳에 드물게라도 쓰면 도장이 특별하지 않게 된다.
- **Do** 응답 화면에서는 장면의 모든 줄을 펼쳐 보여 준다. 접거나 일부 줄만 보여 주지 않는다.
- **Don't** 시안·목업의 예시 데이터에 AC3의 비공개 항목을 넣지 않는다.
- **Don't** 도장을 협약서 종이 밖(로딩, 빈 화면, 로고, 안내 카드)에 쓰지 않는다.
- **Don't** 복숭아꽃과 가지를 협약서 화면 밖에 쓰지 않는다.
- **Don't** 흩날리는 꽃잎이 화면 가운데 본문 영역을 지나게 하지 않는다.
- **Don't** 가지가 조항 글자를 가려 읽기 어렵게 만들지 않는다.
- **Don't** 동행의 답을 점수, 궁합 막대, 성향 차트로 시각화하지 않는다(AC7).
- **Don't** 배너·발표자료의 장식(큰 원, 둥근 배경면, 영문 대문자 머리말)을 앱 화면에 가져오지 않는다. 그 자료는 표지용이다.
- **Don't** 화면마다 다른 강조색을 만들지 않는다. 강조는 놋쇠 하나다.
- **Don't** 화면에 작은거나 연한 글씨로 불필요한 정보나 사족을 제시하지 않는다.

## 참고 자료

- 형식: [DESIGN.md 형식 명세(alpha)](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md), [DESIGN.md 철학](https://github.com/google-labs-code/design.md/blob/main/PHILOSOPHY.md). 토큰 검사는 `npx @google/design.md lint DESIGN.md`.
- 접근성: [Apple HIG Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)(최소 조작 크기 44×44pt, 17pt 이하 글자 대비 4.5:1, 글자 200% 확대), [Android 접근성 가이드](https://developer.android.com/guide/topics/ui/accessibility/apps)(터치 대상 48dp), [WCAG 2.2 SC 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)(24×24px), [MDN `env()`](https://developer.mozilla.org/en-US/docs/Web/CSS/env)(safe area).
- 방향 설정·점검 기준: unslop 스킬(Damir Sokolovsky, [@heydamir](https://x.com/heydamir), CC BY 4.0)의 방향 다섯 줄과 9단계 점검을 이 제품에 맞게 적용했다.
- 내부 자료: 색상·서체 값은 1차 중간발표 `.pptx`의 슬라이드 XML에서, 화면 연출은 [9/23 회의](docs/meetings/2026-09-23.md#결과-화면과-공유)에서 가져왔다.
