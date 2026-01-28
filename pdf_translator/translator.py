"""텍스트 번역 모듈 (OpenAI API 사용)."""

import os
from openai import OpenAI
from tqdm import tqdm


def _translate_batch(client: OpenAI, texts: list[str], source: str, target: str, model: str) -> list[str]:
    """여러 텍스트를 하나의 API 호출로 번역한다."""
    numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts))

    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate the following {source} texts to {target}. "
                    f"Each line starts with [number]. Return ONLY the translations, one per line, "
                    f"keeping the same [number] prefix. Do not add explanations."
                ),
            },
            {"role": "user", "content": numbered},
        ],
    )

    result_text = response.choices[0].message.content.strip()
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
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """추출된 페이지 데이터의 텍스트를 OpenAI API로 번역한다."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OpenAI API 키가 필요합니다. 환경변수 OPENAI_API_KEY를 설정하거나 --api-key 옵션을 사용하세요."
        )

    client = OpenAI(api_key=key)

    all_texts = []
    index_map = []

    for pi, page in enumerate(pages):
        for bi, block in enumerate(page["blocks"]):
            all_texts.append(block["text"])
            index_map.append((pi, bi))

    print(f"번역할 텍스트 블록: {len(all_texts)}개")

    # 배치 단위로 번역 (한 번에 50개씩)
    BATCH_SIZE = 50
    translated = []

    for start in tqdm(range(0, len(all_texts), BATCH_SIZE), desc="번역 중"):
        batch = all_texts[start:start + BATCH_SIZE]
        try:
            result = _translate_batch(client, batch, source, target, model)
            translated.extend(result)
        except Exception as e:
            print(f"\n배치 번역 실패, 개별 번역 시도: {e}")
            for text in batch:
                try:
                    r = _translate_batch(client, [text], source, target, model)
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
