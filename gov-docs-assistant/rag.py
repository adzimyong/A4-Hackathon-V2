"""Core logic: read documents -> chunk -> embed -> store -> search -> answer.
Also: access levels per role, a library overview, and a meeting-minutes action item extractor.
Everything runs locally via Ollama + ChromaDB.
"""
import os
import re
import json
import hashlib
from pathlib import Path

import chromadb
import ollama
from rank_bm25 import BM25Okapi

# ---------- settings (change with environment variables) ----------
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")        # multilingual (English + Bahasa Malaysia)
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")       # small, runs on most laptops
DOCS_DIR = Path(os.getenv("DOCS_DIR", "docs"))
DB_DIR = os.getenv("DB_DIR", "db")
COLLECTION = "gov_docs"
CHUNK_SIZE = 900        # characters per chunk
CHUNK_OVERLAP = 150     # characters shared between neighbouring chunks
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.65"))  # above this = "not relevant enough"

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}

# ---------- access control ----------
LEVELS = ["public", "internal", "confidential"]
ROLE_ACCESS = {
    "Public": ["public"],
    "Staff": ["public", "internal"],
    "Manager": ["public", "internal", "confidential"],
}
# Used the first time, when docs/access.json does not exist yet. Edit that file to change the rules.
DEFAULT_ACCESS = {
    "default": "internal",
    "types": {"circular": "public", "sop": "internal", "minutes": "confidential"},
    "files": {},
}


# ---------- 1. reading files ----------
def load_file(path: Path):
    """Return a list of (page_number, text)."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        import fitz  # PyMuPDF
        pages = []
        with fitz.open(path) as pdf:
            for i, page in enumerate(pdf, start=1):
                pages.append((i, page.get_text()))
        return pages
    if ext == ".docx":
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        d = docx.Document(str(path))
        parts = []
        # walk the body in order so paragraphs AND tables are both read
        for child in d.element.body.iterchildren():
            if child.tag.endswith("}p"):
                parts.append(Paragraph(child, d).text)
            elif child.tag.endswith("}tbl"):
                for row in Table(child, d).rows:
                    cells = []
                    for c in row.cells:
                        t = c.text.strip()
                        if t and (not cells or cells[-1] != t):  # merged cells repeat their text
                            cells.append(t)
                    if cells:
                        parts.append(" | ".join(cells))
        return [(1, "\n".join(parts))]
    if ext in {".txt", ".md"}:
        return [(1, path.read_text(encoding="utf-8", errors="ignore"))]
    return []


# ---------- 2. chunking ----------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):  # try to cut at a sentence/paragraph end
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


# ---------- 3. access rules (public / internal / confidential) ----------
def _access_path():
    return DOCS_DIR / "access.json"


def load_access_rules():
    p = _access_path()
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(DEFAULT_ACCESS, indent=2), encoding="utf-8")
        except OSError:
            pass
        return json.loads(json.dumps(DEFAULT_ACCESS))
    try:
        rules = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(rules, dict):
            rules = {}
    except ValueError:
        rules = {}
    rules.setdefault("default", "internal")
    rules.setdefault("types", {})
    rules.setdefault("files", {})
    return rules


def default_level(doc_type: str, file_name: str = None):
    """Per-file rule first, then per-type rule, then the default."""
    r = load_access_rules()
    lvl = (r["files"].get(file_name) if file_name else None) or r["types"].get(doc_type) or r["default"]
    return lvl if lvl in LEVELS else "internal"


def save_file_level(file_name: str, level: str):
    r = load_access_rules()
    r["files"][file_name] = level
    _access_path().write_text(json.dumps(r, indent=2), encoding="utf-8")


# ---------- 4. embeddings + database ----------
def embed(texts, batch=16):
    out = []
    for i in range(0, len(texts), batch):
        out.extend(ollama.embed(model=EMBED_MODEL, input=texts[i:i + batch])["embeddings"])
    return out


def get_collection():
    client = chromadb.PersistentClient(path=DB_DIR)
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def guess_doc_type(path: Path):
    """docs/sop/x.pdf -> 'sop'. Files directly in docs/ -> 'general'."""
    try:
        rel = path.relative_to(DOCS_DIR)
        return rel.parts[0].lower() if len(rel.parts) > 1 else "general"
    except ValueError:
        return "general"


def guess_year(name: str):
    m = re.search(r"(19|20)\d{2}", name)
    return m.group(0) if m else ""


def ingest_file(path: Path, doc_type: str = None, classification: str = None):
    path = Path(path)
    doc_type = doc_type or guess_doc_type(path)
    level = classification if classification in LEVELS else default_level(doc_type, path.name)
    ids, docs, metas = [], [], []
    order = 0
    for page_no, text in load_file(path):
        for j, chunk in enumerate(chunk_text(text)):
            ids.append(hashlib.md5(f"{path.name}|{page_no}|{j}|{chunk[:50]}".encode()).hexdigest())
            # put the document name inside the text, so questions like "Milestone 1" can match it
            docs.append(f"Document: {path.stem}\n{chunk}")
            metas.append({"source": path.name, "page": page_no, "idx": order,
                          "doc_type": doc_type, "year": guess_year(path.name),
                          "classification": level})
            order += 1
    if not docs:
        return 0
    col = get_collection()
    col.upsert(ids=ids, documents=docs, embeddings=embed(docs), metadatas=metas)
    _cache["count"] = -1
    return len(docs)


def reset_collection():
    """Wipe the index so old chunks never linger after files change."""
    client = chromadb.PersistentClient(path=DB_DIR)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    _cache["count"] = -1


def ingest_all(progress=print):
    reset_collection()
    load_access_rules()  # creates docs/access.json with sensible defaults if it is missing
    total = 0
    files = [p for p in DOCS_DIR.rglob("*") if p.suffix.lower() in SUPPORTED]
    for p in sorted(files):
        n = ingest_file(p)
        progress(f"{p.name}: {n} chunks")
        total += n
    return total


def needs_reindex():
    """True if the index was built by an older version (missing the newer metadata)."""
    col = get_collection()
    if col.count() == 0:
        return False
    metas = col.get(limit=20, include=["metadatas"])["metadatas"]
    return any("classification" not in m or "idx" not in m for m in metas)


def set_classification(file_name: str, level: str):
    """Change a file's level without re-indexing, and remember it in docs/access.json."""
    if level not in LEVELS:
        return 0
    col = get_collection()
    data = col.get(where={"source": file_name}, include=["metadatas"])
    if not data["ids"]:
        return 0
    col.update(ids=data["ids"], metadatas=[dict(m, classification=level) for m in data["metadatas"]])
    save_file_level(file_name, level)
    _cache["count"] = -1
    return len(data["ids"])


# ---------- 5. library overview (answers "what files do you have?" without the AI) ----------
def library_summary(levels=None):
    """{doc_type: {file_name: {"pages", "chunks", "classification"}}}. Only files the role may see."""
    col = get_collection()
    if col.count() == 0:
        return {}
    lib = {}
    for m in col.get(include=["metadatas"])["metadatas"]:
        cls = m.get("classification", "internal")
        if levels and cls not in levels:
            continue
        info = lib.setdefault(m["doc_type"], {}).setdefault(
            m["source"], {"pages": 0, "chunks": 0, "classification": cls})
        info["pages"] = max(info["pages"], int(m["page"]))
        info["chunks"] += 1
    return lib


def hidden_count(levels):
    """How many files exist that this role cannot see."""
    if not levels:
        return 0
    everything = {n for t in library_summary().values() for n in t}
    visible = {n for t in library_summary(levels).values() for n in t}
    return len(everything - visible)


def list_doc_types(levels=None):
    return sorted(library_summary(levels))


def file_label(name, info):
    label = name
    if name.lower().endswith(".pdf"):
        n = info["pages"]
        label += f" ({n} page{'s' if n != 1 else ''})"
    return f"{label} · {info.get('classification', 'internal')}"


_ITEM = r"(?:files?|documents?|docs?|pdfs?|reports?)"
_CATALOG_REGEXES = [
    rf"\bhow many {_ITEM}\b",
    rf"^\W*(?:please )?(?:list|show|display)(?: me)?(?: all)?(?: the)?(?: available| indexed| uploaded)? {_ITEM}"
    rf"(?: you have| available| indexed| uploaded)?(?: (?:in|under|inside) .*)?\W*$",
    rf"\bwhat {_ITEM} (?:do you have|are (?:there|available|indexed|uploaded|stored)|have been (?:uploaded|indexed))",
    rf"\bwhich {_ITEM} (?:do you have|are (?:there|available|indexed|uploaded|stored))",
    rf"\b{_ITEM} (?:are )?(?:in|under|inside) (?:the )?[\w -]*(?:folder|library)\b",
    r"\bberapa(?: banyak)? (?:fail|dokumen)\b",
    r"\bsenarai (?:semua )?(?:fail|dokumen)\b",
]
# "how many documents are required to apply..." is a content question, not a library question
_NOT_CATALOG = re.compile(r"\b(required|require|needed|need|must|submit|attach|supporting|procedure|steps|apply|application)\b")


def answer_catalog_question(question: str, levels=None):
    """If the question is about the library itself (counts / lists of files), answer it from the
    database and return markdown. Otherwise return None."""
    q = question.lower().strip()
    lib = library_summary(levels)
    types = sorted(lib, key=len, reverse=True)

    hit = any(re.search(p, q) for p in _CATALOG_REGEXES)
    if not hit and types:  # e.g. "list all circulars"
        types_re = "|".join(re.escape(t) for t in types)
        hit = bool(re.search(rf"^\W*(?:list|show|display)(?: me)?(?: all)?(?: the)? (?:{types_re})s?\W*$", q))
    if not hit or _NOT_CATALOG.search(q):
        return None
    hidden = hidden_count(levels)
    if not lib:
        if hidden:
            return "🔒 There are no documents available for your role."
        return "No documents are indexed yet. Add some in the sidebar or run `python ingest.py`."

    wanted = [t for t in types if re.search(rf"\b{re.escape(t)}s?\b", q)]
    m = re.search(r"\b([\w-]+) (?:folder|category)\b", q)
    if m and not wanted and m.group(1) not in {"the", "a", "this", "that", "which", "each", "every", "what", "any"}:
        return (f"I couldn't find a folder called **{m.group(1)}**. "
                f"Available folders: {', '.join(f'**{t}**' for t in sorted(lib))}.")

    scope = {t: lib[t] for t in wanted} if wanted else lib
    total = sum(len(v) for v in scope.values())
    s = "" if total == 1 else "s"
    where = (f"in {', '.join(f'**{t}**' for t in sorted(scope))}" if wanted
             else f"in the library, across {len(scope)} folder{'' if len(scope) == 1 else 's'}")
    out = [f"There {'is' if total == 1 else 'are'} **{total} file{s}** {where}:", ""]
    for t in sorted(scope):
        out.append(f"**{t}** ({len(scope[t])} file{'' if len(scope[t]) == 1 else 's'})")
        out.append("")
        out += [f"- {file_label(n, i)}" for n, i in sorted(scope[t].items())]
        out.append("")
    if hidden:
        out.append(f"🔒 {hidden} more file{'' if hidden == 1 else 's'} {'is' if hidden == 1 else 'are'} "
                   f"restricted for your role.")
    return "\n".join(out)


# ---------- 6. search (meaning + keywords) ----------
_cache = {"count": -1}


def _tok(s: str):
    return re.findall(r"\w+", s.lower())


def _bm25(col):
    n = col.count()
    if _cache["count"] != n:
        data = col.get(include=["documents", "metadatas"])
        _cache.update(count=n, ids=data["ids"], docs=data["documents"], metas=data["metadatas"],
                      bm25=BM25Okapi([_tok(d) for d in data["documents"]]) if data["documents"] else None)
    return _cache


def retrieve(question: str, k: int = 5, doc_types=None, levels=None):
    """Return (hits, best_distance). Each hit = {text, meta}. `levels` = classifications the user may see."""
    col = get_collection()
    if col.count() == 0:
        return [], None
    conds = []
    if doc_types:
        conds.append({"doc_type": {"$in": list(doc_types)}})
    if levels:
        conds.append({"classification": {"$in": list(levels)}})
    where = None if not conds else (conds[0] if len(conds) == 1 else {"$and": conds})

    # (a) semantic search
    sem = col.query(query_embeddings=embed([question]), n_results=min(20, col.count()),
                    where=where, include=["documents", "metadatas", "distances"])
    sem_ids = sem["ids"][0]
    best_dist = sem["distances"][0][0] if sem["distances"][0] else None
    store = {i: {"text": t, "meta": m} for i, t, m in zip(sem_ids, sem["documents"][0], sem["metadatas"][0])}

    # (b) keyword search (good for exact things like "Circular 3/2024")
    c = _bm25(col)
    kw_ids = []
    if c["bm25"] is not None:
        scores = c["bm25"].get_scores(_tok(question))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:20]
        for i in order:
            if scores[i] <= 0:
                break
            meta = c["metas"][i]
            if doc_types and meta["doc_type"] not in doc_types:
                continue
            if levels and meta.get("classification", "internal") not in levels:
                continue
            kw_ids.append(c["ids"][i])
            store.setdefault(c["ids"][i], {"text": c["docs"][i], "meta": meta})

    # (c) merge the two rankings (reciprocal rank fusion)
    score = {}
    for ranking in (sem_ids, kw_ids):
        for rank, cid in enumerate(ranking):
            score[cid] = score.get(cid, 0) + 1 / (60 + rank)
    top = sorted(score, key=score.get, reverse=True)[:k]
    return [store[i] for i in top], best_dist


def restricted_distance(question: str, levels):
    """Distance of the best match among documents this role is NOT allowed to see (None if there are none).
    Only the distance is used. Nothing from the hidden document is ever shown."""
    if not levels or set(LEVELS) <= set(levels):
        return None
    col = get_collection()
    if col.count() == 0:
        return None
    hidden = [lv for lv in LEVELS if lv not in levels]
    res = col.query(query_embeddings=embed([question]), n_results=1,
                    where={"classification": {"$in": hidden}}, include=["distances"])
    d = res["distances"][0]
    return d[0] if d else None


def lock_applies(hidden_dist, visible_best, margin: float = 0.1):
    """Show the "restricted" message when the best document for this question is one the user cannot see.
    - hidden_dist: distance of the best hidden match (None = nothing hidden)
    - visible_best: distance of the best visible match (None = nothing visible)"""
    if hidden_dist is None or hidden_dist > MAX_DISTANCE:
        return False
    if visible_best is None or visible_best > MAX_DISTANCE:
        return True
    return hidden_dist + margin < visible_best  # hidden document is clearly a better match


def restricted_match(question: str, levels):
    """True if the question looks answerable from a document this role is NOT allowed to see."""
    return lock_applies(restricted_distance(question, levels), None)


# ---------- 7. answer with citations ----------
SYSTEM_PROMPT = (
    "You are an assistant for government staff. Answer the question using ONLY the numbered "
    "context passages below. After each fact, cite the passage number like [1] or [2]. "
    "If the context does not contain the answer, say you could not find it in the documents. "
    "Answer in the same language as the question. Be short and clear."
)


def answer_stream(question: str, hits):
    context = "\n\n".join(
        f"[{i}] ({h['meta']['source']}, page {h['meta']['page']})\n{h['text']}"
        for i, h in enumerate(hits, start=1)
    )
    stream = ollama.chat(
        model=LLM_MODEL,
        stream=True,
        keep_alive="30m",  # keep the model in memory so the next question starts faster
        options={"temperature": 0.1},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    for part in stream:
        yield part["message"]["content"]


_REFUSAL_RE = re.compile(
    r"(could\s*(not|n't)\s+find|cannot\s+find|can't\s+find|unable\s+to\s+find|"
    r"(do|does)\s+not\s+(mention|contain|provide|include|specify|state|say|have)|"
    r"not\s+(mentioned|found|specified|stated|provided)\s+in|no\s+(relevant\s+)?information|"
    r"tidak\s+(dapat\s+)?(jumpa|menemui|menjumpai|ada\s+maklumat|disebut|dinyatakan|mengandungi)|"
    r"tiada\s+maklumat)", re.I)


def looks_like_refusal(text: str) -> bool:
    """True when the model's answer says it could not find the answer in the documents."""
    return bool(text) and len(text) < 400 and bool(_REFUSAL_RE.search(text))


# ---------- 8. meeting minutes -> action items ----------
# Fast path: minutes that label their lines ("ACTION: Ahmad to ... by 15 October", "DECISION: ...") are parsed
# with simple patterns, which is instant. Only unlabeled minutes go to the AI, and then it only reads the
# sentences that look like actions or decisions (much less to read and write = much faster on a CPU).
ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["action", "decision"]},
                    "description": {"type": "string"},
                    "owner": {"type": "string"},
                    "deadline": {"type": "string"},
                },
                "required": ["type", "description", "owner", "deadline"],
            },
        }
    },
    "required": ["items"],
}

ACTION_PROMPT = (
    "You extract action items and decisions from meeting minutes. Rules: "
    "include ONLY tasks and decisions that are clearly written in the text; never invent anything. "
    "'action' = something a person or team must do. 'decision' = something that was agreed or decided. "
    "'owner' = the person or team responsible, or 'Not stated'. "
    "'deadline' = the date or time frame mentioned, or 'Not stated'. "
    "Keep each description short (under 15 words). "
    "Keep the original language of the text. If there are none, return an empty list."
)


def get_file_chunks(source: str, levels=None):
    """All text chunks of one file, in reading order (role-checked)."""
    col = get_collection()
    data = col.get(where={"source": source}, include=["documents", "metadatas"])
    rows = [(m.get("page", 1), m.get("idx", 0), d, m) for d, m in zip(data["documents"], data["metadatas"])]
    if levels:
        rows = [r for r in rows if r[3].get("classification", "internal") in levels]
    rows.sort(key=lambda r: (r[0], r[1]))
    return [re.sub(r"^Document: [^\n]*\n", "", r[2]) for r in rows]


def _stitch(chunks, max_overlap: int = CHUNK_OVERLAP + 20):
    """Join stored chunks back into one text, removing the overlap that chunking added."""
    out = ""
    for c in chunks:
        k = min(len(out), len(c), max_overlap)
        while k > 20 and not out.endswith(c[:k]):
            k -= 1
        out = out + " " + c if k <= 20 else out + c[k:]
    return out.strip()


_ABBR_RE = re.compile(r"\b(Dr|Mr|Mrs|Ms|Prof|Ir|Hj|Hjh|No|Bil|St|Tn|Pn|Cik)\.", re.I)
_DOT = "․"  # stands in for the dot in "Dr." so it is not treated as the end of a sentence


def _flat(text):
    return _ABBR_RE.sub(lambda m: m.group(1) + _DOT, re.sub(r"\s+", " ", text)).strip()


def _unflat(s):
    return s.replace(_DOT, ".")


_MONTH = (r"(?:jan(?:uary|uari)?|feb(?:ruary|ruari)?|mar(?:ch)?|mac|apr(?:il)?|mei|may|jun(?:e)?|jul(?:y|ai)?|"
          r"aug(?:ust)?|ogos|sep(?:t(?:ember)?)?|oct(?:ober)?|okt(?:ober)?|nov(?:ember)?|dec(?:ember)?|dis(?:ember)?)\b")
_DATE = (rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}(?:\s+\d{{4}})?"
         rf"|{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?"
         r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")
_DEADLINE_RE = re.compile(
    rf"\b(?:by|before|no later than|not later than|on or before|until|sebelum|menjelang|selewat-lewatnya)\s+"
    rf"(?:the\s+)?(?:end of\s+)?(?P<d>{_DATE}|next meeting|next week|next month|end of (?:the )?(?:week|month|year)"
    rf"|akhir (?:minggu|bulan|tahun))"
    rf"|\bwithin\s+(?P<w>\d+\s+(?:working\s+|business\s+)?(?:days?|weeks?|months?|hari|minggu|bulan))\b",
    re.I)
_MARKER = re.compile(
    r"\b(?P<tag>action(?:\s+items?)?|decisions?|resolved|resolution|to\s+do|tindakan|keputusan)\s*(?::|\s[-–—]\s)\s*",
    re.I)
_DECISION_TAGS = {"decision", "decisions", "resolved", "resolution", "keputusan"}
_OWNER_RE = re.compile(
    r"^(?P<owner>(?:[A-Z][\w․'’-]*\s+){0,4}[A-Z][\w․'’-]*)\s+"
    r"(?:to|will|shall|should|must|is to|are to|akan|perlu|hendaklah|untuk)\s+(?P<rest>.+)$")


def _tidy(s):
    s = _unflat(s).strip(" ,.;:-–—")
    return (s[0].upper() + s[1:]) if s else s


def _rule_extract(text):
    """Parse lines labelled ACTION:/DECISION: (also Tindakan:/Keputusan:). Instant, no AI."""
    t = _flat(text)
    marks = list(_MARKER.finditer(t))
    items = []
    for i, m in enumerate(marks):
        limit = marks[i + 1].start() if i + 1 < len(marks) else len(t)
        rest = t[m.end():limit]
        brk = re.search(r"(?<=[.!?])\s+(?=[A-Z0-9])", rest)  # the label's text ends with its sentence
        body = (rest[:brk.start()] if brk else rest).strip()
        if len(body) < 5:
            continue
        is_decision = m.group("tag").lower().split()[0] in _DECISION_TAGS

        deadline = "Not stated"
        dm = _DEADLINE_RE.search(body)
        if dm:
            deadline = _unflat((dm.group("d") or dm.group("w")).strip())
            body = body[:dm.start()] + body[dm.end():]

        owner = "Not stated"
        if not is_decision:
            om = _OWNER_RE.match(body.strip())
            if om:
                owner, body = om.group("owner"), om.group("rest")

        desc = _tidy(re.sub(r"\s+", " ", body))
        if len(desc) >= 5:
            items.append({"type": "Decision" if is_decision else "Action", "description": desc,
                          "owner": _unflat(owner), "deadline": deadline})
    return items


_CUE_RE = re.compile(r"\b(action|decid\w*|agree\w*|approv\w*|resolv\w*|endors\w*|shall|will|must|should|to be|"
                     r"responsible|follow[- ]up|tindakan|keputusan|diputuskan|bersetuju|diluluskan|perlu|"
                     r"hendaklah|akan|bertanggungjawab)\b", re.I)


def _candidate_text(text):
    """Keep only the sentences that look like an action or a decision (less for the AI to read)."""
    seen, keep = set(), []
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", _flat(text)):
        s = s.strip()
        key = re.sub(r"\W+", " ", s.lower())
        if s and key not in seen and (_CUE_RE.search(s) or _DEADLINE_RE.search(s)):
            seen.add(key)
            keep.append(s)
    return _unflat(" ".join(keep))


def _windows(text, size):
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(s) > size:
            out.append(cur)
            cur = ""
        cur += (" " if cur else "") + s
    if cur:
        out.append(cur)
    return out


def _llm_extract(text: str):
    """Ask the local model for action items in one piece of text. Returns a clean list of dicts."""
    try:
        resp = ollama.chat(
            model=LLM_MODEL, format=ACTION_SCHEMA, keep_alive="30m",
            options={"temperature": 0, "num_predict": 900},
            messages=[{"role": "system", "content": ACTION_PROMPT},
                      {"role": "user", "content": f"Meeting minutes text:\n{text}"}],
        )
        data = json.loads(resp["message"]["content"])
    except Exception:
        return []
    out = []
    for it in (data.get("items", []) if isinstance(data, dict) else []):
        if not isinstance(it, dict):
            continue
        desc = str(it.get("description", "")).strip()
        if len(desc) < 5:
            continue
        out.append({
            "type": "Decision" if str(it.get("type", "")).lower().startswith("dec") else "Action",
            "description": desc,
            "owner": str(it.get("owner", "")).strip() or "Not stated",
            "deadline": str(it.get("deadline", "")).strip() or "Not stated",
        })
    return out


def extract_action_items(source: str, levels=None, progress=None, use_ai: bool = False, window_chars: int = 2500):
    """Returns (items, method). method is "rules" (instant) or "ai".
    Labelled minutes use the fast rules. Unlabelled minutes (or use_ai=True) go to the AI."""
    text = _stitch(get_file_chunks(source, levels))
    if not text:
        return [], "rules"

    items, method = [], "rules"
    if not use_ai:
        items = _rule_extract(text)
    if items:
        if progress:
            progress(1, 1)
    else:
        method = "ai"
        cand = _candidate_text(text)
        wins = _windows(cand, window_chars) if cand else []
        for i, w in enumerate(wins):
            if progress:
                progress(i, len(wins))
            items += _llm_extract(w)
        if progress and wins:
            progress(len(wins), len(wins))

    out, seen = [], set()
    for it in items:
        key = re.sub(r"\W+", " ", it["description"].lower()).strip()[:80]
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out, method