# Notes

## How to run

Needs Python 3.8+ (standard library only, nothing to install).

1. Copy `cloud-flare.sh` to `cloud-flare.local.sh` and put in your Cloudflare account ID
   and a Workers AI API token. That file is in `.gitignore`, so it is never committed.
2. Classify the first set with `clef-flash`:

       python classify.py comments.json --model clef-flash

   This writes `results.html` (the page to review) and `results.json` (Clef's raw answers).
3. Classify the harder set with `clef`:

       python classify.py comments-v2.json --model clef

   This writes `results-v2.html` and `results-v2.json`.
4. To rebuild a page without calling the API again: `python classify.py comments.json --html-only`.

The page shows each comment with Clef's label, confidence and the probability for each
label. You can filter by label, show only low-confidence answers (below 0.5, highlighted),
sort least-confident first, and search.

## Tools and models used

<!-- Fill in yourself: which AI tools you used and for what. -->

## What I felt about doing this

<!-- Fill in yourself. -->
