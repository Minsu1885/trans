# PDF 한글 번역기

영문 PDF를 넣으면 동일한 레이아웃의 한글 번역 PDF를 생성합니다.

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

```bash
python -m pdf_translator input.pdf                    # → input_ko.pdf 생성
python -m pdf_translator input.pdf -o translated.pdf   # 출력 파일명 지정
python -m pdf_translator input.pdf --source en --target ja  # 다른 언어로 번역
```

## 동작 방식

1. **추출** - PyMuPDF로 PDF에서 텍스트 블록의 위치·폰트·크기·색상 정보를 추출
2. **번역** - Google Translate API(무료)로 텍스트를 한국어로 번역
3. **생성** - 원본 PDF 위에 흰색으로 영어 텍스트를 덮고 같은 위치에 한글을 삽입
