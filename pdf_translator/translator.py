"""텍스트 번역 모듈 (Google Translate 무료 API 사용)."""

from deep_translator import GoogleTranslator
from tqdm import tqdm


def translate_pages(pages: list[dict], source: str = "en", target: str = "ko") -> list[dict]:
    """추출된 페이지 데이터의 텍스트를 번역한다.

    원본 레이아웃 정보는 그대로 유지하고 text 필드만 번역본으로 교체한다.
    """
    translator = GoogleTranslator(source=source, target=target)

    # 모든 텍스트를 한 번에 모아서 배치 번역 (API 호출 최소화)
    all_texts = []
    index_map = []  # (page_idx, block_idx)

    for pi, page in enumerate(pages):
        for bi, block in enumerate(page["blocks"]):
            all_texts.append(block["text"])
            index_map.append((pi, bi))

    # 5000자 제한이 있으므로 청크로 나눠서 번역
    translated = []
    chunk: list[str] = []
    chunk_len = 0
    MAX_CHUNK = 4500

    print(f"번역할 텍스트 블록: {len(all_texts)}개")

    for text in tqdm(all_texts, desc="번역 중"):
        if chunk_len + len(text) + 1 > MAX_CHUNK and chunk:
            batch = "\n||\n".join(chunk)
            try:
                result = translator.translate(batch)
                translated.extend(result.split("\n||\n"))
            except Exception:
                # 실패 시 개별 번역 시도
                for t in chunk:
                    try:
                        translated.append(translator.translate(t))
                    except Exception:
                        translated.append(t)
            chunk = []
            chunk_len = 0
        chunk.append(text)
        chunk_len += len(text) + 1

    # 남은 청크 처리
    if chunk:
        batch = "\n||\n".join(chunk)
        try:
            result = translator.translate(batch)
            translated.extend(result.split("\n||\n"))
        except Exception:
            for t in chunk:
                try:
                    translated.append(translator.translate(t))
                except Exception:
                    translated.append(t)

    # 번역 결과 수가 맞지 않으면 개별 번역으로 폴백
    if len(translated) != len(all_texts):
        print("배치 번역 결과 불일치, 개별 번역으로 재시도...")
        translated = []
        for text in tqdm(all_texts, desc="개별 번역 중"):
            try:
                translated.append(translator.translate(text))
            except Exception:
                translated.append(text)

    # 번역 결과를 원본 구조에 반영
    for idx, (pi, bi) in enumerate(index_map):
        if idx < len(translated):
            pages[pi]["blocks"][bi]["translated"] = translated[idx].strip()
        else:
            pages[pi]["blocks"][bi]["translated"] = pages[pi]["blocks"][bi]["text"]

    return pages
