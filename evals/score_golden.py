"""Compare model records with the hand-labeled golden 50 and write a markdown report.
Labels are read ONLY here, never in prompts, examples, thresholds or issue discovery.

usage: python evals/score_golden.py work/golden/records.jsonl [out.md] [--title "..."] [--held-out evals/heldout_labeled.csv]
Predeclared tolerance: sentiment counts as agreeing when |model - human| <= 0.5 (human scale is -1, -0.5, 0, 0.5, 1).
"""
import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.common import TOPICS, INTENTS  # noqa: E402

SENT_TOL = 0.5


def macro_f1(pairs, classes):
    f = []
    for c in classes:
        tp = sum(g == c and p == c for g, p in pairs)
        fp = sum(g != c and p == c for g, p in pairs)
        fn = sum(g == c and p != c for g, p in pairs)
        if tp + fp + fn:
            f.append(2 * tp / (2 * tp + fp + fn))
    return sum(f) / len(f)


def table(pairs, classes):
    lines = ["| human \\ model | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
    cnt = Counter(pairs)
    for g in classes:
        if any(cnt[(g, p)] for p in classes):
            lines.append(f"| {g} | " + " | ".join(str(cnt[(g, p)] or "") for p in classes) + " |")
    return "\n".join(lines)


def score(rec_path, gold_path, texts_path, title):
    gold = {r["review_id"]: r for r in csv.DictReader(open(gold_path, encoding="utf-8-sig", newline=""))}
    texts = {r["review_id"]: r["review_text"] for r in csv.DictReader(open(texts_path, encoding="utf-8-sig", newline=""))}
    pred = {}
    for line in open(rec_path, encoding="utf-8"):
        d = json.loads(line); pred[d["review_id"]] = d
    done = [i for i in gold if pred.get(i, {}).get("status") == "completed"]
    n = len(gold)
    L = [f"## {title}\n", f"Cases: {n} | model completed: {len(done)} (missing counts as wrong)\n"]
    for field, classes in (("topic", TOPICS), ("intent", INTENTS)):
        pairs = [(gold[i][field], pred[i][field]) for i in done]
        acc = sum(g == p for g, p in pairs) / n
        L.append(f"- **{field}** agreement {acc:.2f} ({sum(g == p for g, p in pairs)}/{n}), macro-F1 {macro_f1(pairs, classes):.2f}")
    sev = [(int(gold[i]["severity"]), pred[i]["severity"]) for i in done]
    L.append(f"- **severity** exact {sum(g == p for g, p in sev) / n:.2f}, within 1 {sum(abs(g - p) <= 1 for g, p in sev) / n:.2f}, MAE {sum(abs(g - p) for g, p in sev) / len(sev):.2f}; model higher/lower than human: {sum(p > g for g, p in sev)}/{sum(p < g for g, p in sev)}")
    sm = [abs(float(gold[i]["sentiment"]) - pred[i]["sentiment"]) for i in done]
    L.append(f"- **sentiment** MAE {sum(sm) / len(sm):.2f}; within predeclared tolerance {SENT_TOL}: {sum(x <= SENT_TOL for x in sm)}/{len(sm)}")
    q = sum(pred[i]["evidence_quote"] in texts[i] for i in done)
    L.append(f"- **evidence_quote** exact substring of source: {q}/{len(done)} (checked in code; whether the quote *supports* the label needs the human read below)")
    hn = {i: gold[i]["needs_review"].strip().lower() == "true" for i in gold}
    tp = sum(hn[i] and pred[i]["needs_review"] for i in done)
    fp = sum((not hn[i]) and pred[i]["needs_review"] for i in done)
    fn = sum(hn[i] and not pred[i]["needs_review"] for i in done)
    L.append(f"- **needs_review** (human flagged {sum(hn.values())} ambiguous cases): model flagged {tp + fp}; caught {tp}, missed {fn}, extra {fp}")
    ents = sum(1 for i in done if pred[i]["entities"])
    L.append(f"- **entities**: model listed entities on {ents}/{len(done)} reviews (inspect for unsupported additions; not scored against human lists)\n")
    L.append("Topic counts (human): " + ", ".join(f"{k} {v}" for k, v in Counter(g["topic"] for g in gold.values()).most_common()))
    L.append("\nTopic confusion:\n\n" + table([(gold[i]["topic"], pred[i]["topic"]) for i in done], TOPICS))
    L.append("\nIntent confusion:\n\n" + table([(gold[i]["intent"], pred[i]["intent"]) for i in done], INTENTS))
    L.append("\nConcrete disagreements (human topic/intent/sev -> model topic/intent/sev):\n")
    for i in done:
        g, p = gold[i], pred[i]
        if (g["topic"], g["intent"], int(g["severity"])) != (p["topic"], p["intent"], p["severity"]):
            L.append(f"- `{i[:8]}` {g['topic']}/{g['intent']}/{g['severity']} -> {p['topic']}/{p['intent']}/{p['severity']} | {texts[i][:140]!r}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    title = "Golden-50 evaluation"
    gold, texts = ROOT / "evals/golden_50_labeled.csv", ROOT / "data/golden_50_to_label.csv"
    if "--title" in sys.argv:
        title = sys.argv[sys.argv.index("--title") + 1]; args = [a for a in args if a != title]
    if "--held-out" in sys.argv:
        gold = Path(sys.argv[sys.argv.index("--held-out") + 1]); args = [a for a in args if a != str(gold)]
        texts = ROOT / "evals/heldout_to_label.csv"
    out = score(args[0], gold, texts, title)
    print(out)
    if len(args) > 1:
        Path(args[1]).write_text(out, encoding="utf-8", newline="\n")
