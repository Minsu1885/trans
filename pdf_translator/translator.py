"""텍스트 번역 모듈 (Google Gemini API 사용)."""

import os
import google.generativeai as genai
from tqdm import tqdm


def _translate_batch(model, texts: list[str], source: str, target: str) -> list[str]:
    """여러 텍스트를 하나의 API 호출로 번역한다."""
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


def translate_pages(
    pages: list[dict],
    source: str = "en",
    target: str = "ko",
    api_key: str | None = None,
    model: str = "gemini-2.0-flash",
) -> list[dict]:
    """추출된 페이지 데이터의 텍스트를 Gemini API로 번역한다."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "Gemini API 키가 필요합니다. 환경변수 GEMINI_API_KEY를 설정하거나 --api-key 옵션을 사용하세요."
        )

    genai.configure(api_key=key)
    gemini_model = genai.GenerativeModel(model)

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

    # 번역 결과를 원본 구조에 반영
    for idx, (pi, bi) in enumerate(index_map):
        if idx < len(translated):
            pages[pi]["blocks"][bi]["translated"] = translated[idx].strip()
        else:
            pages[pi]["blocks"][bi]["translated"] = pages[pi]["blocks"][bi]["text"]

    return pages
