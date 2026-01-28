"""PDF 번역기 CLI 진입점."""

import argparse
import os
import sys

from .extractor import extract_pages
from .translator import translate_pages
from .generator import generate_pdf


def main():
    parser = argparse.ArgumentParser(
        description="영문 PDF를 한글 PDF로 번역합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python -m pdf_translator input.pdf
  python -m pdf_translator input.pdf -o output_ko.pdf
  python -m pdf_translator input.pdf --source en --target ko
        """,
    )
    parser.add_argument("input", help="번역할 영문 PDF 파일 경로")
    parser.add_argument("-o", "--output", help="출력 PDF 파일 경로 (기본: <입력파일>_ko.pdf)")
    parser.add_argument("--source", default="en", help="원본 언어 코드 (기본: en)")
    parser.add_argument("--target", default="ko", help="대상 언어 코드 (기본: ko)")

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
    pages = translate_pages(pages, source=args.source, target=args.target)

    print(f"[3/3] 번역 PDF 생성 중: {args.output}")
    generate_pdf(pages, args.output, args.input)

    print("완료!")


if __name__ == "__main__":
    main()
