# GitHub Foundations Certification Practice Quiz — toolkit

Everything lives in `~/github-cert-quiz/`.

- **quiz.html** — the quiz. Double-click to open in any browser. A copy is also kept at
  `~/Desktop/GitHub-Cert-Quiz.html`. No internet needed; all questions are embedded.
- **manifest.json** — every screenshot ever transcribed, keyed by the image's content hash.
  Existing questions are never re-transcribed.
- **questions.json** — the deduplicated question set currently in the quiz.
- **template.html** — the app UI/logic the builder injects questions into.
- **update_quiz.py** — the incremental builder.
- **publish.py** — one command to rebuild **and** push the live GitHub Pages site.
- **site/** — the published web app (`index.html`); this folder is the GitHub Pages git repo.
- **pending/** — scratch area where brand-new screenshots are staged for transcription.

**Live site:** https://ggingo.github.io/github-foundations-cert-quiz/

## Taking the quiz
- One question at a time; radio buttons for single-answer, checkboxes for "select all that apply".
- **Submit** to grade: correct picks turn green, wrong picks red, the right answer is always shown green.
- Missed questions are randomly re-inserted into the queue so you see them again.
- **Restart** button (top-right) starts over any time.
- **Auto-save & resume**: progress is saved in your browser after every answer. Close the tab and
  reopen `quiz.html` later — it offers **Resume** or **Start over**. (Saved progress is automatically
  discarded if the question set changes after you add new questions.)
- At the end: total answered, first-attempt %, and overall accuracy.

## Adding more questions later (the recurring workflow)
1. Add your new screenshots to the Word doc and save it
   (default location: `~/Downloads/Foundations Study Material.docx`).
2. In Copilot CLI, say: **"update my cert quiz with the new questions."**
   Behind the scenes that runs:
   ```
   python3 ~/github-cert-quiz/update_quiz.py
   ```
   which finds only the NEW screenshots and stages them in `pending/`.
   Transcribing images requires AI vision, so Copilot reads the staged images,
   writes their Q&A, and folds them in with:
   ```
   python3 ~/github-cert-quiz/update_quiz.py --ingest <transcriptions.json>
   ```
3. `quiz.html` (and the Desktop copy) are rebuilt automatically. Reopen and study.

If the doc lives somewhere else, point at it:
```
python3 ~/github-cert-quiz/update_quiz.py --docx "/path/to/your.docx"
```

> ⚠️ The toolkit reads a **local** `.docx` file. If you edit the doc in SharePoint/OneDrive
> online, **download the latest copy first** (or save it to a synced OneDrive folder),
> otherwise the local file is stale and no new questions will be found.

## Publishing updates to the live website
The published site at GitHub Pages is a static snapshot — it does **not** auto-update.
After adding questions, push the new build live with **one command**:
```
python3 ~/github-cert-quiz/publish.py
```
This detects new screenshots, rebuilds, copies the result into `site/index.html`,
and commits + pushes (only if something changed). The live URL redeploys in ~1 minute.

If there are brand-new screenshots that still need transcribing, `publish.py` pauses and
asks you to transcribe them first (say *"transcribe the pending quiz images"* to Copilot),
then re-run `publish.py`.

Other options:
```
python3 ~/github-cert-quiz/publish.py --build-only   # skip docx detect; rebuild from manifest + publish
python3 ~/github-cert-quiz/publish.py --no-push       # build + stage only (dry run)
python3 ~/github-cert-quiz/publish.py --docx "/path/to/your.docx"
```

## Handy commands
```
python3 ~/github-cert-quiz/update_quiz.py --status   # counts + anything pending
python3 ~/github-cert-quiz/update_quiz.py --build     # rebuild quiz.html from manifest only
```
