"""Build exams/<CODE>.json from the verified bank + rule-based generators.
Usage: python tools/build_exam.py ALP-20261006-K7M42 [--neg 0.3333] [--allow-short]
Same code -> same paper (seeded). Only bank items with "verified": true are used.
Generated Maths/Reasoning answers are computed in code, so they are correct by construction."""
import argparse, hashlib, json, random, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
QUOTA = {"Mathematics": 20, "Reasoning": 25, "General Science": 20, "General Awareness": 10}  # CBT-1 pattern

def mk(r, sec, topic, diff, q, ans, wrong, expl):
    opts = [str(ans)] + [x for x in dict.fromkeys(map(str, wrong)) if x != str(ans)][:3]
    if len(opts) < 4: return None
    r.shuffle(opts)
    return dict(id=hashlib.md5(q.encode()).hexdigest()[:10], section=sec, topic=topic, difficulty=diff,
                question=q, options=opts, answer=opts.index(str(ans)), explanation=expl)

def percent(r):
    p, n = r.choice([10, 15, 20, 25, 30, 40, 50]), r.choice(range(120, 2000, 20)); a = n*p//100
    return mk(r, "Mathematics", "Percentage", "Easy", f"What is {p}% of {n}?", a, [a+10, a-10, a*2, a+p], f"{n} × {p}/100 = {a}.")
def simple_int(r):
    P, R, T = r.choice(range(1000, 10001, 500)), r.choice([4, 5, 6, 8, 10]), r.choice([2, 3, 4, 5]); a = P*R*T//100
    return mk(r, "Mathematics", "Simple Interest", "Medium", f"Find the simple interest on Rs {P} at {R}% per annum for {T} years.", a, [a+P//10, a-P//20, a*2, a+R*T], f"SI = P×R×T/100 = {P}×{R}×{T}/100 = {a}.")
def dist(r):
    sp, t = r.choice([36, 45, 54, 60, 72, 90]), r.choice([2, 3, 4, 5]); a = sp*t
    return mk(r, "Mathematics", "Time, Speed & Distance", "Easy", f"A train runs at {sp} km/h. How far does it travel in {t} hours?", f"{a} km", [f"{a+sp} km", f"{a-sp} km", f"{a+10} km"], f"Distance = {sp}×{t} = {a} km.")
def average(r):
    x = [r.randint(10, 60) for _ in range(4)]
    x.append((5 - sum(x) % 5) % 5 + 5*r.randint(2, 12)); a = sum(x)//5
    return mk(r, "Mathematics", "Average", "Easy", f"Find the average of {', '.join(map(str, x))}.", a, [a+1, a-1, a+2, a+5], f"Sum = {sum(x)}; ÷5 = {a}.")
def profit(r):
    cp, pc = r.choice(range(200, 2001, 100)), r.choice([10, 20, 25, 30, 40]); a = cp + cp*pc//100
    return mk(r, "Mathematics", "Profit & Loss", "Medium", f"An article bought for Rs {cp} is sold at {pc}% profit. Find the selling price (Rs).", a, [cp, a+pc, a-pc*2, cp+cp*pc//50], f"SP = {cp}×(100+{pc})/100 = {a}.")
def ratio(r):
    a, b = r.choice([(2, 3), (3, 5), (4, 5), (3, 7), (5, 7), (2, 5)]); k = r.choice(range(20, 200, 10)); big = max(a, b)*k
    return mk(r, "Mathematics", "Ratio & Proportion", "Medium", f"Rs {(a+b)*k} is divided in the ratio {a}:{b}. What is the larger share (Rs)?", big, [min(a, b)*k, big+k, big-k], f"Total parts {a+b}; one part = {k}; larger = {max(a,b)}×{k} = {big}.")
def s_ap(r):
    a, d = r.randint(2, 20), r.randint(2, 9); t = [a+i*d for i in range(5)]
    return mk(r, "Reasoning", "Number Series", "Easy", f"Find the next term: {', '.join(map(str, t[:4]))}, ?", t[4], [t[4]+1, t[4]-1, t[4]+d], f"Common difference {d}; next = {t[4]}.")
def s_gp(r):
    a, m = r.choice([2, 3, 4, 5]), r.choice([2, 3]); t = [a*m**i for i in range(5)]
    return mk(r, "Reasoning", "Number Series", "Medium", f"Find the next term: {', '.join(map(str, t[:4]))}, ?", t[4], [t[3]+t[2], t[4]+m, t[4]-m], f"Each term × {m}; next = {t[4]}.")
def s_sq(r):
    n, k = r.randint(2, 9), r.choice([0, 1, 2, 3]); t = [(n+i)**2+k for i in range(5)]
    return mk(r, "Reasoning", "Number Series", "Medium", f"Find the next term: {', '.join(map(str, t[:4]))}, ?", t[4], [t[4]+2, t[4]-2, t[4]+2*(n+4)+1], f"Terms are squares of {n}, {n+1}, … plus {k}; next = {n+4}² + {k} = {t[4]}.")
def alpha(r):
    d = r.randint(1, 4); s0 = r.randint(0, 25-5*d); L = lambda i: chr(65+s0+i*d)
    return mk(r, "Reasoning", "Alphabet Series", "Easy", f"Find the next letter: {', '.join(L(i) for i in range(4))}, ?", L(4), [chr(ord(L(4))+1), chr(ord(L(4))-1), chr(ord(L(4))+2)], f"Each letter moves +{d}; next = {L(4)}.")
def code_sum(r):
    w = r.choice(["RAIL", "TRAIN", "LOCO", "TRACK", "SIGNAL", "PILOT", "ENGINE", "GUARD"]); a = sum(ord(c)-64 for c in w)
    return mk(r, "Reasoning", "Coding-Decoding", "Medium", f"If A=1, B=2, …, Z=26, what is the sum of letter values of '{w}'?", a, [a+1, a-1, a+3, a-2], " + ".join(f"{c}={ord(c)-64}" for c in w) + f" = {a}.")
GEN = {"Mathematics": [percent, simple_int, dist, average, profit, ratio], "Reasoning": [s_ap, s_gp, s_sq, alpha, code_sum]}

def used_ids(skip):
    ids = set()
    for f in (ROOT/"exams").glob("ALP-*.json"):
        if f.stem != skip: ids |= {q["id"] for q in json.loads(f.read_text(encoding="utf-8"))["questions"]}
    return ids

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("code"); ap.add_argument("--neg", type=float, default=0.0)
    ap.add_argument("--allow-short", action="store_true"); a = ap.parse_args()
    if not re.match(r"^ALP-\d{8}-[A-Z0-9]{5}$", a.code): sys.exit("Bad code format")
    r = random.Random(int(hashlib.sha256(a.code.encode()).hexdigest(), 16))
    bank = [q for q in json.load(open(ROOT/"bank/questions.json", encoding="utf-8")) if q.get("verified") is True]
    for q in bank: q["id"] = hashlib.md5(q["question"].encode()).hexdigest()[:10]
    used, paper = used_ids(a.code), []
    for sec, n in QUOTA.items():
        pool = [q for q in bank if q["section"] == sec]; r.shuffle(pool)
        pool.sort(key=lambda q: q["id"] in used)            # unused first
        got = {q["id"]: q for q in pool[:n]}
        for _ in range(500):
            if len(got) >= n or sec not in GEN: break
            q = r.choice(GEN[sec])(r)
            if q and q["id"] not in used: got.setdefault(q["id"], q)
        got = list(got.values()); r.shuffle(got)
        if len(got) < n:
            msg = f"{sec}: only {len(got)}/{n} verified questions"
            if not a.allow_short: sys.exit("ERROR " + msg + " (add to bank/questions.json or use --allow-short)")
            print("WARNING", msg)
        paper += got
    out = dict(code=a.code, title=f"RRB ALP CBT-1 Mock – {a.code}", duration_minutes=60, marks_per_question=1,
               negative_marking=a.neg, questions=paper)
    (ROOT/"exams"/f"{a.code}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote exams/{a.code}.json with {len(paper)} questions")
main()
