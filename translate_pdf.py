"""영문 PDF → 한글 PDF 번역기 (단일 파일 버전)"""

import argparse
import io
import os
import sys
import urllib.request

import fitz  # PyMuPDF
import google.generativeai as genai
from tqdm import tqdm


# ── 1. PDF 텍스트 추출 ──────────────────────────────────────────────

def extract_pages(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        page_data = {"width": page.rect.width, "height": page.rect.height, "blocks": []}
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in text_dict.get("blocks", []):
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    page_data["blocks"].append({
                        "bbox": span["bbox"],
                        "text": text,
                        "font": span["font"],
                        "size": span["size"],
                        "color": span["color"],
                        "origin": span["origin"],
                    })
        pages.append(page_data)
    doc.close()
    return pages


# ── 2. Gemini 번역 ──────────────────────────────────────────────────

def _translate_batch(model, texts, source, target):
    numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts))
    prompt = (
        f"You are a professional translator. Translate the following {source} texts to {target}. "
        f"Each line starts with [number]. Return ONLY the translations, one per line, "
        f"keeping the same [number] prefix. Do not add explanations.\n\n"
        f"{numbered}"
    )
    response = model.generate_content(prompt)
    result_text = response.text.strip()
    results = {}
    for line in result_text.split("\n"):
        line = line.strip()
        if line.startswith("["):
            bracket_end = line.find("]")
            if bracket_end != -1:
                try:
                    idx = int(line[1:bracket_end])
                    results[idx] = line[bracket_end + 1:].strip()
                except ValueError:
                    pass
    return [results.get(i, texts[i]) for i in range(len(texts))]


def translate_pages(pages, source, target, api_key, model_name):
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(model_name)

    all_texts = []
    index_map = []
    for pi, page in enumerate(pages):
        for bi, block in enumerate(page["blocks"]):
            all_texts.append(block["text"])
            index_map.append((pi, bi))

    print(f"번역할 텍스트 블록: {len(all_texts)}개")

    BATCH_SIZE = 50
    translated = []
    for start in tqdm(range(0, len(all_texts), BATCH_SIZE), desc="번역 중"):
        batch = all_texts[start:start + BATCH_SIZE]
        try:
            result = _translate_batch(gemini_model, batch, source, target)
            translated.extend(result)
        except Exception as e:
            print(f"\n배치 번역 실패, 개별 번역 시도: {e}")
            for text in batch:
                try:
                    r = _translate_batch(gemini_model, [text], source, target)
                    translated.extend(r)
                except Exception:
                    translated.append(text)

    for idx, (pi, bi) in enumerate(index_map):
        if idx < len(translated):
            pages[pi]["blocks"][bi]["translated"] = translated[idx].strip()
        else:
            pages[pi]["blocks"][bi]["translated"] = pages[pi]["blocks"][bi]["text"]
    return pages


# ── 3. 번역 PDF 생성 ────────────────────────────────────────────────

_FONT_CANDIDATES = [
    "C:\\Windows\\Fonts\\malgun.ttf",      # Windows 맑은고딕
    "C:\\Windows\\Fonts\\gulim.ttc",        # Windows 굴림
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


def _find_korean_font():
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    # 없으면 다운로드
    font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    os.makedirs(font_dir, exist_ok=True)
    dest = os.path.join(font_dir, "NanumGothic.ttf")
    if os.path.exists(dest):
        return dest
    print("한글 폰트를 다운로드합니다...")
    url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    urllib.request.urlretrieve(url, dest)
    print(f"폰트 저장: {dest}")
    return dest


def generate_pdf(pages, output_path, source_pdf_path):
    font_path = _find_korean_font()
    doc = fitz.open(source_pdf_path)

    for page_idx, page_data in enumerate(pages):
        if page_idx >= len(doc):
            break
        page = doc[page_idx]

        for block in page_data["blocks"]:
            translated = block.get("translated", block["text"])
            if not translated:
                continue

            x0, y0, x1, y1 = block["bbox"]
            font_size = block["size"]

            # 원본 텍스트를 흰색으로 덮기
            cover_rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
            page.draw_rect(cover_rect, color=None, fill=(1, 1, 1))

            # 한글 폰트 크기 조정
            text_width = x1 - x0
            estimated_kr_width = len(translated) * font_size * 0.55
            if estimated_kr_width > text_width and text_width > 0:
                scale = text_width / estimated_kr_width
                adjusted_size = max(font_size * scale, 5)
            else:
                adjusted_size = font_size

            # 색상 변환
            color_int = block.get("color", 0)
            r = ((color_int >> 16) & 0xFF) / 255.0
            g = ((color_int >> 8) & 0xFF) / 255.0
            b = (color_int & 0xFF) / 255.0

            text_rect = fitz.Rect(x0, y0, x1, y1 + adjusted_size * 0.5)
            page.insert_textbox(
                text_rect, translated,
                fontsize=adjusted_size, fontfile=font_path, fontname="korean",
                color=(r, g, b), align=fitz.TEXT_ALIGN_LEFT,
            )

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"번역 PDF 저장 완료: {output_path}")


# ── 4. CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="영문 PDF를 한글 PDF로 번역합니다.")
    parser.add_argument("input", help="번역할 PDF 파일 경로")
    parser.add_argument("-o", "--output", help="출력 PDF 경로 (기본: <파일명>_ko.pdf)")
    parser.add_argument("--api-key", required=True, help="Gemini API 키")
    parser.add_argument("--model", default="gemini-2.0-flash", help="Gemini 모델 (기본: gemini-2.0-flash)")
    parser.add_argument("--source", default="en", help="원본 언어 (기본: en)")
    parser.add_argument("--target", default="ko", help="대상 언어 (기본: ko)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"오류: 파일을 찾을 수 없습니다: {args.input}")
        sys.exit(1)

    if args.output is None:
        base, ext = os.path.splitext(args.input)
        args.output = f"{base}_ko{ext}"

    print(f"[1/3] PDF 텍스트 추출 중: {args.input}")
    pages = extract_pages(args.input)
    total_blocks = sum(len(p["blocks"]) for p in pages)
    print(f"       {len(pages)}페이지, {total_blocks}개 텍스트 블록 추출 완료")

    print(f"[2/3] {args.source} → {args.target} 번역 중...")
    pages = translate_pages(pages, args.source, args.target, args.api_key, args.model)

    print(f"[3/3] 번역 PDF 생성 중: {args.output}")
    generate_pdf(pages, args.output, args.input)
    print("완료!")


if __name__ == "__main__":
    main()
