"""RRB ALP CBT-1 mock test. Run: streamlit run app.py"""
import base64, html, json, math, uuid, random, re, sqlite3, time
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
EXAMS, DB = ROOT / "exams", ROOT / "history.db"
CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{2,60}$")   # letters, digits, - and _ only (blocks path tricks)
NEG_RRB = 1 / 3
SHORT = {"Mathematics": "Maths", "General Science": "Science", "General Awareness": "GA"}
s = st.session_state
st.set_page_config(page_title="RRB ALP CBT-1 Mock", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"]{display:none !important}
.block-container{max-width:100% !important;padding:.8rem 2rem 2rem !important}
.stApp{background:linear-gradient(180deg,#eef2ff 0,#f8fafc 260px)}
h1{font-weight:800 !important;color:#1e3a8a;letter-spacing:-.5px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;background:linear-gradient(90deg,#1e3a8a,#2563eb);
  color:#fff;padding:12px 22px;border-radius:14px;box-shadow:0 4px 14px rgba(30,58,138,.25);margin-bottom:14px}
.topbar .t{font-size:1.25rem;font-weight:700}.topbar .s{font-size:.8rem;opacity:.85}
.pill{display:inline-block;background:rgba(255,255,255,.15);border-radius:10px;padding:6px 16px;margin-left:10px;text-align:center}
.pill b{display:block;font-size:1.5rem;font-variant-numeric:tabular-nums;line-height:1.1}.pill span{font-size:.7rem;opacity:.85}
.pill.low{background:#dc2626;animation:pulse 1s infinite}@keyframes pulse{50%{opacity:.7}}
.qmeta span{background:#e0e7ff;color:#3730a3;border-radius:999px;padding:3px 12px;font-size:.78rem;font-weight:600;margin-right:6px}
.qtext{font-size:1.3rem;font-weight:600;color:#0f172a;margin:12px 0 6px;line-height:1.5}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:14px !important;box-shadow:0 2px 10px rgba(15,23,42,.06)}
div[role="radiogroup"]{gap:10px}
div[role="radiogroup"] label{border:2px solid #e2e8f0;border-radius:12px;padding:12px 16px;background:#f8fafc;width:100%;transition:.15s}
div[role="radiogroup"] label:hover{border-color:#93c5fd;background:#eff6ff}
div[role="radiogroup"] label:has(input:checked){border-color:#2563eb;background:#dbeafe}
div[role="radiogroup"] label p{font-size:1.05rem}
.stButton>button{border-radius:10px;font-weight:600;border:1px solid #cbd5e1;transition:.15s}
.stButton>button:hover{border-color:#2563eb;color:#2563eb;transform:translateY(-1px)}
.stButton>button[kind="primary"]{background:#16a34a;border-color:#16a34a;color:#fff}
.stButton>button[kind="primary"]:hover{background:#15803d;color:#fff}
[data-testid="stMetric"]{background:#fff;border-radius:14px;padding:14px 18px;box-shadow:0 2px 10px rgba(15,23,42,.07);border-left:5px solid #2563eb}
[data-testid="stMetricValue"]{font-weight:800;color:#1e3a8a}
.legend{font-size:.78rem;display:flex;flex-wrap:wrap;gap:8px 14px;margin:2px 0 10px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-1px}
[data-testid="stExpander"]{background:#fff;border-radius:12px}
</style>""", unsafe_allow_html=True)

def normalize(raw, code):
    """Accept {"questions":[...]} or a bare list; tolerate common key/answer styles."""
    if isinstance(raw, list):
        raw = {"questions": raw}
    qs = raw.get("questions") if isinstance(raw, dict) else None
    if not qs:
        raise ValueError("Exam file has no questions.")
    out, ints = [], []
    for n, q in enumerate(qs, 1):
        opts = q.get("options") or q.get("choices")
        if isinstance(opts, dict):
            opts = [opts[k] for k in sorted(opts)]
        text = q.get("question") or q.get("text") or q.get("q")
        if not text or not opts or len(opts) != 4:
            raise ValueError(f"Question {n}: needs question text and exactly 4 options.")
        ans = q.get("answer", q.get("correct_answer", q.get("correct", q.get("correct_option"))))
        if ans is None:
            raise ValueError(f"Question {n}: no answer key found.")
        out.append(dict(question=str(text), options=[str(o) for o in opts], _ans=ans,
                        section=q.get("section") or q.get("subject") or "General",
                        topic=q.get("topic") or q.get("chapter") or q.get("section") or "General",
                        difficulty=q.get("difficulty") or "Medium",
                        explanation=q.get("explanation") or q.get("solution") or "No explanation provided."))
        if isinstance(ans, int) and not isinstance(ans, bool):
            ints.append(ans)
    one_based = bool(ints) and min(ints) >= 1 and max(ints) <= 4 and len(ints) == len(out) and 0 not in ints
    for n, q in enumerate(out, 1):
        a = q.pop("_ans")
        if isinstance(a, int):
            a = a - 1 if one_based else a
        else:
            a = str(a).strip()
            if a.upper() in ("A", "B", "C", "D"):
                a = "ABCD".index(a.upper())
            elif a.isdigit():
                a = int(a) - 1 if one_based else int(a)
            elif a in q["options"]:
                a = q["options"].index(a)
            else:
                raise ValueError(f"Question {n}: answer '{a}' doesn't match any option.")
        if not 0 <= a <= 3:
            raise ValueError(f"Question {n}: answer index out of range.")
        q["answer"] = a
    return dict(code=code, title=raw.get("title", f"RRB ALP CBT-1 Mock - {code}") if isinstance(raw, dict) else code,
                duration_minutes=raw.get("duration_minutes", 60), marks_per_question=raw.get("marks_per_question", 1),
                negative_marking=raw.get("negative_marking", 0.0), questions=out)

def find_exam(code):
    for f in EXAMS.glob("*.json"):
        if f.stem.lower() == code.lower():
            return f

def load_exam(code):
    if not CODE_RE.match(code):
        return None, "Code can contain only letters, numbers, - and _ (e.g. TECH-20260313-S1)."
    f = find_exam(code)
    if not f:
        return None, "No exam found for this code. Pick one from the available exams below."
    try:
        return normalize(json.loads(f.read_text(encoding="utf-8-sig")), f.stem), None
    except (ValueError, json.JSONDecodeError) as e:
        return None, f"Exam file problem: {e}"

# ---------------- history (SQLite, local file history.db) ----------------
def conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, code TEXT, ts TEXT, score REAL, maxscore REAL,"
              " correct INT, wrong INT, skipped INT, accuracy REAL, total_time REAL, neg REAL, detail TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS progress2(sid TEXT PRIMARY KEY, saved REAL, data TEXT)")
    try: c.execute("ALTER TABLE attempts ADD COLUMN name TEXT")
    except sqlite3.OperationalError: pass
    return c

def last_name():
    with conn() as c:
        r = c.execute("SELECT name FROM attempts WHERE name IS NOT NULL AND name != '' ORDER BY id DESC LIMIT 1").fetchone()
    return r[0] if r else ""

def list_exams():
    with conn() as c:
        hist = {r[0]: (r[1], r[2]) for r in c.execute("SELECT code, COUNT(*), MAX(score*100.0/maxscore) FROM attempts GROUP BY code")}
    rows = []
    for f in sorted(EXAMS.glob("*.json"), reverse=True):
        try:
            raw = json.loads(f.read_text(encoding="utf-8-sig"))
            qs = raw if isinstance(raw, list) else raw.get("questions", [])
            dur = 60 if isinstance(raw, list) else raw.get("duration_minutes", 60)
            title = "" if isinstance(raw, list) else raw.get("title", "")
            n, best = hist.get(f.stem, (0, None))
            rows.append({"Code": f.stem, "Questions": len(qs), "Minutes": dur, "Title": title,
                         "Attempts": n, "Best %": round(best, 1) if best is not None else None})
        except (ValueError, OSError):
            rows.append({"Code": f.stem, "Questions": 0, "Minutes": 0, "Title": "⚠ unreadable file", "Attempts": 0, "Best %": None})
    return pd.DataFrame(rows)

def save_attempt(code, m, detail, name):
    with conn() as c:
        c.execute("INSERT INTO attempts(code,ts,score,maxscore,correct,wrong,skipped,accuracy,total_time,neg,detail,name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (code, datetime.now().strftime("%Y-%m-%d %H:%M"), m["score"], m["max"], m["correct"], m["wrong"], m["skipped"],
                   m["accuracy"], m["total_time"], m["neg"], json.dumps(detail), name))

def analyse(exam, answers, qtime):
    Q = exam["questions"]; target = exam["duration_minutes"] * 60 / len(Q)   # benchmark secs per question
    rows, det = [], []
    for i, q in enumerate(Q):
        a, t = answers.get(i), qtime[i]
        if a is None: stt, cat = "Skipped", "Skipped"
        elif a == q["answer"]: stt, cat = "Correct", "Fast & correct" if t <= target else "Slow & correct"
        else: stt, cat = "Wrong", "Slow & wrong" if t > target else "Fast & wrong"
        rows.append(dict(No=i+1, Section=q["section"], Topic=q["topic"], Difficulty=q["difficulty"], Status=stt, Category=cat, Time=round(t, 1)))
        det.append(dict(q, user=a, Status=stt, Category=cat, time=round(t, 1)))
    return pd.DataFrame(rows), det, target

def clean(t):
    for a, b in {"×": "x", "÷": "/", "–": "-", "—": "-", "…": "...", "’": "'", "‘": "'", "“": '"', "”": '"', "₹": "Rs ",
                 "≤": "<=", "≥": ">=", "°": " deg", "²": "^2", "³": "^3", "√": "sqrt"}.items():
        t = str(t).replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")

def make_pdf(title, summary, sec, top, det):
    from fpdf import FPDF
    pdf = FPDF(); pdf.set_auto_page_break(True, 15); pdf.add_page()
    def w(txt, size=10, bold=False, font="Helvetica"):
        pdf.set_font(font, "B" if bold else "", size); pdf.multi_cell(0, 5.5, clean(txt), new_x="LMARGIN", new_y="NEXT")
    w(title, 15, True); w(summary); pdf.ln(2)
    w("Section-wise", 12, True); w(sec.to_string(index=False), 8, font="Courier"); pdf.ln(2)
    w("Topic-wise", 12, True); w(top.to_string(index=False), 8, font="Courier"); pdf.ln(3)
    w("Question-wise analysis", 12, True)
    for i, d in enumerate(det, 1):
        you = d["options"][d["user"]] if d["user"] is not None else "Not attempted"
        w(f"Q{i} [{d['Status']}] {d['section']} / {d['topic']} / {d['difficulty']} / {d['time']}s", 10, True)
        w(d["question"]); w(f"Your answer: {you}"); w(f"Correct answer: {d['options'][d['answer']]}"); w(f"Explanation: {d['explanation']}"); pdf.ln(2)
    return bytes(pdf.output())

def start(exam, name=None):
    n, now = len(exam["questions"]), time.time()
    s.update(exam=exam, answers={}, marked=set(), visited={0}, qtime=[0.0]*n, cur=0, last=now, start=now,
             submitted=False, end=None, saved=False, confirm=False, name=name or last_name() or "Candidate")
    s.pop("pending", None)

def flush():
    now = time.time(); s.qtime[s.cur] += now - s.last; s.last = now

def goto(i):
    flush(); s.cur = i; s.visited.add(i)

def sid():
    """Private id kept in the page URL (?sid=...). A refresh keeps it; other visitors get their own."""
    if "sid" not in s:
        q = st.query_params.get("sid", "")
        if not re.fullmatch(r"[A-Za-z0-9]{8,32}", q or ""):
            q = uuid.uuid4().hex[:16]; st.query_params["sid"] = q
        s.sid = q
    return s.sid

def inprog_save():
    qt = list(s.qtime); qt[s.cur] += time.time() - s.last
    data = dict(exam=s.exam, answers=s.answers, marked=sorted(s.marked), visited=sorted(s.visited),
                qtime=qt, cur=s.cur, start=s.start, name=s.name)
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO progress2(sid, saved, data) VALUES(?, ?, ?)", (sid(), time.time(), json.dumps(data)))

def inprog_load():
    with conn() as c:
        r = c.execute("SELECT data FROM progress2 WHERE sid = ?", (sid(),)).fetchone()
    return json.loads(r[0]) if r else None

def inprog_clear():
    with conn() as c: c.execute("DELETE FROM progress2 WHERE sid = ?", (sid(),))

def submit():
    if not s.submitted:
        flush(); s.submitted = True; s.end = time.time(); inprog_clear()

def resume(d):
    s.update(exam=d["exam"], answers={int(k): v for k, v in d["answers"].items()}, marked=set(d["marked"]),
             visited=set(d["visited"]), qtime=d["qtime"], cur=d["cur"], last=time.time(), start=d["start"],
             submitted=False, end=None, saved=False, confirm=False, name=d["name"])
    s.pop("pending", None)
    if time.time() - d["start"] >= d["exam"]["duration_minutes"] * 60:
        submit()          # time ran out while the page was closed

def save_answer(i):
    v = s.get(f"opt{i}")
    if v is not None: s.answers[i] = v

# ---------------- progress & practice page ----------------
def do_clear(scope):
    with conn() as c:
        if scope.startswith("Everything"):
            n = c.execute("DELETE FROM attempts").rowcount
        else:
            n = c.execute("DELETE FROM attempts WHERE code = ?", (scope.split(": ", 1)[1],)).rowcount
    s.clear_sure = False; s.clear_scope = "Everything (all attempts and scores)"
    s.hist_msg = f"Deleted {n} attempt{'s' if n != 1 else ''}."

def clear_panel(att):
    st.divider()
    with st.container(border=True, key="clearbox"):
        st.markdown("#### 🗑 Clear history")
        st.caption("Deletes saved attempts, scores and progress from history.db. Your exam files are not touched.")
        scope = st.selectbox("What to clear", ["Everything (all attempts and scores)"] + [f"Only exam: {c}" for c in sorted(att.code.unique())],
                             key="clear_scope")
        sure = st.checkbox("I understand this cannot be undone", key="clear_sure")
        st.button("Delete selected history", disabled=not sure, key="clear_btn", on_click=do_clear, args=(scope,))

def progress():
    if s.get("hist_msg"): st.success(s.pop("hist_msg"))
    with conn() as c:
        att = pd.read_sql("SELECT * FROM attempts ORDER BY id", c)
    if att.empty:
        st.info("No attempts yet. Finish a test and it will appear here."); return
    _progress(att)
    clear_panel(att)

def _progress(att):
    real = att[att.code != "PRACTICE"].copy()
    if not real.empty:
        real["Score %"] = (100 * real.score / real.maxscore).round(1)
        m = st.columns(4)
        m[0].metric("Tests taken", len(real)); m[1].metric("Average score", f"{real['Score %'].mean():.1f}%")
        m[2].metric("Best score", f"{real['Score %'].max():.1f}%"); m[3].metric("Avg accuracy", f"{real.accuracy.mean():.1f}%")
        st.caption("Score % and accuracy % across your tests (oldest to newest)")
        st.line_chart(real.reset_index(drop=True).rename(columns={"accuracy": "Accuracy %"})[["Score %", "Accuracy %"]])
        rows = [dict(topic=d["topic"], ok=d["Status"] == "Correct") for dj in real.detail for d in json.loads(dj)]
        t = pd.DataFrame(rows).groupby("topic").ok.agg(Questions="count", Correct="sum").reset_index()
        t["Accuracy %"] = (100 * t.Correct / t.Questions).round(1)
        t = t.sort_values("Accuracy %")
        st.subheader("Topics across all tests (weakest first)")
        st.dataframe(t, width="stretch", hide_index=True)
        weak = t[(t.Questions >= 3) & (t["Accuracy %"] < 50)].topic.tolist()
        st.error("Persistently weak (<50%, 3+ questions): " + (", ".join(weak) or "none"))
        st.subheader("History")
        st.dataframe(real[["ts", "code", "score", "maxscore", "correct", "wrong", "skipped", "accuracy"]].iloc[::-1],
                     width="stretch", hide_index=True)
    latest = {}
    for dj in att.detail:                       # latest result per question wins
        for d in json.loads(dj): latest[d["question"]] = d
    pool = [d for d in latest.values() if d["Status"] != "Correct" or d["Category"] == "Slow & correct"]
    st.subheader("🎯 Practice my wrong, skipped & slow questions")
    if not pool:
        st.success("Nothing to revise. Everything was answered correctly and quickly."); return
    n = st.number_input("How many questions?", 1, len(pool), min(30, len(pool)))
    if st.button(f"Start practice ({n} of {len(pool)} pending)", type="primary"):
        random.shuffle(pool)
        qs = [{k: d[k] for k in ("question", "options", "answer", "section", "topic", "difficulty", "explanation")} for d in pool[:n]]
        start(dict(code="PRACTICE", title="Practice: my wrong & slow questions", duration_minutes=max(5, math.ceil(n * 0.8)),
                   marks_per_question=1, negative_marking=0.0, questions=qs)); st.rerun()

st.markdown("""<style>
.hero{background:linear-gradient(120deg,#1e3a8a,#2563eb 60%,#06b6d4);color:#fff;border-radius:18px;padding:26px 32px;margin-bottom:18px;box-shadow:0 8px 24px rgba(37,99,235,.28)}
.hero h1{color:#fff !important;margin:0;font-size:2rem}.hero p{margin:6px 0 0;opacity:.92}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 18px}
.tiles div{flex:1;min-width:170px;background:#fff;border-radius:14px;padding:14px 16px;box-shadow:0 2px 10px rgba(15,23,42,.07);border-top:4px solid #2563eb;font-size:.9rem;color:#475569}
.tiles b{display:block;color:#1e3a8a;font-size:1rem;margin-bottom:2px}
.chip{display:inline-block;background:#e0e7ff;color:#3730a3;border-radius:999px;padding:3px 12px;font-size:.8rem;font-weight:600;margin:0 6px 6px 0}
.stTabs [data-baseweb="tab"]{font-weight:600;font-size:1rem}
.stTextInput input,[data-baseweb="select"]>div{border-radius:10px !important}
.inst li{margin-bottom:.45rem;line-height:1.55}
</style>""", unsafe_allow_html=True)

FS_HTML = """<style>body{margin:0}button{width:100%;height:38px;border:none;border-radius:999px;cursor:pointer;font:600 14px Poppins,Segoe UI,sans-serif;
color:#fff;background:linear-gradient(90deg,#4338ca,#0ea5e9);box-shadow:0 3px 10px rgba(67,56,202,.3)}button:hover{filter:brightness(1.1)}</style>
<button id="b">⛶ Full screen</button>
<script>
const d = window.parent.document, b = document.getElementById('b');
const upd = () => { b.textContent = d.fullscreenElement ? '🗗 Exit full screen' : '⛶ Full screen'; };
b.onclick = () => { try { d.fullscreenElement ? d.exitFullscreen() : d.documentElement.requestFullscreen(); }
                    catch (e) { b.textContent = 'Press F11 for full screen'; } };
d.addEventListener('fullscreenchange', upd); upd();
window.addEventListener('pagehide', () => d.removeEventListener('fullscreenchange', upd));
</script>"""

def fs_button():
    if hasattr(st, "iframe"): st.iframe(FS_HTML, height=46)      # newer Streamlit
    else: components.html(FS_HTML, height=46)                    # older Streamlit

def _svg_doc(body, label):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 390 112" width="390" height="112"><defs>'
            '<pattern id="sl" width="13" height="6" patternUnits="userSpaceOnUse"><rect width="8" height="6" fill="#4a382b"/></pattern>'
            '<linearGradient id="glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e0f2fe"/><stop offset="1" stop-color="#6cb8e6"/></linearGradient>'
            '<linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".5"/>'
            '<stop offset=".45" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".30"/></linearGradient></defs>'
            '<rect x="382" y="5" width="4" height="84" fill="#7b8794"/><rect x="368" y="7" width="30" height="3" fill="#7b8794"/>'
            '<line x1="0" y1="9" x2="390" y2="9" stroke="#cbd5e1" stroke-width="1.6"/>'
            '<rect x="0" y="86" width="390" height="14" fill="#7a6e62"/><rect x="0" y="88" width="390" height="6" fill="url(#sl)"/>'
            '<rect x="0" y="85.5" width="390" height="2.4" fill="#d5dbe3"/><rect x="0" y="87.9" width="390" height="1" fill="#59606b"/>'
            '<rect x="0" y="100" width="390" height="12" fill="#2e2620"/>' + body +
            f'<text x="195" y="109.5" text-anchor="middle" font-family="Lora,Georgia,serif" font-size="10" font-weight="700" fill="#f3d9a0">{label}</text></svg>')
def _bogie(x, axles=3):
    out = f'<rect x="{x-6}" y="75" width="{axles*19+2}" height="8" rx="3" fill="#1f2937"/>'
    for i in range(axles):
        cx = x + 6 + i * 19
        out += f'<circle cx="{cx}" cy="79" r="7.5" fill="#111827"/><circle cx="{cx}" cy="79" r="5" fill="#374151"/><circle cx="{cx}" cy="79" r="2" fill="#9ca3af"/>'
    return out
def _pan(x):
    return (f'<rect x="{x}" y="30" width="26" height="3.5" fill="#64748b"/>'
            f'<path d="M{x+3} 30 L{x+14} 15 L{x+23} 30 M{x+9} 23 L{x+20} 23 M{x+14} 15 V11" stroke="#e5e7eb" stroke-width="2.2" fill="none" stroke-linejoin="round"/>'
            f'<rect x="{x+3}" y="8" width="22" height="3" rx="1.5" fill="#f1f5f9"/>')
def _louvres(x0, x1, step, y, h, dark, light):
    return "".join(f'<rect x="{x}" y="{y}" width="9" height="{h}" rx="1.5" fill="{dark}"/>'
                   + "".join(f'<rect x="{x+1}" y="{y+2+k*4}" width="7" height="1.2" fill="{light}"/>' for k in range((h - 3) // 4))
                   for x in range(x0, x1, step))
def _svg_wag12b():      # heavy electric freight locomotive: twin cabs, two pantographs, two 3-axle bogies
    return _svg_doc('<path d="M10 76 V40 Q10 33 18 33 H272 Q280 33 280 40 V76 Z" fill="#1e4fbf"/>'
                    '<rect x="10" y="60" width="270" height="6" fill="#f59e0b"/><rect x="10" y="67" width="270" height="2" fill="#fff" opacity=".85"/>'
                    '<rect x="128" y="27" width="22" height="7" rx="1" fill="#475569"/>'
                    + _louvres(62, 250, 15, 41, 19, "#12306b", "#4f78c9") +
                    '<rect x="20" y="38" width="30" height="15" rx="3" fill="url(#glass)" stroke="#0f2a63" stroke-width="2"/>'
                    '<rect x="242" y="38" width="30" height="15" rx="3" fill="url(#glass)" stroke="#0f2a63" stroke-width="2"/>'
                    '<path d="M10 76 V40 Q10 33 18 33 H272 Q280 33 280 40 V76 Z" fill="url(#shade)"/>'
                    '<rect x="10" y="74" width="270" height="3" fill="#1f2937"/>'
                    '<circle cx="14" cy="66" r="3" fill="#fde68a"/><circle cx="276" cy="66" r="3" fill="#fde68a"/>'
                    '<rect x="3" y="70" width="8" height="5" fill="#9ca3af"/><rect x="279" y="70" width="8" height="5" fill="#9ca3af"/>'
                    + _pan(86) + _pan(170) + _bogie(36) + _bogie(204), "WAG-12B · Freight")
def _svg_wap9():        # streamlined high-speed passenger locomotive
    body = "M10 76 V40 Q10 33 18 33 H206 Q252 34 286 60 L290 76 Z"
    return _svg_doc(f'<path d="{body}" fill="#f1f5f9"/><path d="M10 58 H282 L288 66 H10 Z" fill="#1d4ed8"/><path d="M10 66 H288 L289 70 H10 Z" fill="#f59e0b"/>'
                    + _louvres(62, 196, 13, 39, 17, "#94a3b8", "#e2e8f0") +
                    '<path d="M222 38 Q254 40 272 56 H222 Z" fill="#0f172a"/><path d="M227 41 Q248 43 262 52" stroke="#64748b" stroke-width="1.5" fill="none"/>'
                    '<rect x="20" y="38" width="26" height="14" rx="3" fill="url(#glass)" stroke="#475569" stroke-width="1.6"/>'
                    f'<path d="{body}" fill="url(#shade)"/><rect x="10" y="74" width="278" height="3" fill="#1f2937"/>'
                    '<circle cx="285" cy="66" r="3" fill="#fde68a"/><rect x="3" y="70" width="8" height="5" fill="#9ca3af"/>'
                    + _pan(112) + _bogie(34) + _bogie(196), "WAP-9 · Express")
def _svg_mmts():        # suburban electric multiple unit: three coaches with a driving cab at the front
    body = ""
    for i in range(3):
        x = 6 + i * 121; last = i == 2
        shape = (f"M{x} 76 V39 Q{x} 34 {x+6} 34 H{x+108} Q{x+124} 36 {x+126} 58 V76 Z" if last
                 else f"M{x} 76 V39 Q{x} 34 {x+6} 34 H{x+112} Q{x+118} 34 {x+118} 39 V76 Z")
        body += f'<path d="{shape}" fill="#f5c518"/><rect x="{x}" y="60" width="{126 if last else 118}" height="7" fill="#1e40af"/>'
        body += f'<rect x="{x+8}" y="29" width="{100 if not last else 90}" height="5" rx="2" fill="#cbd5e1"/><rect x="{x+30}" y="26" width="24" height="4" rx="1" fill="#94a3b8"/>'
        body += "".join(f'<rect x="{x+9+j*20}" y="40" width="14" height="14" rx="2" fill="url(#glass)" stroke="#1e3a8a" stroke-width="1.8"/>' for j in range(5 if not last else 4))
        if last: body += f'<path d="M{x+88} 38 H{x+108} Q{x+119} 39 {x+120} 52 H{x+88} Z" fill="#0f172a"/><circle cx="{x+122}" cy="64" r="3" fill="#fde68a"/>'
        body += f'<path d="{shape}" fill="url(#shade)"/><rect x="{x}" y="74" width="{118}" height="3" fill="#1f2937"/>'
        body += _bogie(x + 14, 2) + _bogie(x + 70, 2)
        if not last: body += f'<rect x="{x+118}" y="62" width="9" height="5" fill="#1f2937"/>'
    return _svg_doc(body + _pan(6 + 121 + 48), "MMTS · Suburban")
def _uri(svg): return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
def _hill_uri(color, y0, amp):
    d = f"M0 {y0} Q75 {y0-amp} 150 {y0-amp//3} T300 {y0-amp//2} T450 {y0-amp*2//3} T600 {y0} V140 H0Z"
    return _uri(f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="140" viewBox="0 0 600 140"><path d="{d}" fill="{color}"/></svg>')
def _cloud_uri():
    g = "".join(f'<g fill="#fff" opacity=".85"><ellipse cx="{x}" cy="{y}" rx="{w}" ry="{w//3}"/><ellipse cx="{x+w//2}" cy="{y-8}" rx="{w//2}" ry="{w//4}"/>'
                f'<ellipse cx="{x-w//2}" cy="{y-4}" rx="{w//2}" ry="{w//5}"/></g>' for x, y, w in [(120, 40, 60), (430, 72, 80), (720, 36, 55)])
    return _uri(f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="120" viewBox="0 0 900 120">{g}</svg>')

@st.cache_data(show_spinner=False)
def _photo_strip(sig):
    """Header from the images in assets/. Large files are shrunk first so the page stays fast."""
    import io
    from PIL import Image, ImageOps
    H, GAP, SPEED = 150, 44, 55           # picture height (px), space between pictures (px), scroll speed (px/s)
    items, setw = [], 0
    for name, _ in sig:
        f = ROOT / "assets" / name
        try:
            im = ImageOps.exif_transpose(Image.open(f))
            cut = im.mode in ("RGBA", "LA", "P") and im.convert("RGBA").getchannel("A").getextrema()[0] < 250   # transparent background?
            im = im.convert("RGBA" if cut else "RGB"); im.thumbnail((3000, H * 2))
        except Exception:
            continue                       # unreadable image: skip it
        w = max(1, round(H * im.width / im.height)); buf = io.BytesIO()
        im.save(buf, "PNG" if cut else "JPEG", **({"optimize": True} if cut else {"quality": 82, "optimize": True}))
        cap = html.escape(re.sub(r"^\d+[\s_\-]*", "", f.stem).replace("_", " ").replace("-", " ").strip().upper())
        mime = "png" if cut else "jpeg"
        items.append(f"<figure class='{'cut' if cut else 'ph'}' style='width:{w}px'><img src='data:image/{mime};base64,{base64.b64encode(buf.getvalue()).decode()}' "
                     f"style='width:{w}px;height:{H}px'/><figcaption>{cap}</figcaption></figure>")
        setw += w + GAP
    if not items: return ""
    reps = min(12, max(2, -(-2800 // setw) + 1))
    return (f"<div class='pstrip'><div class='pmv' style='--setw:{setw}px;animation-duration:{setw / SPEED:.0f}s'>"
            + "".join(items) * reps + "</div></div>")

def train_strip():
    """Your own photos (assets/*.jpg|png|webp) if present, otherwise the animated train scene."""
    adir = ROOT / "assets"
    pics = sorted(f for f in adir.glob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")) if adir.is_dir() else []
    strip = _photo_strip(tuple((f.name, f.stat().st_mtime) for f in pics[:8])) if pics else ""
    if strip: return strip
    imgs = "".join(f"<img class='tr' src='{_uri(f())}'/>" for f in (_svg_wag12b, _svg_wap9, _svg_mmts)) * 4
    return f"<div class='rail'><div class='mv'>{imgs}</div></div>"

CAPTIONS = ["Every mock test brings you one step closer to the Loco Pilot’s cab.",
            "Discipline today, a railway career tomorrow.",
            "Practise with patience, succeed with confidence.",
            "Your journey to the Indian Railways starts with the next question."]

THEME_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');
.stApp{background:repeating-linear-gradient(135deg,rgba(200,150,46,.05) 0 2px,transparent 2px 15px),
  radial-gradient(900px 380px at 50% -80px,#ffe3a6 0,transparent 70%),linear-gradient(180deg,#fff1d3 0,#fffaf0 420px,#fbf5e8 100%) !important}
.stApp::after{content:"";position:fixed;left:0;right:0;bottom:0;height:9px;z-index:99;pointer-events:none;border-top:2px solid #cfd6df;
  background:repeating-linear-gradient(90deg,#5b4636 0 12px,#8a6a4a 12px 16px)}
h1,h2,h3,.stApp h1,.stApp h2,.stApp h3,.ecode{font-family:'Playfair Display',Georgia,serif !important;color:#0b2a4a}
.qtext{font-family:'Lora',Georgia,serif !important;color:#1c1917}
.hero{position:relative;overflow:hidden;border-radius:22px;padding:34px 40px 0 !important;margin-bottom:22px;border:2px solid #c8962e;
  animation:none !important;box-shadow:0 14px 34px rgba(11,42,74,.35);
  background:radial-gradient(circle at 80% 90%,#fff6c9 0,rgba(255,220,130,.8) 7%,rgba(255,170,80,.35) 20%,transparent 42%),
             linear-gradient(180deg,#0b2a4a 0%,#244f7d 34%,#e9a15f 76%,#ffd9a0 100%) !important}
.hero:after{content:none !important}
.clouds,.hills{position:absolute;left:0;right:0;pointer-events:none}
.clouds{top:0;height:130px;background:url("__CLOUDS__") repeat-x 0 14px;background-size:900px 120px;opacity:.55;animation:drift1 170s linear infinite}
.hills{height:140px}
.hills.far{bottom:44px;background:url("__FAR__") repeat-x bottom;background-size:600px 140px;opacity:.7;animation:drift2 240s linear infinite}
.hills.near{bottom:26px;background:url("__NEAR__") repeat-x bottom;background-size:600px 140px;animation:drift2 130s linear infinite}
@keyframes drift1{to{background-position-x:-900px}}@keyframes drift2{to{background-position-x:-600px}}
.htxt{position:relative;z-index:3}
.hero h1{color:#fff9ea !important;font-size:2.5rem !important;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.hero p{color:#ffe9bf;font-size:1.05rem;text-shadow:0 1px 6px rgba(0,0,0,.5)}
.caps{position:relative;height:28px;margin-top:8px}
.caps span{position:absolute;left:0;top:0;opacity:0;color:#fff4d6;font:italic 1.08rem 'Lora',Georgia,serif;text-shadow:0 1px 6px rgba(0,0,0,.55);animation:cap 20s infinite}
@keyframes cap{0%{opacity:0;transform:translateY(8px)}3%,22%{opacity:1;transform:none}27%,100%{opacity:0}}
.rail{position:relative;z-index:4;overflow:hidden;height:112px;margin:10px -40px 0}
.mv{display:flex;width:max-content;animation:drive 45s linear infinite}.tr{display:block;flex:none;height:112px;width:390px}
@keyframes drive{from{transform:translateX(-25%)}to{transform:translateX(0)}}
@media (prefers-reduced-motion:reduce){.mv,.pmv,.clouds,.hills{animation:none}}
.pstrip{position:relative;z-index:4;margin:10px -40px 0;overflow:hidden}
.pstrip:after{content:"";display:block;height:20px;border-bottom:6px solid #2e2620;
  background:repeating-linear-gradient(90deg,#4a382b 0 8px,transparent 8px 13px),linear-gradient(180deg,#d5dbe3 0 3px,#7a6e62 3px 100%)}
.pmv{display:flex;align-items:flex-end;width:max-content;padding-top:8px;animation:pdrive linear infinite}
.pstrip:hover .pmv{animation-play-state:paused}
@keyframes pdrive{from{transform:translateX(calc(-1 * var(--setw)))}to{transform:translateX(0)}}
.pmv figure{margin:0 44px 0 0;flex:none}.pmv img{display:block;object-fit:cover}
.pmv .ph img{border-radius:12px;border:2px solid #c8962e;box-shadow:0 6px 16px rgba(0,0,0,.4)}
.pmv .cut img{object-fit:contain;filter:drop-shadow(0 6px 5px rgba(0,0,0,.45))}
.pmv figcaption{margin:6px auto 4px;width:max-content;max-width:100%;font:700 .68rem 'Lora',Georgia,serif;letter-spacing:.8px;color:#3b2a0a;
  background:linear-gradient(180deg,#f3d9a0,#c8962e);border-radius:5px;padding:2px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.topbar{background:linear-gradient(90deg,#0b2a4a,#14467a) !important;border-bottom:3px solid #c8962e;box-shadow:0 4px 14px rgba(11,42,74,.3) !important}
.stats div{border:1px solid #ecdcb8;border-top:4px solid #c8962e;background:rgba(255,253,246,.9)}
.stats span{background:none !important;-webkit-text-fill-color:#0b2a4a;color:#0b2a4a;font-family:'Playfair Display',serif}
.tag{background:#c8962e !important;color:#fff !important}
.stTabs [aria-selected="true"]{background:#0b2a4a !important}
.stTabs button[data-baseweb="tab"]{border:1px solid #ecdcb8}
[data-testid="stMetric"]{border-left:5px solid #c8962e !important;background:#fffdf8}
[data-testid="stMetricValue"]{color:#0b2a4a !important;font-family:'Playfair Display',serif}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fffdf8 !important;border:1px solid #ecdcb8 !important}
.qmeta span,.chip{background:#fdeccd !important;color:#7a4b0b !important}
div[role="radiogroup"] label{background:#fffaf0;border-color:#ecdcb8}
div[role="radiogroup"] label:hover{border-color:#c8962e;background:#fff3d6}
div[role="radiogroup"] label:has(input:checked){border-color:#c8962e !important;background:#ffefc2 !important}
.stButton>button:hover{border-color:#0b2a4a;color:#0b2a4a}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,#2e7d32,#1b5e20);border:none}
.stButton>button[kind="primary"]:hover{color:#fff;filter:brightness(1.1)}
[data-testid='stFileUploaderDropzone']{border:2px dashed #c8962e !important;background:#fff7e0 !important}
</style>"""

st.markdown(THEME_CSS.replace("__CLOUDS__", _cloud_uri()).replace("__FAR__", _hill_uri("#5d7ea6", 80, 46))
            .replace("__NEAR__", _hill_uri("#2f5a45", 96, 40)), unsafe_allow_html=True)

def _mini_train():
    return _uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 22" width="52" height="22"><rect x="2" y="3" width="40" height="13" rx="3" fill="#1e4fbf"/>'
                '<path d="M38 3 H44 Q50 5 51 16 H38Z" fill="#f1f5f9"/><rect x="8" y="6" width="9" height="5" rx="1" fill="#bae6fd"/><rect x="22" y="6" width="9" height="5" rx="1" fill="#bae6fd"/>'
                '<rect x="2" y="12" width="48" height="2.5" fill="#f59e0b"/>' + "".join(f'<circle cx="{x}" cy="18" r="3" fill="#111827"/>' for x in (12, 22, 34, 44)) + '</svg>')

STATION_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
/* departure-board stat tiles */
.stats div{background:#0f1b2d !important;border:2px solid #c8962e !important;border-radius:10px !important;color:#9fb3c8 !important;
  text-transform:uppercase;letter-spacing:.14em;font-size:.68rem !important;box-shadow:inset 0 0 0 3px #0f1b2d,inset 0 0 0 4px rgba(200,150,46,.45)}
.stats span{-webkit-text-fill-color:#ffb703 !important;color:#ffb703 !important;font-family:'Share Tech Mono',monospace !important;font-size:2rem !important;
  letter-spacing:2px;text-shadow:0 0 10px rgba(255,183,3,.6)}
/* signboard tabs */
.stTabs [data-baseweb="tab-list"]{gap:6px}
.stTabs button[data-baseweb="tab"]{border-radius:6px 6px 0 0 !important;background:#0b2a4a !important;border:none !important;padding:10px 22px !important;box-shadow:none}
.stTabs button[data-baseweb="tab"] p{color:#e9dfc7 !important;font-weight:700;letter-spacing:.4px}
.stTabs button[aria-selected="true"]{background:#c8962e !important;box-shadow:inset 0 -4px 0 #ffd77a !important}
.stTabs button[aria-selected="true"] p{color:#0b2a4a !important}
.stApp h3{border-bottom:2px solid #ecdcb8;padding-bottom:.25rem}
/* buttons: enamel-plate look (zero-specificity base so keyed colours still win) */
:where(.stApp .stButton) > button:not([kind="primary"]){border:2px solid #0b2a4a;border-radius:8px;font-weight:700;letter-spacing:.3px;background:#fffaf0;color:#0b2a4a}
:where(.stApp .stButton) > button:not([kind="primary"]):hover{box-shadow:0 4px 10px rgba(11,42,74,.25)}
/* ticket cards */
[class*="st-key-tk_"]{background:linear-gradient(180deg,#fff9e6,#fff3d1) !important;border:2px solid #c8962e !important;border-radius:14px !important}
.tk-h{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.tk-t{font:700 .66rem 'Lora',Georgia,serif;letter-spacing:.18em;color:#7a4b0b}
.stamp{margin-left:auto;font:700 .66rem 'Lora',Georgia,serif;border:2px solid;border-radius:6px;padding:1px 8px;transform:rotate(-6deg);letter-spacing:.1em}
.stamp.new{color:#2e7d32;border-color:#2e7d32}.stamp.done{color:#b45309;border-color:#b45309}
.tk-row{display:flex;margin:10px 0 4px;border:1px solid #ecdcb8;border-radius:8px;overflow:hidden;background:#fffdf5}
.tk-row div{flex:1;text-align:center;padding:6px 4px;border-right:1px dashed #d9c08a}.tk-row div:last-child{border:none}
.tk-row small{display:block;font-size:.58rem;letter-spacing:.14em;color:#8a6a3a}.tk-row b{font:400 1.3rem 'Share Tech Mono',monospace;color:#0b2a4a}
.tk-perf{position:relative;border-top:2px dashed #c8962e;margin:14px -18px 12px}
.tk-perf:before,.tk-perf:after{content:"";position:absolute;top:-11px;width:20px;height:20px;border-radius:50%;background:#fbf4e2}
.tk-perf:before{left:-12px}.tk-perf:after{right:-12px}
/* notice-board instructions */
.inst{list-style:none;padding-left:0;counter-reset:i}.inst li{counter-increment:i;position:relative;padding-left:46px;min-height:32px}
.inst li:before{content:counter(i);position:absolute;left:0;top:-2px;width:32px;height:32px;border-radius:50%;background:#0b2a4a;color:#ffd77a;
  font:700 .95rem 'Playfair Display',serif;display:grid;place-items:center;box-shadow:0 0 0 3px #ecdcb8}
/* departure-board exam header */
.topbar{background:#0f1b2d !important;border:2px solid #c8962e;border-radius:10px !important;
  box-shadow:inset 0 0 0 3px #0f1b2d,inset 0 0 0 4px rgba(200,150,46,.45),0 6px 16px rgba(0,0,0,.3) !important}
.topbar .t{font-family:'Playfair Display',serif;color:#ffe9bf}.topbar .s{color:#9fb3c8}
.pill{background:#060b14 !important;border:2px solid #3a4658;border-radius:8px}
.pill b{font-family:'Share Tech Mono',monospace;color:#ffb703;text-shadow:0 0 9px rgba(255,183,3,.7);letter-spacing:2px}
.pill span{color:#8da2b8}.pill.low{background:#2a0a0a !important;border-color:#ff4d3d}
.pill.low b{color:#ff4d3d;text-shadow:0 0 10px rgba(255,77,61,.85)}
/* ruled exam paper */
.st-key-qcard{background:repeating-linear-gradient(180deg,transparent 0 33px,rgba(11,42,74,.07) 33px 34px),#fffef9 !important}
.qmeta span:first-child{background:#0b2a4a !important;color:#ffd77a !important}
</style>"""
st.markdown(STATION_CSS, unsafe_allow_html=True)

def hero(title, sub):
    _, c = st.columns([9, 1.2])
    with c: fs_button()
    caps = "".join(f"<span style='animation-delay:{i*5}s'>{html.escape(t)}</span>" for i, t in enumerate(CAPTIONS))
    st.markdown(f"<div class='hero'><div class='clouds'></div><div class='hills far'></div><div class='hills near'></div>"
                f"<div class='htxt'><h1>{title}</h1><p>{sub}</p><div class='caps'>{caps}</div></div>{train_strip()}</div>", unsafe_allow_html=True)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
.stApp{background:radial-gradient(circle at 8% 0%,#c7d2fe 0,transparent 38%),radial-gradient(circle at 95% 8%,#a5f3fc 0,transparent 32%),
  radial-gradient(circle at 60% 100%,#fbcfe8 0,transparent 35%),#f8fafc}
.stApp p,.stApp h1,.stApp h2,.stApp h3,.stApp label,.stApp li,.stApp button,.stApp input,.qtext{font-family:'Poppins',sans-serif}
.hero{position:relative;overflow:hidden;background:linear-gradient(115deg,#1e1b4b,#4338ca 45%,#0ea5e9,#4338ca);background-size:250% 100%;
  animation:flow 12s ease infinite;padding:38px 40px;border-radius:22px;box-shadow:0 14px 34px rgba(67,56,202,.30);margin-bottom:20px}
@keyframes flow{50%{background-position:100% 0}}
.hero:after{content:"🚆";position:absolute;right:38px;top:50%;transform:translateY(-50%);font-size:5.5rem;opacity:.22}
.hero h1{font-size:2.3rem !important;font-weight:800 !important;letter-spacing:-.5px}.hero p{font-size:1.02rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:0 0 20px}
.stats div{background:rgba(255,255,255,.78);backdrop-filter:blur(6px);border:1px solid #e0e7ff;border-radius:16px;padding:14px 18px;color:#64748b;font-size:.85rem;font-weight:500}
.stats span{display:block;font-size:1.9rem;font-weight:800;background:linear-gradient(90deg,#4338ca,#0ea5e9);-webkit-background-clip:text;background-clip:text;color:transparent}
.stTabs [data-baseweb="tab-list"]{gap:8px;border:none}
.stTabs [data-baseweb="tab"]{background:#fff;border-radius:999px;padding:8px 20px;box-shadow:0 1px 4px rgba(15,23,42,.08)}
.stTabs [aria-selected="true"]{background:#4338ca}.stTabs [aria-selected="true"] p{color:#fff !important}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none !important;height:0 !important;background:transparent !important}
.stTabs button[data-baseweb="tab"]{padding:10px 24px !important;height:auto !important;margin-right:6px}
[data-testid="stVerticalBlockBorderWrapper"]{transition:.2s}
[data-testid="stVerticalBlockBorderWrapper"]:hover{box-shadow:0 12px 28px rgba(67,56,202,.16)}
.tag{background:linear-gradient(90deg,#4338ca,#0ea5e9);color:#fff;border-radius:8px;padding:2px 10px;font-size:.72rem;font-weight:700;letter-spacing:.6px}
.ecode{font-size:1.12rem;font-weight:700;color:#1e1b4b;margin-top:8px}.edate{color:#64748b;font-size:.82rem}
.emeta{margin:10px 0;color:#475569;font-size:.9rem}
.emeta i{display:inline-block;width:5px;height:5px;border-radius:50%;background:#94a3b8;margin:0 10px;vertical-align:middle}
.estat{font-size:.8rem;font-weight:600;border-radius:8px;padding:4px 10px;display:inline-block;margin-bottom:8px}
.estat.new{background:#fef3c7;color:#92400e}.estat.done{background:#dcfce7;color:#166534}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,#16a34a,#0d9488);border:none;box-shadow:0 4px 12px rgba(13,148,136,.3)}
.stButton>button[kind="primary"]:hover{filter:brightness(1.08);color:#fff}
.qtext{font-size:1.35rem}
div[role="radiogroup"] label{border-radius:14px;padding:14px 18px;box-shadow:0 1px 3px rgba(15,23,42,.05)}
div[role="radiogroup"] label:hover{transform:translateX(4px)}
</style>""", unsafe_allow_html=True)

def card_meta(code):
    m = re.match(r"^([A-Za-z]+)[-_](\d{8})", code)
    if m:
        try: return m[1].upper(), datetime.strptime(m[2], "%Y%m%d").strftime("%d %b %Y")
        except ValueError: pass
    return code.split("-")[0].upper()[:8], "Custom test"

def open_exam(code, neg):
    ex, err = load_exam(code) if code else (None, "Type an exam code or pick one below.")
    if err: st.error(err); return
    ex["negative_marking"] = NEG_RRB if neg else 0.0
    s.pending = ex; st.rerun()

def upload_panel(neg):
    """Pick exam .json files from your computer: start them directly and/or save them into exams/."""
    st.markdown("<style>.st-key-clear_btn button:not(:disabled){background:#dc2626;color:#fff;border:none}[data-testid='stFileUploaderDropzone']{border:2px dashed #818cf8;background:#eef2ff;border-radius:14px}</style>", unsafe_allow_html=True)
    with st.container(border=True, key="uploadbox"):
        st.markdown("#### 📤 Upload an exam file")
        if s.get("flash"): st.success(s.pop("flash"))
        files = st.file_uploader("Choose one or more exam .json files (any layout the app supports)", type=["json"],
                                 accept_multiple_files=True, key="exam_upload")
        for f in files or []:
            code = re.sub(r"[^A-Za-z0-9_\-]", "_", Path(f.name).stem)[:60] or "UPLOAD"
            uid = re.sub(r"\W", "_", f"{f.name}_{f.size}")
            try:
                ex = normalize(json.loads(f.getvalue().decode("utf-8-sig")), code)
            except (ValueError, UnicodeDecodeError) as e:        # JSONDecodeError is a ValueError
                st.error(f"**{f.name}** can't be used: {e}"); continue
            secs = {}
            for q in ex["questions"]: secs[q["section"]] = secs.get(q["section"], 0) + 1
            exists = find_exam(code)
            c1, c2, c3 = st.columns([3, 1.3, 1.3], vertical_alignment="center")
            c1.markdown(f"✅ **{html.escape(f.name)}** → code `{code}` · **{len(ex['questions'])}** questions · "
                        + ", ".join(f"{a} {b}" for a, b in secs.items()))
            ow = c1.checkbox("A file with this code exists: overwrite it", key=f"ow_{uid}") if exists else True
            if c2.button("💾 Save to library", key=f"sv_{uid}", width="stretch"):
                if not ow: st.warning("Tick overwrite to replace the existing exam.")
                else:
                    EXAMS.mkdir(exist_ok=True)
                    (exists or EXAMS / f"{code}.json").write_bytes(f.getvalue())
                    s.flash = f"Saved as {code}. It now appears under Choose a test."; st.rerun()
            if c3.button("▶ Start now", key=f"go_{uid}", type="primary", width="stretch"):
                ex["negative_marking"] = NEG_RRB if neg else 0.0
                s.pending = ex; st.rerun()

# ---------------- instructions + candidate name ----------------
def section_panel(ex):
    """Optional section-wise test: choose which sections to attempt; time is scaled to match."""
    secs = list(dict.fromkeys(q["section"] for q in ex["questions"]))
    if len(secs) < 2: return ex
    with st.container(border=True, key="setupbox"):
        st.markdown("#### 🧩 Sections to attempt")
        pick = st.multiselect("Keep all selected for the full paper, or choose specific sections for a section-wise test",
                              secs, default=secs, key=f"cfg_sec_{ex['code']}")
        if not pick: st.warning("Select at least one section. Using all sections."); pick = secs
        qs = [q for q in ex["questions"] if q["section"] in pick]
        mins = max(1, round(ex["duration_minutes"] * len(qs) / len(ex["questions"])))
        st.caption(f"{len(qs)} questions · {mins} minutes")
    return dict(ex, questions=qs, duration_minutes=mins)

def instructions():
    hero("📋 Instructions", html.escape(s.pending["title"]))
    ex = section_panel(s.pending); Qs = ex["questions"]; n = len(Qs); mins = ex["duration_minutes"]
    neg, mpq = ex.get("negative_marking", 0.0), ex.get("marks_per_question", 1)
    negtxt = (f"<b>{'1/3' if abs(neg-NEG_RRB)<.01 else f'{neg:.2f}'} mark</b> is deducted for every wrong answer."
              if neg else "There is <b>no negative marking</b> in this attempt.")
    L, R = st.columns([2, 1.1], gap="large")
    with L, st.container(border=True):
        st.markdown("### Please read carefully")
        st.markdown(f"""<ol class="inst">
<li>The test has <b>{n} multiple-choice questions</b>, each with four options. Only one option is correct.</li>
<li>Total time is <b>{mins} minutes</b>. The countdown (top right) starts the moment you click <i>Start test</i>, and the test <b>auto-submits</b> when it reaches zero.</li>
<li>Each correct answer carries <b>+{mpq} mark</b>. {negtxt} Unanswered questions carry no marks.</li>
<li>Use <b>Previous / Next</b> or click a number in the <b>question palette</b> to jump to any question. Section tabs in the palette let you move between subjects freely.</li>
<li><b>Mark for review</b> flags a question to revisit. A marked question that has an answer is still evaluated.</li>
<li><b>Clear</b> removes your selected answer for the current question.</li>
<li>A small timer shows the time spent on the current question. It feeds your speed analysis after the test.</li>
<li><b>Do not refresh or close this page</b> during the test: the attempt cannot be resumed.</li>
<li>Click <b>Submit test</b> and confirm to finish early. You will then see your score, topic analysis and a downloadable report.</li></ol>""",
                    unsafe_allow_html=True)
        st.markdown("**Palette colours**")
        st.markdown("""<span class="chip" style="background:#16a34a;color:#fff">Answered</span><span class="chip" style="background:#7c3aed;color:#fff">Marked for review</span>
          <span class="chip" style="background:#fecaca;color:#7f1d1d">Visited, not answered</span><span class="chip" style="background:#e2e8f0;color:#334155">Not visited</span>""",
                    unsafe_allow_html=True)
    with R, st.container(border=True):
        st.markdown("### Candidate")
        name = st.text_input("Your name", value=last_name(), placeholder="Enter your full name", max_chars=60, key="name_in").strip()
        secs = {}
        for x in Qs: secs[x["section"]] = secs.get(x["section"], 0) + 1
        st.markdown(f"**Exam:** `{ex['code']}`")
        k = st.columns(2); k[0].metric("Questions", n); k[1].metric("Minutes", mins)
        st.markdown("".join(f"<span class='chip'>{html.escape(a)} · {b}</span>" for a, b in secs.items()), unsafe_allow_html=True)
        agree = st.checkbox("I have read and understood the instructions")
        if st.button("▶ Start test", type="primary", disabled=len(name) < 2 or not agree, width="stretch"):
            start(ex, name); st.rerun()
        if len(name) < 2: st.caption("Enter your name to continue.")
        if st.button("← Back", width="stretch"):
            s.pop("pending"); st.rerun()

if "exam" not in s and "pending" in s:
    instructions(); st.stop()

# ---------------- entry screen ----------------
if "exam" not in s:
    hero("🚆 RRB ALP CBT-1 – Daily Mock Test", "Prepare. Practise. Progress. Your journey to the Loco Pilot’s seat begins here.")
    d = inprog_load()
    if d:
        left = d["exam"]["duration_minutes"] * 60 - (time.time() - d["start"])
        with st.container(border=True, key="resumebox"):
            c1, c2, c3 = st.columns([4, 1, 1], vertical_alignment="center")
            c1.markdown(f"#### ⏸ Unfinished test: `{html.escape(d['exam']['code'])}`")
            c1.markdown(f"👤 {html.escape(d['name'])} · answered **{len(d['answers'])}/{len(d['exam']['questions'])}** · "
                        + ("⏰ **time is up**, it will be submitted when you resume" if left <= 0 else f"⏱ **{int(left)//60:02d}:{int(left)%60:02d}** left (the clock kept running)"))
            if c2.button("▶ Resume", type="primary", key="resume_btn", width="stretch"): resume(d); st.rerun()
            if c3.button("Discard", key="discard_btn", width="stretch"): inprog_clear(); st.rerun()
    t1, t2 = st.tabs(["📝 Take exam", "📈 Progress & practice"])
    with t1:
        avail = list_exams()
        bests = avail["Best %"].dropna() if not avail.empty else []
        st.markdown(f"""<div class="stats"><div><span>{len(avail)}</span>Exams available</div>
          <div><span>{int(avail.Attempts.sum()) if not avail.empty else 0}</span>Attempts so far</div>
          <div><span>{f'{bests.max():.0f}%' if len(bests) else '—'}</span>Best score</div><div><span>1/3</span>Negative marking</div></div>""",
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns([3, 1, 1.5], vertical_alignment="bottom")
        typed = c1.text_input("Have an exam code?", placeholder="Type any code, e.g. TECH-20260313-S1").strip()
        go = c2.button("Load code", type="primary", width="stretch")
        neg = c3.toggle("Negative marking (1/3)", value=True)
        if go: open_exam(typed, neg)
        upload_panel(neg)
        st.markdown("### 🗂 Choose a test")
        if avail.empty: st.info("No exam files found in the exams folder.")
        rows = avail.to_dict("records")
        for r0 in range(0, len(rows), 3):
            for col, r in zip(st.columns(3), rows[r0:r0 + 3]):
                kid = re.sub(r"\W", "_", r["Code"])
                with col, st.container(border=True, key=f"tk_{kid}"):
                    pre, date = card_meta(r["Code"])
                    n_at = int(r["Attempts"]); best = f"{r['Best %']:.0f}%" if n_at and pd.notna(r["Best %"]) else "—"
                    stamp = f"<span class='stamp done'>ATTEMPTED x{n_at}</span>" if n_at else "<span class='stamp new'>NEW</span>"
                    st.markdown(f"<div class='tk-h'><span class='tag'>{html.escape(pre)}</span><span class='tk-t'>MOCK TEST TICKET</span>{stamp}</div>"
                                f"<div class='ecode'>{html.escape(r['Code'])}</div><div class='edate'>Date of test · {date}</div>"
                                f"<div class='tk-row'><div><small>QUESTIONS</small><b>{r['Questions']}</b></div><div><small>MINUTES</small><b>{r['Minutes']}</b></div>"
                                f"<div><small>BEST</small><b>{best}</b></div></div><div class='tk-perf'></div>", unsafe_allow_html=True)
                    if st.button("▶ Start", key=f"card_{r['Code']}", type="primary", width="stretch"):
                        open_exam(r["Code"], neg)
    with t2: progress()
    st.stop()

exam = s.exam; Q = exam["questions"]; N = len(Q)
DUR = exam["duration_minutes"] * 60
NEG = exam.get("negative_marking", 0.0)
MPQ = exam.get("marks_per_question", 1)
fmt = lambda t: f"{int(max(t,0))//60:02d}:{int(max(t,0))%60:02d}"

# ---------------- results screen ----------------
if s.submitted:
    df, det, target = analyse(exam, s.answers, s.qtime)
    c, w, sk = (int((df.Status == x).sum()) for x in ("Correct", "Wrong", "Skipped"))
    score = (c - w * NEG) * MPQ; plain = c * MPQ
    total_t = sum(s.qtime)
    m = dict(score=score, max=N*MPQ, correct=c, wrong=w, skipped=sk, accuracy=100*c/max(c+w, 1), total_time=total_t, neg=NEG)
    if not s.saved:
        save_attempt(exam["code"], m, det, s.name); s.saved = True
    hero(f"📊 Result – {html.escape(s.name)}", f"{html.escape(exam['title'])} · {datetime.now():%d %b %Y}")
    k = st.columns(4)
    k[0].metric("Score", f"{score:.2f} / {N*MPQ}"); k[1].metric("Correct", c); k[2].metric("Wrong", w); k[3].metric("Skipped", sk)
    k = st.columns(3)
    k[0].metric("Accuracy (of attempted)", f"{m['accuracy']:.1f}%"); k[1].metric("Total time", fmt(total_t))
    k[2].metric("Avg time / question", f"{total_t/N:.1f}s")
    st.caption(f"Without negative marking: **{plain:.2f}** · With 1/3 negative marking: **{(c - w*NEG_RRB)*MPQ:.2f}** · Applied in this attempt: **{score:.2f}**")

    st.subheader("Section-wise score")
    sec = df.groupby("Section").agg(Questions=("No", "count"), Correct=("Status", lambda x: (x == "Correct").sum()),
                                    Wrong=("Status", lambda x: (x == "Wrong").sum()), Skipped=("Status", lambda x: (x == "Skipped").sum()),
                                    AvgTime=("Time", "mean")).reset_index()
    sec["Marks"] = ((sec.Correct - sec.Wrong * NEG) * MPQ).round(2)
    sec["Accuracy %"] = (100 * sec.Correct / sec.Questions).round(1); sec["AvgTime"] = sec.AvgTime.round(1)
    st.dataframe(sec, width="stretch", hide_index=True)

    st.subheader("Topic-wise performance")
    g = df.groupby(["Section", "Topic"]).agg(Questions=("No", "count"), Correct=("Status", lambda x: (x == "Correct").sum()),
                                             Wrong=("Status", lambda x: (x == "Wrong").sum()), Skipped=("Status", lambda x: (x == "Skipped").sum()),
                                             AvgTime=("Time", "mean")).reset_index()
    g["Accuracy %"] = (100 * g.Correct / g.Questions).round(1); g["AvgTime"] = g.AvgTime.round(1)   # skipped counts against you
    st.dataframe(g, width="stretch", hide_index=True)
    a, b = st.columns(2)
    a.success("💪 Strong (≥75%): " + (", ".join(g[g["Accuracy %"] >= 75].Topic) or "—"))
    b.error("⚠️ Weak (<50%): " + (", ".join(g[g["Accuracy %"] < 50].Topic) or "—"))

    st.subheader("Charts")
    c1, c2, c3 = st.columns(3)
    c1.caption("Topic accuracy (%)"); c1.bar_chart(df.groupby("Topic").Status.apply(lambda x: 100 * (x == "Correct").mean()))
    c2.caption("Time spent per question (s)"); c2.scatter_chart(df, x="No", y="Time", color="Status")
    c3.caption("Speed vs accuracy (count)"); c3.bar_chart(df.Category.value_counts())

    st.subheader("Speed vs accuracy")
    st.caption(f"'Fast' = within {target:.0f}s (exam time ÷ questions).")
    for cat in ["Fast & correct", "Slow & correct", "Slow & wrong", "Fast & wrong", "Skipped"]:
        nums = df[df.Category == cat].No.tolist()
        st.write(f"**{cat}** ({len(nums)}): {', '.join(map(str, nums)) or '—'}")

    st.subheader("Download report")
    rep = pd.DataFrame([dict(No=i+1, Section=d["section"], Topic=d["topic"], Difficulty=d["difficulty"], Question=d["question"],
                             YourAnswer=d["options"][d["user"]] if d["user"] is not None else "Not attempted",
                             CorrectAnswer=d["options"][d["answer"]], Status=d["Status"], Category=d["Category"],
                             TimeSec=d["time"], Explanation=d["explanation"]) for i, d in enumerate(det)])
    d1, d2 = st.columns(2)
    d1.download_button("⬇ CSV report", rep.to_csv(index=False).encode("utf-8-sig"), f"{exam['code']}_report.csv", "text/csv", width="stretch")
    try:
        summ = (f"Score {score:.2f}/{N*MPQ} | Correct {c} | Wrong {w} | Skipped {sk} | Accuracy {m['accuracy']:.1f}% | "
                f"Total time {fmt(total_t)} | Avg {total_t/N:.1f}s/question | Negative marking {NEG:.2f}")
        d2.download_button("⬇ PDF report", make_pdf(f'{exam["title"]} - {s.name}', summ, sec, g, det), f"{exam['code']}_report.pdf",
                           "application/pdf", width="stretch")
    except ImportError:
        d2.info("For PDF: pip install fpdf2")

    st.subheader("Question-wise analysis")
    redo = [d for d in det if d["Status"] != "Correct"]
    if redo and st.button(f"🎯 Retry my {len(redo)} wrong / skipped questions", type="primary"):
        qs = [{k: d[k] for k in ("question", "options", "answer", "section", "topic", "difficulty", "explanation")} for d in redo]
        start(dict(code="PRACTICE", title="Retry: wrong & skipped questions", duration_minutes=max(5, math.ceil(len(qs) * 0.8)),
                   marks_per_question=1, negative_marking=0.0, questions=qs), s.name); st.rerun()
    flt = st.radio("Show", ["All", "Wrong", "Skipped", "Slow (over benchmark)", "Marked for review"], horizontal=True)
    keep = lambda i, d: (flt == "All" or (flt == "Wrong" and d["Status"] == "Wrong") or (flt == "Skipped" and d["Status"] == "Skipped")
                         or (flt.startswith("Slow") and d["time"] > target) or (flt.startswith("Marked") and i in s.marked))
    shown = [(i, d) for i, d in enumerate(det) if keep(i, d)]
    st.caption(f"{len(shown)} question(s) shown")
    for i, d in shown:
        icon = {"Correct": "✅", "Wrong": "❌", "Skipped": "⏭️"}[d["Status"]]
        with st.expander(f"{icon} Q{i+1} · {d['topic']} · {d['difficulty']} · {d['time']}s · {d['Category']}"):
            st.write(d["question"])
            st.write(f"**Your answer:** {d['options'][d['user']] if d['user'] is not None else 'Not attempted'}")
            st.write(f"**Correct answer:** {d['options'][d['answer']]}")
            st.info(d["explanation"])
    if st.button("Back to start"):
        s.clear(); st.rerun()
    st.stop()

# ---------------- exam screen ----------------
inprog_save()      # every interaction is saved, so a refresh can be resumed
@st.fragment(run_every=1)
def timers():
    left = DUR - (time.time() - s.start)
    if left <= 0:
        submit(); st.rerun()
    qt = s.qtime[s.cur] + time.time() - s.last
    st.markdown(f"""<div style="text-align:right"><span class="pill {'low' if left < 300 else ''}"><b>{fmt(left)}</b><span>TIME LEFT</span></span>
      <span class="pill"><b>{int(qt)}s</b><span>THIS QUESTION</span></span></div>""", unsafe_allow_html=True)

top = st.columns([3, 2, 0.9, 1.1], vertical_alignment="center")
top[0].markdown(f"""<div class="topbar" style="margin:0"><div><div class="t">🚆 {html.escape(exam.get('title', 'ALP CBT-1 Mock'))}</div>
  <div class="s">👤 {html.escape(s.name)} · {N} questions · {exam['duration_minutes']} min · negative marking {'1/3' if abs(NEG-NEG_RRB)<.01 else ('off' if not NEG else f'{NEG:.2f}')}</div></div></div>""", unsafe_allow_html=True)
with top[1]: timers()
with top[2]: fs_button()
if top[3].button("✔ Submit test", key="submit_top", width="stretch"):
    s.confirm = True

done = len(s.answers)
st.markdown(f"<div class='prog'><div style='width:{100*done/N:.0f}%'></div><img src='{_mini_train()}' style='left:{100*done/N:.0f}%'/></div>"
            f"<div class='progtxt'>{done} of {N} answered · {len(s.marked)} marked for review</div>", unsafe_allow_html=True)
if s.get("confirm"):
    with st.container(border=True, key="confirmbox"):
        st.markdown(f"#### Submit your test?\nAnswered **{done}** · Not answered **{N-done}** · Marked for review **{len(s.marked)}**. "
                    "You cannot change answers after submitting.")
        y, n_, _ = st.columns([1, 1, 4])
        if y.button("Yes, submit", type="primary", width="stretch"): s.confirm = False; submit(); st.rerun()
        if n_.button("Cancel", width="stretch"): s.confirm = False; st.rerun()

def pal_css():   # colour each palette button by state (needs Streamlit >= 1.39)
    r = ["""<style>
.st-key-submit_top button{background:linear-gradient(90deg,#dc2626,#f97316) !important;color:#fff !important;border:none !important;font-weight:700;min-height:3.1rem;box-shadow:0 4px 14px rgba(220,38,38,.35)}
.st-key-mark button{background:#fef3c7;border-color:#f59e0b;color:#92400e}
.st-key-clear button{background:#f1f5f9;color:#475569}
.st-key-nextq button,.st-key-prevq button{min-height:3rem;font-size:1rem}
.st-key-qcard{border-left:6px solid #c8962e !important}
.st-key-confirmbox{border:2px solid #f97316 !important;background:#fff7ed !important}
.prog{position:relative;height:12px;margin-top:20px;border-radius:6px;background:repeating-linear-gradient(90deg,#8a6a4a 0 7px,transparent 7px 12px),#d8cfbe}
.prog div{height:100%;border-radius:6px;background:linear-gradient(90deg,#2e7d32,#7cb342);transition:width .4s}
.prog img{position:absolute;top:-17px;width:52px;height:22px;transform:translateX(-85%);transition:left .4s}
.progtxt{font-size:.8rem;color:#64748b;margin:4px 0 14px}
[data-testid="stColumn"]:has(.st-key-palbox){position:sticky;top:10px;align-self:flex-start}
.cnt{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:4px 0 12px}
.cnt div{border-radius:10px;padding:6px 10px;font-size:.78rem;font-weight:600}.cnt b{font-size:1.1rem;margin-right:4px}
"""]
    for k in range(N):
        ans, mk = k in s.answers, k in s.marked
        bg, fg = ("#7c3aed", "#fff") if mk else ("#16a34a", "#fff") if ans else ("#fecaca", "#7f1d1d") if k in s.visited else ("#e2e8f0", "#334155")
        ring = "outline:3px solid #0f172a;outline-offset:1px;" if k == s.cur else ""
        r.append(f".st-key-p{k} button{{background:{bg};color:{fg};border:none;min-height:2.4rem;width:100%;border-radius:7px;font-weight:700;box-shadow:inset 0 0 0 2px rgba(255,255,255,.55);{ring}}}"
                 f".st-key-p{k} button:hover{{color:{fg};filter:brightness(1.1)}}")
    return "".join(r) + "</style>"
st.markdown(pal_css(), unsafe_allow_html=True)

main, pal = st.columns([3, 1.1])
i = s.cur; q = Q[i]
with main:
    with st.container(border=True, key="qcard"):
        st.markdown(f"<div class='qmeta'><span>Q {i+1} / {N}</span><span>{html.escape(q['section'])}</span><span>{html.escape(q['topic'])}</span><span>{html.escape(q['difficulty'])}</span></div>"
                    f"<div class='qtext'>{q['question']}</div>", unsafe_allow_html=True)
        st.radio("Options", range(4), index=s.answers.get(i), key=f"opt{i}", label_visibility="collapsed",
                 format_func=lambda k: f"{'ABCD'[k]}.  {q['options'][k]}", on_change=save_answer, args=(i,))
    c = st.columns(4)
    c[0].button("⬅ Previous", key="prevq", disabled=i == 0, on_click=goto, args=(i-1,), width="stretch")
    if c[1].button("Clear response", key="clear", width="stretch"):
        s.answers.pop(i, None); s.pop(f"opt{i}", None); st.rerun()
    if c[2].button("Unmark review" if i in s.marked else "🔖 Mark for review", key="mark", width="stretch"):
        s.marked.symmetric_difference_update({i}); st.rerun()
    c[3].button("Save & Next ➡", key="nextq", type="primary", disabled=i == N-1, on_click=goto, args=(i+1,), width="stretch")

def pal_buttons(idxs):
    cols = st.columns(5)
    for n, k in enumerate(idxs):
        cols[n % 5].button(str(k+1), key=f"p{k}", on_click=goto, args=(k,))

with pal:
    with st.container(border=True, key="palbox"):
        st.markdown("**Question palette**")
        na = len(s.visited - set(s.answers)); nv = N - len(s.visited)
        st.markdown(f"""<div class="cnt"><div style="background:#16a34a;color:#fff"><b>{done}</b>Answered</div>
          <div style="background:#7c3aed;color:#fff"><b>{len(s.marked)}</b>Marked</div>
          <div style="background:#fecaca;color:#7f1d1d"><b>{na}</b>Not answered</div>
          <div style="background:#e2e8f0;color:#334155"><b>{nv}</b>Not visited</div></div>""", unsafe_allow_html=True)
        secs = list(dict.fromkeys(x["section"] for x in Q))
        if len(secs) > 1:
            groups = [[k for k in range(N) if Q[k]["section"] == sc] for sc in secs]
            tabs = st.tabs([f"{SHORT.get(sc, sc)} {sum(k in s.answers for k in g)}/{len(g)}" for sc, g in zip(secs, groups)])
            for tb, g in zip(tabs, groups):
                with tb: pal_buttons(g)
        else:
            pal_buttons(range(N))
