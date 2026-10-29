"""受限子程序：文字PDF只經記憶體，不寫原檔，不啟用OCR。"""
from io import BytesIO
import json
import sys


def extract(data):
    from pypdf import PdfReader
    if len(data) > 10 * 1024 * 1024 or not data.startswith(b"%PDF-"):
        raise ValueError("invalid_or_oversized_pdf")
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > 50:
        raise ValueError("encrypted_or_too_many_pages")
    pages = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if len(text) > 8000:
            raise ValueError("page_text_limit")
        pages.append({"page": number, "text": text})
    if sum(len(p["text"]) for p in pages) < 30 or sum(len(p["text"]) for p in pages) > 100000:
        raise ValueError("empty_or_text_limit")
    return pages


if __name__ == "__main__":
    try:
        if sys.platform != "win32":
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(extract(sys.stdin.buffer.read(10 * 1024 * 1024 + 1)), ensure_ascii=False))
    except Exception:
        sys.stderr.write("pdf_requires_manual_review")
        sys.exit(1)
