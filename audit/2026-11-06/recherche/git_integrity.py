"""Section 1 : historique git de chaque script figé / test.
Pour chaque version d'un script : date, commit, sujet, et si le CODE (AST sans le
docstring de module) a changé par rapport à la version précédente, avec les
constantes REFERENCE/REF modifiées.
Usage : python3 git_integrity.py [motif]   (lecture seule du dépôt)"""
import ast, subprocess, sys, re, difflib
REPO = "/home/user/AutoTrader"
def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True).stdout
pat = sys.argv[1] if len(sys.argv) > 1 else None
files = sorted(set(git("log", "--since=2026-01-01", "--name-only", "--format=").split()))
files = [f for f in files if f.startswith("scripts/") and f.endswith(".py") and
         (re.search(r"(frozen_|test|_test|swing_portfolio|robustness|audit_|gap_fill|incremental|backtest_liquidity|ma_grid|other_markets)", f))]
if pat: files = [f for f in files if pat in f]
def code_of(src):
    try:
        t = ast.parse(src)
    except SyntaxError:
        return None, {}
    if t.body and isinstance(t.body[0], ast.Expr) and isinstance(getattr(t.body[0], "value", None), ast.Constant):
        t.body = t.body[1:]
    consts = {}
    for n in t.body:
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name) and re.match(r"^(REF|REFERENCE)", tg.id):
                    consts[tg.id] = ast.unparse(n.value)
    return ast.unparse(t), consts
for f in files:
    log = git("log", "--follow", "--reverse", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M", "--", f).strip().splitlines()
    log = [l for l in log if l.split("|")[1] >= "2026"]
    print(f"\n=== {f} ({len(log)} commits)")
    prev_code, prev_c = None, {}
    for line in log:
        h, d, s = line.split("|", 2)
        src = git("show", f"{h}:{f}")
        code, consts = code_of(src)
        if not src:
            print(f"  {d} {h} [supprime] {s[:90]}"); continue
        if prev_code is None:
            tag = "CREE"
        elif code == prev_code:
            tag = "docstring seul"
        else:
            dl = [l for l in difflib.unified_diff(prev_code.splitlines(), code.splitlines(), lineterm="", n=0)
                  if l[:1] in "+-" and not l.startswith(("+++", "---"))]
            tag = f"CODE +-{len(dl)} lignes"
        refch = [k for k in set(consts) | set(prev_c) if consts.get(k) != prev_c.get(k)] if prev_code is not None else []
        print(f"  {d} {h} [{tag}]{' REF MODIFIEE: ' + ','.join(refch) if refch else ''} {s[:95]}")
        prev_code, prev_c = code, consts
