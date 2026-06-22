#!/usr/bin/env python3
"""
GitHub Certification Quiz - incremental builder.

Workflow when you add new screenshots to the Word doc:
  1. python3 update_quiz.py            -> extracts images, finds NEW ones, rebuilds quiz from what's known
  2. If it reports new images, ask Copilot to transcribe them (they're staged in ./pending/)
  3. Copilot writes the transcriptions and runs:  python3 update_quiz.py --ingest <file.json>
  4. quiz.html is rebuilt automatically. Open it.

Other commands:
  python3 update_quiz.py --build       -> just rebuild quiz.html from manifest.json (no docx needed)
  python3 update_quiz.py --status      -> show counts + anything pending transcription

The manifest (manifest.json) remembers every screenshot we've already transcribed,
keyed by the image's content hash, so existing questions are never re-transcribed.
Duplicate questions (same text/options) are removed automatically at build time.
"""
import json, os, re, sys, glob, zipfile, hashlib, shutil, tempfile, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")


def _default_docx():
    """Local docx path: config.json -> legacy Downloads file."""
    try:
        with open(CONFIG) as f:
            p = json.load(f).get("docx_path")
        if p:
            return os.path.expanduser(p)
    except Exception:
        pass
    return os.path.expanduser("~/Downloads/Foundations Study Material.docx")


DOCX_DEFAULT = _default_docx()
MANIFEST = os.path.join(HERE, "manifest.json")
PENDING_DIR = os.path.join(HERE, "pending")
PENDING_JSON = os.path.join(HERE, "pending", "pending.json")
QUESTIONS_JSON = os.path.join(HERE, "questions.json")
QUIZ_HTML = os.path.join(HERE, "quiz.html")
TEMPLATE = os.path.join(HERE, "template.html")
COURSES_DIR = os.path.join(HERE, "courses")
DESKTOP_COPY = os.path.expanduser("~/Desktop/GitHub-Cert-Quiz.html")

# Questions from the screenshot manifest belong to this course unless tagged otherwise.
DEFAULT_COURSE = "foundations"


# ---------- helpers ----------
def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(s):
    if not s:
        return ""
    return re.sub(r"[\s\W_]+", " ", str(s).lower()).strip()


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            return json.load(f)
    return {}


def save_manifest(m):
    with open(MANIFEST, "w") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)


def load_courses():
    """Load curated, sourceless question sets from courses/*.json.

    Each file is a JSON array of question dicts already in final shape:
      {question, type, options:[{text,correct}], explanation, source, course}
    A question's course defaults to the file's name stem (e.g. courses/copilot.json
    -> course "copilot") when the question itself doesn't specify one.
    """
    out = []
    if os.path.isdir(COURSES_DIR):
        for fn in sorted(os.listdir(COURSES_DIR)):
            if not fn.endswith(".json"):
                continue
            stem = os.path.splitext(fn)[0]
            with open(os.path.join(COURSES_DIR, fn)) as f:
                arr = json.load(f)
            for q in arr:
                q = dict(q)
                q.setdefault("course", stem)
                out.append(q)
    return out


def extract_media(docx):
    """Return dict hash -> temp filepath for every embedded image."""
    tmp = tempfile.mkdtemp(prefix="quizmedia_")
    out = {}
    with zipfile.ZipFile(docx) as z:
        for name in z.namelist():
            if name.startswith("word/media/") and re.search(r"\.(png|jpe?g)$", name, re.I):
                data = z.read(name)
                h = hashlib.sha256(data).hexdigest()
                ext = os.path.splitext(name)[1].lower()
                p = os.path.join(tmp, h + ext)
                if h not in out:
                    with open(p, "wb") as f:
                        f.write(data)
                    out[h] = p
    return tmp, out


# ---------- build ----------
def build():
    manifest = load_manifest()
    # Combine the screenshot manifest (Foundations) with any curated course files.
    candidates = []
    for h, q in manifest.items():
        q = dict(q)
        q.setdefault("course", DEFAULT_COURSE)
        candidates.append(q)
    candidates.extend(load_courses())

    kept, seen, dropped, deduped = [], set(), 0, 0
    for q in candidates:
        qt = q.get("question")
        if not qt or not str(qt).strip():
            dropped += 1
            continue
        low = str(qt).lower()
        if any(x in low for x in ("not visible", "not readable", "cropped")) or low.strip().startswith("[question"):
            dropped += 1
            continue
        opts = q.get("options") or []
        if not opts or not any(o.get("correct") for o in opts):
            dropped += 1
            continue
        course = q.get("course") or DEFAULT_COURSE
        # Dedup within a course only: the same concept may legitimately appear in
        # both Foundations and Copilot study sets.
        key = course + "||" + norm(qt) + "||" + "|".join(sorted(norm(o.get("text", "")) for o in opts))
        if key in seen:
            deduped += 1
            continue
        seen.add(key)
        n_correct = sum(1 for o in opts if o.get("correct"))
        qtype = "multiple" if n_correct > 1 else (q.get("type") or "single")
        kept.append({
            "question": str(qt).strip(),
            "type": qtype,
            "options": [{"text": str(o.get("text", "")).strip(), "correct": bool(o.get("correct"))} for o in opts],
            "explanation": q.get("explanation") or None,
            "course": course,
            "source": q.get("source") or None,
        })

    with open(QUESTIONS_JSON, "w") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)
    with open(TEMPLATE) as f:
        tpl = f.read()
    html = tpl.replace("__QUESTIONS_DATA__", json.dumps(kept, ensure_ascii=False))
    with open(QUIZ_HTML, "w") as f:
        f.write(html)
    try:
        shutil.copyfile(QUIZ_HTML, DESKTOP_COPY)
        desk = f" (and copied to {DESKTOP_COPY})"
    except Exception:
        desk = ""
    by_course = {}
    for q in kept:
        by_course[q["course"]] = by_course.get(q["course"], 0) + 1
    course_str = ", ".join(f"{k}: {v}" for k, v in sorted(by_course.items()))
    print(f"Built {len(kept)} unique questions "
          f"[{sum(1 for q in kept if q['type']=='single')} single / "
          f"{sum(1 for q in kept if q['type']=='multiple')} multi]; "
          f"removed {deduped} duplicates, {dropped} unusable.")
    print(f"By course -> {course_str}")
    print(f"Wrote {QUIZ_HTML}{desk}")
    return kept


# ---------- detect new ----------
def detect(docx):
    if not os.path.exists(docx):
        print(f"ERROR: document not found at: {docx}")
        print("Pass the correct path:  python3 update_quiz.py --docx '/path/to/your.docx'")
        sys.exit(1)
    manifest = load_manifest()
    tmp, media = extract_media(docx)
    new = {h: p for h, p in media.items() if h not in manifest}
    # stage pending images with stable names
    if os.path.isdir(PENDING_DIR):
        for f in glob.glob(os.path.join(PENDING_DIR, "p*.png")) + glob.glob(os.path.join(PENDING_DIR, "p*.jpg")):
            os.remove(f)
    else:
        os.makedirs(PENDING_DIR, exist_ok=True)
    pending = []
    for i, (h, p) in enumerate(sorted(new.items()), 1):
        ext = os.path.splitext(p)[1].lower()
        name = f"p{i:03d}{ext}"
        dest = os.path.join(PENDING_DIR, name)
        shutil.copyfile(p, dest)
        pending.append({"name": name, "hash": h})
    with open(PENDING_JSON, "w") as f:
        json.dump(pending, f, indent=2)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Document images: {len(media)} | already known: {len(media)-len(new)} | NEW: {len(new)}")
    if new:
        print(f"\n{len(new)} new screenshot(s) staged in: {PENDING_DIR}")
        print("ASK COPILOT: \"transcribe the pending quiz images\" — it will read ./pending/ "
              "and run --ingest to fold them in.")
    return pending


# ---------- ingest transcriptions ----------
def ingest(trans_file):
    with open(PENDING_JSON) as f:
        pend = {x["name"]: x["hash"] for x in json.load(f)}
    with open(trans_file) as f:
        objs = json.load(f)
    manifest = load_manifest()
    added = 0
    for o in objs:
        src = o.get("source") or o.get("name")
        h = pend.get(src) or pend.get(os.path.basename(src or ""))
        if not h:
            print(f"  ! could not match '{src}' to a pending image hash; skipping")
            continue
        manifest[h] = {
            "question": o.get("question"),
            "type": o.get("type"),
            "options": o.get("options") or [],
            "explanation": o.get("explanation"),
            "source": src,
        }
        added += 1
    save_manifest(manifest)
    print(f"Ingested {added} transcription(s) into manifest ({len(manifest)} total known).")
    build()


def status():
    manifest = load_manifest()
    print(f"Known transcribed images: {len(manifest)}")
    if os.path.exists(PENDING_JSON):
        with open(PENDING_JSON) as f:
            p = json.load(f)
        if p:
            print(f"Pending transcription: {len(p)} image(s) in {PENDING_DIR}")
    if os.path.exists(QUESTIONS_JSON):
        with open(QUESTIONS_JSON) as f:
            print(f"Quiz currently has: {len(json.load(f))} unique questions")


def main():
    ap = argparse.ArgumentParser(description="Incremental GitHub cert quiz builder")
    ap.add_argument("--docx", default=DOCX_DEFAULT, help="path to the Word document")
    ap.add_argument("--build", action="store_true", help="rebuild quiz.html from manifest only")
    ap.add_argument("--ingest", metavar="FILE", help="merge a transcription JSON into the manifest, then rebuild")
    ap.add_argument("--status", action="store_true", help="show counts")
    a = ap.parse_args()
    if a.status:
        return status()
    if a.ingest:
        return ingest(a.ingest)
    if a.build:
        return build()
    # default: detect new from docx, then rebuild from what's known
    detect(a.docx)
    build()


if __name__ == "__main__":
    main()
