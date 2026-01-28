"""PDF 텍스트 및 레이아웃 추출 모듈."""

import fitz  # PyMuPDF


def extract_pages(pdf_path: str) -> list[dict]:
    """PDF에서 페이지별 텍스트 블록과 스타일 정보를 추출한다.

    Returns:
        각 페이지의 블록 정보 리스트. 블록에는 좌표, 텍스트, 폰트, 크기, 색상 포함.
    """
    doc = fitz.open(pdf_path)
    pages = []

    for page in doc:
        page_data = {
            "width": page.rect.width,
            "height": page.rect.height,
            "blocks": [],
            "images": [],
        }

        # 이미지 추출
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    base_image = doc.extract_image(xref)
                    page_data["images"].append({
                        "rect": img_rects[0],
                        "image_bytes": base_image["image"],
                        "ext": base_image["ext"],
                    })
            except Exception:
                pass

        # 텍스트 블록 추출 (dict 모드로 span 단위 정보 확보)
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in text_dict.get("blocks", []):
            if block["type"] != 0:  # 텍스트 블록만
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    page_data["blocks"].append({
                        "bbox": span["bbox"],  # (x0, y0, x1, y1)
                        "text": text,
                        "font": span["font"],
                        "size": span["size"],
                        "color": span["color"],
                        "origin": span["origin"],  # (x, y) baseline
                    })

        pages.append(page_data)

    doc.close()
    return pages
