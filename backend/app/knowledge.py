"""Knowledge base: parse documents into cited chunks, and retrieve them with BM25."""
import csv
import io
import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Chunk, Document

STOP = set("a an the and or of to in on for with by is are was were be been it this that these those as at from not no but if then "
           "than so such can could should would will may might must do does did has have had its into about over under per via".split())
SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".xlsx", ".json", ".html", ".htm"}


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9_\-]*", text.lower()) if len(t) > 1 and t not in STOP]


def extract_pages(filename: str, data: bytes) -> list[str]:
    """Return text per page (or per logical section)."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type '{ext or filename}'. Supported: {', '.join(sorted(SUPPORTED))}")
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
        if not any(p.strip() for p in pages):
            raise ValueError("This PDF has no extractable text (it may be a scanned image). Upload a text PDF or the source document.")
        return pages
    if ext == ".docx":
        import docx
        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return _paginate("\n".join(parts))
    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        pages = []
        for ws in wb.worksheets:
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= 500:
                    break
                rows.append(" | ".join("" if v is None else str(v) for v in row))
            pages.append(f"Sheet: {ws.title}\n" + "\n".join(rows))
        return pages
    text = data.decode("utf-8", errors="replace")
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(text)))[:500]
        text = "\n".join(" | ".join(r) for r in rows)
    if ext in (".html", ".htm"):
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return _paginate(text)


def _paginate(text: str, size=3500) -> list[str]:
    text = text.strip()
    return [text[i:i + size] for i in range(0, max(len(text), 1), size)] if text else [""]


def chunk_pages(pages: list[str], size=1200, overlap=150) -> list[tuple[int, str]]:
    out = []
    for pno, page in enumerate(pages, 1):
        page = re.sub(r"[ \t]+", " ", page).strip()
        if not page:
            continue
        i = 0
        while i < len(page):
            end = min(len(page), i + size)
            if end < len(page):
                cut = page.rfind(". ", i + size // 2, end)
                end = cut + 1 if cut > 0 else end
            out.append((pno, page[i:end].strip()))
            if end >= len(page):
                break
            i = max(end - overlap, i + 1)
    return out


def ingest(db: Session, doc: Document, data: bytes) -> Document:
    pages = extract_pages(doc.filename, data)
    chunks = chunk_pages(pages)
    for i, (page, text) in enumerate(chunks):
        db.add(Chunk(org_id=doc.org_id, document_id=doc.id, ord=i, page=page, text=text, terms=dict(Counter(tokens(text)))))
    doc.pages, doc.chunks, doc.status = len(pages), len(chunks), "ready"
    return doc


def search(db: Session, org_id: str, query: str, k: int = 5) -> list[dict]:
    """BM25 over the organisation's chunks. Returns text with document + page citations."""
    q = tokens(query)
    if not q:
        return []
    rows = db.execute(select(Chunk, Document.filename).join(Document, Document.id == Chunk.document_id)
                      .where(Chunk.org_id == org_id)).all()
    if not rows:
        return []
    n = len(rows)
    avgdl = sum(sum(c.terms.values()) for c, _ in rows) / n or 1
    df = Counter()
    for c, _ in rows:
        for t in set(q) & set(c.terms):
            df[t] += 1
    k1, b = 1.4, 0.75
    scored = []
    for c, fname in rows:
        dl = sum(c.terms.values()) or 1
        s = 0.0
        for t in q:
            f = c.terms.get(t, 0)
            if f:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))
        if s > 0:
            scored.append((s, c, fname))
    scored.sort(key=lambda x: -x[0])
    return [{"document": fname, "document_id": c.document_id, "page": c.page, "score": round(s, 3), "text": c.text}
            for s, c, fname in scored[:k]]


def corpus_digest(db: Session, org_id: str, budget_chars: int = 60000) -> list[dict]:
    """A budgeted sample of every document for the understanding pipeline: the start of each, round-robin."""
    docs = db.execute(select(Document).where(Document.org_id == org_id, Document.status == "ready")).scalars().all()
    if not docs:
        return []
    per = max(2000, budget_chars // len(docs))
    out = []
    for d in docs:
        chunks = db.execute(select(Chunk).where(Chunk.document_id == d.id).order_by(Chunk.ord)).scalars().all()
        text, used = [], 0
        for c in chunks:
            if used + len(c.text) > per:
                break
            text.append(f"[p.{c.page}] {c.text}")
            used += len(c.text)
        out.append({"document": d.filename, "pages": d.pages, "excerpt": "\n".join(text)})
    return out
