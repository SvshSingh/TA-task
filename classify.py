"""Classify forum comments as acceptable / toxic / spam with Cloudflare's Clef model,
then write an easy-to-scan HTML report.

Usage:
    python classify.py                                   # comments.json, clef-flash -> results.html
    python classify.py comments-v2.json --model clef -o results-v2.html
    python classify.py comments.json --html-only         # re-render HTML from saved raw results

Credentials are read from cloud-flare.local.sh (never committed; see .gitignore).
Python standard library only.
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LABELS = ["acceptable", "toxic", "spam"]
LOW_CONFIDENCE = 0.5  # answers below this get flagged for a human look

# --- What we ask Clef -------------------------------------------------------------

INSTRUCTIONS = (
    "You are moderating the discussion forum of {course}, an online college course. "
    "This forum is for: {forum}. Students and instructors post doubts, share their work, "
    "give feedback, discuss grading and debate the course topic. "
    "Classify `comment`, posted by `author` in the `thread` thread. "
    "Judge the comment as a whole. Disagreement, complaints about the course, blunt or "
    "critical feedback, frustration, casual language and mild slang are all normal in a "
    "student forum and are acceptable as long as they are not aimed at hurting a person. "
    "Sharing a link to your own course work, a resource relevant to the course, or a "
    "genuine question is acceptable. Do not mark a comment as spam just because it "
    "mentions a link, a tool or a product, and do not mark it toxic just because it is "
    "negative."
)

CRITERIA = {
    "acceptable": (
        "A genuine post by a course participant that is fine to leave up: questions, "
        "answers, sharing or reviewing work, feedback (even harsh feedback about the work, "
        "the course or the tools), disagreement, complaints, jokes, and off-topic chat "
        "that is harmless and not promotional."
    ),
    "toxic": (
        "Attacks, insults, mocks, harasses, threatens or demeans a person or group "
        "(another student, an instructor, or people based on caste, religion, region, "
        "gender, language etc.), including name-calling, slurs, sarcasm meant to "
        "humiliate, public shaming, or encouraging others to pile on. Also covers "
        "sharing someone's private information or pushing others to cheat."
    ),
    "spam": (
        "Unsolicited promotion or scams not meant as real participation: selling "
        "assignment-writing or cheating services, paid courses, referral or affiliate "
        "links, giveaways, crypto or money-making offers, phishing, 'contact me on "
        "WhatsApp/Telegram' solicitations, follow-for-follow requests, and repetitive "
        "or copy-pasted advertising, even if dressed up as a normal post."
    ),
}


def build_payload(comment, meta):
    return {
        "state": {
            "comment": comment["comment"],
            "author": comment.get("author", ""),
            "thread": comment.get("thread", ""),
        },
        "questions": {
            "moderation": {
                "type": "choice",
                "instructions": INSTRUCTIONS.format(
                    course=meta.get("course", "a course"), forum=meta.get("forum", "the course")
                ),
                "criteria": CRITERIA,
            }
        },
    }


# --- Calling Clef -----------------------------------------------------------------

def load_credentials(path="cloud-flare.local.sh"):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"Missing {path}: copy cloud-flare.sh to {path} and fill in your account ID and token.")
    creds = dict(re.findall(r'export (\w+)="([^"]*)"', text))
    return creds["CLOUDFLARE_ACCOUNT_ID"], creds["CLOUDFLARE_API_TOKEN"]


def call_clef(payload, account, token, model, retries=5):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{model}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
            if not data.get("success"):
                raise RuntimeError(f"Clef error: {data.get('errors')}")
            return data["result"]["answers"]["moderation"]
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f"HTTP {e.code}: check the account ID and token in cloud-flare.local.sh")
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt)
    raise RuntimeError("Gave up after repeated rate-limit / network errors")


def classify_all(data, model, workers=4):
    account, token = load_credentials()
    comments = data["comments"]
    meta = {k: v for k, v in data.items() if k != "comments"}
    done = 0

    def work(c):
        nonlocal done
        answer = call_clef(build_payload(c, meta), account, token, model)
        done += 1
        print(f"  [{done}/{len(comments)}] #{c['id']}: {answer['choice']} ({answer['confidence']:.2f})")
        return {"id": c["id"], **answer}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(work, comments))


# --- HTML report --------------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clef moderation results</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --text:#1d1d1b; --muted:#6b6b66; --line:#e3e3df;
  --acceptable:#2f7d4f; --toxic:#c0392b; --spam:#b7791f; --flag:#fff4d6; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161615; --card:#1f1f1d; --text:#ececea;
  --muted:#9a9a94; --line:#33332f; --acceptable:#5cc489; --toxic:#ef6b5d; --spam:#e6ad4e; --flag:#3a3220; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,sans-serif; }}
main {{ max-width:1000px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:22px; margin:0 0 4px; }}
.sub {{ color:var(--muted); margin:0 0 20px; }}
.stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 14px; min-width:120px; }}
.stat b {{ display:block; font-size:22px; }}
.bar {{ position:sticky; top:0; background:var(--bg); padding:10px 0; display:flex; gap:8px; flex-wrap:wrap; align-items:center; z-index:1; border-bottom:1px solid var(--line); }}
button {{ font:inherit; border:1px solid var(--line); background:var(--card); color:var(--text); border-radius:999px; padding:4px 12px; cursor:pointer; }}
button.on {{ background:var(--text); color:var(--bg); }}
input[type=search] {{ font:inherit; flex:1; min-width:160px; padding:4px 10px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--text); }}
.c {{ background:var(--card); border:1px solid var(--line); border-left:5px solid var(--line); border-radius:8px; padding:12px 14px; margin-top:10px; }}
.c.acceptable {{ border-left-color:var(--acceptable); }} .c.toxic {{ border-left-color:var(--toxic); }} .c.spam {{ border-left-color:var(--spam); }}
.c.low {{ background:var(--flag); }}
.head {{ display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; font-size:13px; color:var(--muted); }}
.id {{ font-weight:700; color:var(--text); }}
.label {{ font-weight:700; text-transform:uppercase; font-size:12px; letter-spacing:.04em; }}
.label.acceptable {{ color:var(--acceptable); }} .label.toxic {{ color:var(--toxic); }} .label.spam {{ color:var(--spam); }}
.text {{ margin:6px 0 8px; white-space:pre-wrap; overflow-wrap:anywhere; }}
.probs {{ display:flex; gap:12px; flex-wrap:wrap; font-size:12px; color:var(--muted); }}
.p {{ display:flex; align-items:center; gap:4px; }}
.p i {{ display:inline-block; height:6px; border-radius:3px; background:currentColor; }}
.flag {{ color:var(--text); font-weight:600; }}
</style></head><body><main>
<h1>Clef moderation results</h1>
<p class="sub">{source} &middot; model <b>{model}</b> &middot; {n} comments &middot; highlighted cards have confidence below {low}</p>
<div class="stats">{stats}</div>
<div class="bar">
  <button data-f="all" class="on">All</button>
  <button data-f="acceptable">Acceptable</button><button data-f="toxic">Toxic</button><button data-f="spam">Spam</button>
  <button data-f="low">Low confidence</button>
  <button id="sort">Sort: by id</button>
  <input type="search" id="q" placeholder="Search text or author">
</div>
<div id="list">{cards}</div>
</main>
<script>
let f = 'all', byConf = false;
const list = document.getElementById('list'), cards = [...list.children];
function apply() {{
  const q = document.getElementById('q').value.toLowerCase();
  cards.forEach(c => {{
    const okF = f === 'all' || c.classList.contains(f);
    const okQ = !q || c.textContent.toLowerCase().includes(q);
    c.style.display = okF && okQ ? '' : 'none';
  }});
}}
document.querySelectorAll('[data-f]').forEach(b => b.onclick = () => {{
  document.querySelectorAll('[data-f]').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); f = b.dataset.f; apply();
}});
document.getElementById('q').oninput = apply;
document.getElementById('sort').onclick = e => {{
  byConf = !byConf;
  e.target.textContent = byConf ? 'Sort: least confident first' : 'Sort: by id';
  cards.slice().sort((a, b) => byConf ? a.dataset.conf - b.dataset.conf : a.dataset.id - b.dataset.id)
       .forEach(c => list.appendChild(c));
}};
</script></body></html>
"""


def render_html(data, results, model, source):
    by_id = {r["id"]: r for r in results}
    counts = {label: 0 for label in LABELS}
    low = 0
    cards = []
    for c in data["comments"]:
        r = by_id[c["id"]]
        label, conf = r["choice"], r["confidence"]
        counts[label] = counts.get(label, 0) + 1
        is_low = conf < LOW_CONFIDENCE
        low += is_low
        probs = "".join(
            f'<span class="p label {k}" title="{k}">{k[:3]} {p:.2f} <i style="width:{p * 50:.0f}px"></i></span>'
            for k, p in sorted(r["probabilities"].items(), key=lambda kv: -kv[1])
        )
        cards.append(
            f'<div class="c {label}{" low" if is_low else ""}" data-id="{c["id"]}" data-conf="{conf:.4f}">'
            f'<div class="head"><span class="id">#{c["id"]}</span>'
            f'<span class="label {label}">{label}</span>'
            f'<span>confidence {conf:.2f}</span>{"<span class=flag>check</span>" if is_low else ""}'
            f'<span>{html.escape(c.get("author", ""))}</span><span>{html.escape(c.get("thread", ""))}</span>'
            f'<span>{html.escape(c.get("posted_at", ""))}</span></div>'
            f'<div class="text">{html.escape(c["comment"])}</div>'
            f'<div class="probs">{probs}</div></div>'
        )
    stats = "".join(f'<div class="stat"><span class="label {k}">{k}</span><b>{counts[k]}</b></div>' for k in LABELS)
    stats += f'<div class="stat"><span class="label">low confidence</span><b>{low}</b></div>'
    return PAGE.format(
        source=html.escape(data.get("forum", source)), model=html.escape(model), n=len(data["comments"]),
        low=LOW_CONFIDENCE, stats=stats, cards="".join(cards),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", default="comments.json")
    ap.add_argument("--model", default="clef-flash", choices=["clef-flash", "clef"])
    ap.add_argument("-o", "--output", help="HTML file (default: results.html, or results-v2.html for comments-v2.json)")
    ap.add_argument("--html-only", action="store_true", help="re-render HTML from the saved raw results")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    suffix = "-v2" if "v2" in Path(args.input).stem else ""
    output = args.output or f"results{suffix}.html"
    raw_path = Path(output).with_suffix(".json")  # raw Clef answers, kept for re-rendering / review

    if args.html_only:
        saved = json.loads(raw_path.read_text(encoding="utf-8"))
        model, results = saved["model"], saved["results"]
    else:
        model = args.model
        print(f"Classifying {len(data['comments'])} comments from {args.input} with {model}...")
        results = classify_all(data, model)
        raw_path.write_text(json.dumps({"model": model, "results": results}, indent=1), encoding="utf-8")

    Path(output).write_text(render_html(data, results, model, args.input), encoding="utf-8")
    print(f"Wrote {output} (raw answers in {raw_path})")


if __name__ == "__main__":
    main()
