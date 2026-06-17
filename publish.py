#!/usr/bin/env python3
"""
One-command publish helper for the GitHub Foundations Certification Practice Quiz.

What it does, in order:
  1. (default) Detects new screenshots in the Word doc and rebuilds quiz.html.
       - If there are NEW images that still need transcribing, it stops and tells
         you to have Copilot transcribe them first (vision can't be scripted offline).
  2. Copies the freshly built quiz.html into site/index.html.
  3. Commits & pushes to GitHub — but only if the published file actually changed.
  4. Prints the live URL.

Usage:
  python3 publish.py                 # detect new from docx, rebuild, publish
  python3 publish.py --build-only    # skip docx detect; just rebuild from manifest + publish
  python3 publish.py --docx '/path/to/your.docx'
  python3 publish.py --no-push       # build + stage, but don't push (dry run)
"""
import os, sys, json, shutil, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
SITE_INDEX = os.path.join(SITE, "index.html")
QUIZ_HTML = os.path.join(HERE, "quiz.html")
PENDING_JSON = os.path.join(HERE, "pending", "pending.json")
LIVE_URL = "https://ggingo.github.io/github-foundations-cert-quiz/"

sys.path.insert(0, HERE)
import update_quiz as u  # noqa: E402


def git(*args, check=True):
    return subprocess.run(["git", "-C", SITE, *args],
                          capture_output=True, text=True, check=check)


def main():
    ap = argparse.ArgumentParser(description="Build and publish the cert quiz to GitHub Pages")
    ap.add_argument("--docx", default=u.DOCX_DEFAULT, help="path to the Word document")
    ap.add_argument("--build-only", action="store_true",
                    help="skip docx detection; rebuild from manifest only")
    ap.add_argument("--no-push", action="store_true", help="build + stage but do not commit/push")
    a = ap.parse_args()

    # 1. Detect new screenshots (unless --build-only)
    if not a.build_only:
        u.detect(a.docx)
        # If new images were staged but not yet transcribed into the manifest, stop.
        if os.path.exists(PENDING_JSON):
            with open(PENDING_JSON) as f:
                pending = json.load(f)
            manifest = u.load_manifest()
            untranscribed = [p for p in pending if p["hash"] not in manifest]
            if untranscribed:
                print(f"\n⏸  {len(untranscribed)} new screenshot(s) need transcription first.")
                print("    Ask Copilot: \"transcribe the pending quiz images\"")
                print("    Then re-run:  python3 publish.py")
                sys.exit(2)

    # Rebuild from the manifest (covers both new-ingested and build-only paths)
    u.build()

    # 2. Copy build into the published site
    if not os.path.isdir(SITE):
        print(f"ERROR: site folder not found at {SITE}. Was the Pages repo set up?")
        sys.exit(1)
    shutil.copyfile(QUIZ_HTML, SITE_INDEX)

    # 3. Commit & push only if changed
    if a.no_push:
        print("\n--no-push: staged site/index.html but did not publish.")
        return
    changed = git("diff", "--quiet", "index.html", check=False).returncode != 0
    if not changed:
        print(f"\n✓ Nothing to publish — the live site already matches the latest build.\n  {LIVE_URL}")
        return
    git("add", "index.html")
    git("commit", "-q", "-m",
        "Publish updated quiz\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>")
    push = git("push", "-q", "origin", "main", check=False)
    if push.returncode != 0:
        print("ERROR pushing to GitHub:\n" + (push.stderr or push.stdout))
        sys.exit(1)
    print(f"\n🚀 Published! Pages will redeploy in ~1 minute.\n  {LIVE_URL}")


if __name__ == "__main__":
    main()
