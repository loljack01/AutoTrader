"""Comportement d'apres l'historique git (commits de l'auteur Claude, depuis le 01/09/2026, heure de Paris).
Commande de base : git log --author=Claude --format='%ad|%s' --date=iso-strict
Classes (sur le sujet du commit) :
  donnees   Accumulate | evening update | morning (?:update|run) | Frozen strategies: | cache | Cache | Extend | Refresh | Seed | Update FCE1
  idee      nouveau test ou suivi fige : Freeze | Fige | rules fixed before running | frozen before | Add .*test | ^Test
  resultat  Record result | REJETE | rejected | not kept | none kept | no edge | not confirmed | not retained | none adopted | pass | confirmed
  regle     modification des regles en vigueur : Execution rules | working group's decisions | capital | go-live rule | Promote | guard-rails | Amend
  rejet     resultat contenant REJETE | rejected | not kept | none kept | no edge | not confirmed | not retained | none adopted
Seance = jour ouvre 9h00-17h30 Paris (seance europeenne) ; 'elargie' = 8h00-22h00.
Amendements de regles figees : commits (hors donnees) modifiant un scripts/frozen_*.py deja existant, et 'Amended on' dans les docstrings.
Usage : python3 behaviour.py"""
import re, subprocess
from collections import Counter
import pandas as pd

REPO = "/home/user/AutoTrader"
log = subprocess.run(["git", "-C", REPO, "log", "--author=Claude", "--since=2026-09-01", "--format=%H|%ad|%s",
                      "--date=iso-strict"], capture_output=True, text=True).stdout.strip().splitlines()
rows = []
for l in log:
    h, d, s = l.split("|", 2)
    rows.append((h, pd.Timestamp(d).tz_convert("Europe/Paris"), s))
c = pd.DataFrame(rows, columns=["h", "t", "s"]).sort_values("t")
DATA = r"Accumulate|evening update|morning (?:update|run)|Frozen strategies:|[Cc]ache|Extend|Refresh|Seed|Update FCE1|Scripts figes|Principale 30/10 soir|empty trades file"
IDEA = r"Freeze|Fige|rules fixed before running|frozen before|Add .*test|^Test |^Tests 1-3 of"
RES = r"Record result|REJETE|rejected|not kept|none kept|no edge|not confirmed|not retained|none adopted|pass|confirmed|: neither kept"
REJ = r"REJETE|rejected|not kept|none kept|no edge|not confirmed|not retained|none adopted|neither kept"
RULE = r"Execution rules|working group's decisions|capital|go-live rule|Promote|guard-rails|Amend|sizing"
c["data"] = c.s.str.contains(DATA)
c["idea"] = ~c.data & c.s.str.contains(IDEA)
c["res"] = ~c.data & c.s.str.contains(RES)
c["rej"] = ~c.data & c.s.str.contains(REJ)
c["rule"] = ~c.data & c.s.str.contains(RULE)
c["day"] = c.t.dt.date
c["wd"] = c.t.dt.weekday < 5
h = c.t.dt.hour + c.t.dt.minute / 60
c["seance"] = c.wd & (h >= 9) & (h < 17.5)
c["elargie"] = c.wd & (h >= 8) & (h < 22)
w = c[~c.data]
print(f"Commits Claude depuis le 01/09/2026 : {len(c)} dont {c.data.sum()} de donnees/routines, {len(w)} de travail")
print(f"  travail : {w.seance.sum()} en seance 9h-17h30 ({w.seance.mean():.0%}), {w.elargie.sum()} entre 8h et 22h un jour ouvre "
      f"({w.elargie.mean():.0%}), {(~w.wd).sum()} le week-end")
for lab, col in (("idees (tests / suivis figes)", "idea"), ("resultats", "res"), ("dont rejets", "rej"), ("changements de regles", "rule")):
    x = w[w[col]]
    per = x.groupby("day").size()
    print(f"  {lab:30s}: {len(x):3d} sur {per.size:2d} jours actifs, max {per.max() if len(per) else 0}/jour "
          f"(le {per.idxmax() if len(per) else '-'}), en seance {x.seance.mean():.0%}")
ideas = w[w.idea]
oct27 = ideas[ideas.t >= pd.Timestamp("2026-10-22", tz="Europe/Paris")]
print(f"  depuis le 22/10 (zero ordre hors systeme) : {len(oct27)} commits d'idees sur "
      f"{oct27.day.nunique()} jours, {len(oct27) / max(1, ((pd.Timestamp('2026-11-06') - pd.Timestamp('2026-10-22')).days / 7)):.1f} par semaine")
# delai seance -> idee
def since_close(t):
    if t.weekday() < 5 and t.hour + t.minute / 60 >= 9:
        close = t.normalize() + pd.Timedelta(hours=17.5)
        return 0.0 if t < close else (t - close).total_seconds() / 3600
    d = t.normalize() - pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return (t - (d + pd.Timedelta(hours=17.5))).total_seconds() / 3600
dl = ideas.t.map(since_close)
same = ideas.wd & (ideas.t.dt.hour >= 9)
print(f"  idees : delai depuis la fin de la derniere seance mediane {dl.median():.1f} h ; nees PENDANT une seance {(dl == 0).mean():.0%} ; "
      f"nees le jour meme d'une seance (jour ouvre, apres 9h) {same.mean():.0%} ; le week-end {(~ideas.wd).mean():.0%}")
ref = ideas.s[ideas.s.str.contains(r"session|seance|live watch|\d\d/\d\d")]
print(f"  idees citant une seance ou une date : {len(ref)} -> " + " | ".join(ref.str[:70]))
# fige puis rejete : couples idee -> resultat de rejet le meme jour
rej = w[w.rej]
print(f"  commits a la fois gel et resultat (test et resultat dans le meme commit) : {(w.res & w.idea).sum()}")
lag = []
for r in rej.itertuples():
    prev = ideas[(ideas.t <= r.t) & (ideas.h != r.h)]
    if len(prev):
        lag.append((r.t - prev.t.iloc[-1]).total_seconds() / 60)
print(f"  commits de rejet : {len(rej)} ; delai median depuis le dernier gel {pd.Series(lag).median():.0f} min ; "
      f"rejets le jour meme du gel {(pd.Series(lag) < 24 * 60).mean():.0%}")
# amendements de regles figees
files = subprocess.run(["git", "-C", REPO, "ls-files", "scripts/frozen_*.py"], capture_output=True, text=True).stdout.split()
am = 0
per_file = {}
for f in files:
    hs = subprocess.run(["git", "-C", REPO, "log", "--format=%H|%s", "--follow", "--", f], capture_output=True, text=True).stdout.strip().splitlines()
    mods = [x for x in hs[:-1] if not re.search(DATA, x.split("|", 1)[1])]
    per_file[f.split("/")[-1]] = len(mods)
    am += len(mods)
txt = {f: open(f"{REPO}/{f}").read() for f in files}
amended = {f.split("/")[-1]: len(re.findall(r"Amended on", s)) for f, s in txt.items() if "Amended on" in s}
print(f"  scripts figes : {len(files)} ; modifications apres creation (hors donnees) : {am} -> "
      + ", ".join(f"{k} {v}" for k, v in per_file.items() if v))
print(f"  'Amended on' dans les docstrings : " + ", ".join(f"{k} {v}" for k, v in amended.items()))
sw = c[c.s.str.contains("[Ss]wing RSI")]
print(f"  swing : premier gel {sw.t.min():%d/%m %H:%M}, passage en reel phase 1 ({c[c.s.str.contains('swing execution phase')].t.min():%d/%m %H:%M}), "
      f"derniere modification des regles du swing {c[c.s.str.contains('Swing: capital')].t.max():%d/%m %H:%M}")
