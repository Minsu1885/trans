"""번역된 텍스트로 PDF를 재생성하는 모듈."""

import io
import os
import fitz  # PyMuPDF


# 한글 폰트 경로 후보
_KOREAN_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_BUNDLED_FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "NanumGothic.ttf")


def _find_korean_font() -> str | None:
    """시스템에서 한글 폰트를 찾는다."""
    if os.path.exists(_BUNDLED_FONT_PATH):
        return _BUNDLED_FONT_PATH
    for path in _KOREAN_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _download_font() -> str:
    """한글 폰트가 없으면 다운로드한다."""
    font_dir = os.path.join(os.path.dirname(__file__), "fonts")
    os.makedirs(font_dir, exist_ok=True)
    dest = os.path.join(font_dir, "NanumGothic.ttf")
    if os.path.exists(dest):
        return dest

    print("한글 폰트를 다운로드합니다...")
    import urllib.request
    url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    urllib.request.urlretrieve(url, dest)
    print(f"폰트 저장: {dest}")
    return dest


def generate_pdf(pages: list[dict], output_path: str, source_pdf_path: str) -> None:
    """번역된 데이터를 사용해 원본과 동일한 레이아웃의 PDF를 생성한다.

    원본 PDF 위에 흰색으로 텍스트 영역을 덮고 번역된 텍스트를 삽입하는 방식.
    이렇게 하면 이미지, 배경, 도형 등이 원본 그대로 유지된다.
    """
    font_path = _find_korean_font()
    if not font_path:
        font_path = _download_font()

    # 원본 PDF를 열어서 위에 덧쓰기
    doc = fitz.open(source_pdf_path)

    for page_idx, page_data in enumerate(pages):
        if page_idx >= len(doc):
            break
        page = doc[page_idx]

        for block in page_data["blocks"]:
            translated = block.get("translated", block["text"])
            if not translated:
                continue

            bbox = block["bbox"]
            x0, y0, x1, y1 = bbox
            font_size = block["size"]

            # 원본 텍스트 영역을 흰색으로 덮기
            cover_rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
            page.draw_rect(cover_rect, color=None, fill=(1, 1, 1))

            # 한글은 영어보다 넓으므로 폰트 크기 조정
            text_width = x1 - x0
            estimated_kr_width = len(translated) * font_size * 0.55
            if estimated_kr_width > text_width and text_width > 0:
                scale = text_width / estimated_kr_width
                adjusted_size = max(font_size * scale, 5)
            else:
                adjusted_size = font_size

            # 색상 변환 (int -> RGB tuple)
            color_int = block.get("color", 0)
            r = ((color_int >> 16) & 0xFF) / 255.0
            g = ((color_int >> 8) & 0xFF) / 255.0
            b = (color_int & 0xFF) / 255.0

            # 번역 텍스트 삽입
            text_rect = fitz.Rect(x0, y0, x1, y1 + adjusted_size * 0.5)
            page.insert_textbox(
                text_rect,
                translated,
                fontsize=adjusted_size,
                fontfile=font_path,
                fontname="korean",
                color=(r, g, b),
                align=fitz.TEXT_ALIGN_LEFT,
            )

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"번역 PDF 저장 완료: {output_path}")
