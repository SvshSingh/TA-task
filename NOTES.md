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

Rendered pages (no download needed):
- [results.html](https://htmlpreview.github.io/?https://github.com/SvshSingh/TA-task/blob/main/results.html) (`comments.json`, `clef-flash`)
- [results-v2.html](https://htmlpreview.github.io/?https://github.com/SvshSingh/TA-task/blob/main/results-v2.html) (`comments-v2.json`, `clef`)

## Tools and models used

- **Claude Opus 5.5 (Anthropic), in Claude desktop app:** wrote
  `classify.py` and the HTML report, ran both classifications, committed and pushed the
  code and results, and helped me write the instructions and label descriptions sent to
  Clef. I also used it to understand the task, set up Cloudflare.
- **Cloudflare Workers AI:** `clef-flash` for `comments.json`, `clef` for `comments-v2.json`.
  I used the same criteria for both runs.

## What I felt about doing this

I enjoyed this more than I expected. The coding part went quickly with Claude: I described
what I needed and had a working program and results pages fairly fast. The slowest part was
setting up the Cloudflare account and API token, not the code.

The real work was reading the comments. `clef-flash` was good at obvious spam and crude
insults, but it missed comments that hurt people without using rude words, like the
sexist remark about girls' marks (#27) or "it's in their blood" (#76). The larger `clef`
model handled blunt feedback and quoted abuse better, but it was still fooled the other
way: it flagged a student calling only himself dumb (#7) and a student reporting a slur
(#20). The most worrying miss was v2 #91, which tells people where a girl sits in the lab.
It sounds polite, but it is the most dangerous comment in the set.

The borderline cases made me think the most. I see v2 #23 as a classmate helping others save money, not spam. I also had to decide
how much criticism of the professor's lectures or slides is fair (#98 and v2 #88), and how
sure I could be that #40 was phishing and not the real placement cell. These are judgement
calls with no single right answer, so I tried to explain my reasoning each time.

Overall, this showed me what the TA role involves: AI does the first sort quickly, but a
person still has to read the output carefully, especially the comments that look harmless.
