"""Dashboard local simulation (aucun argent reel). Genere dashboard.html autonome."""
import html
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)
PORTFOLIO = os.path.join(DATA, "paper_portfolio.json")
LOG = os.path.join(DATA, "paper.log")
TRADES = os.path.join(DATA, "trades.log")
OUT = os.path.join(DATA, "dashboard.html")
START_CAPITAL = 1000.0


def tail_lines(path, n):
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]
    except OSError:
        return []
    return [ln for ln in lines if ln.strip()][-n:]


def parse_tick(line):
    def grab(key):
        m = re.search(rf"{key}=([^\s]+)", line)
        return m.group(1) if m else "-"
    ts = line.split(" ")[0] if line else "-"
    return {"ts": ts, "prix": grab("prix"), "signal": grab("signal"),
            "sma7": grab("SMA7"), "sma25": grab("SMA25"), "rsi": grab("RSI"),
            "cash": grab("cash"), "btc": grab("btc"), "valeur": grab("valeur"),
            "raw": line}


def fnum(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def svg_curve(values, w=560, h=140, color="#2563eb"):
    if not values:
        return '<p class="muted">Pas de donnees.</p>'
    vmin, vmax = min(values), max(values)
    span = (vmax - vmin) or 1.0
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = 10 + i * (w - 20) / max(n - 1, 1)
        y = h - 10 - (v - vmin) / span * (h - 20)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    label_min, label_max = f"{vmin:.2f}", f"{vmax:.2f}"
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#f8fafc"/>'
        f'<polyline points="{html.escape(poly)}" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<text x="12" y="16" font-size="11" fill="#64748b">max {html.escape(label_max)}</text>'
        f'<text x="12" y="{h - 4}" font-size="11" fill="#64748b">min {html.escape(label_min)}</text>'
        "</svg>"
    )


def main():
    try:
        with open(PORTFOLIO, encoding="utf-8") as f:
            pf = json.load(f)
    except (OSError, ValueError):
        pf = {"cash": START_CAPITAL, "btc": 0.0, "trades": 0}
    cash = fnum(pf.get("cash"), START_CAPITAL)
    btc = fnum(pf.get("btc"), 0.0)
    ntrades = pf.get("trades", 0)

    ticks = [parse_tick(ln) for ln in tail_lines(LOG, 100)]
    prix_hist = [fnum(t["prix"]) for t in ticks if fnum(t["prix"], -1) >= 0]
    val_hist = [fnum(t["valeur"]) for t in ticks if fnum(t["valeur"], -1) >= 0]

    # Prix live, fallback derniere valeur du log.
    live = None
    try:
        import price as price_mod
        live = float(price_mod.get_price("BTCUSDT"))
    except Exception:
        live = prix_hist[-1] if prix_hist else 0.0
    if live is None:
        live = prix_hist[-1] if prix_hist else 0.0

    ref = prix_hist[0] if prix_hist else live
    up = live >= ref
    color = "#16a34a" if up else "#dc2626"
    arrow = "▲" if up else "▼"

    cur_val = cash + btc * live
    pnl = cur_val - START_CAPITAL
    pnl_c = "#16a34a" if pnl >= 0 else "#dc2626"

    last = ticks[-1] if ticks else None
    last_signal = last["signal"] if last else "?"

    trades_raw = tail_lines(TRADES, 50)
    # Derniere explication FR : dernier bloc non vide de trades.log.
    expl = ""
    if trades_raw:
        bloc, cur = [], []
        for ln in trades_raw + [""]:
            if ln.startswith("[") and cur:
                bloc = cur
                cur = [ln]
            elif not ln.strip() and cur:
                bloc = cur
                cur = []
            else:
                cur.append(ln)
        if cur:
            bloc = cur
        expl = "\n".join(bloc).strip()
    if not expl and last:
        expl = last["raw"]

    rows = ""
    for t in ticks[-10:][::-1]:
        rows += ("<tr>" + "".join(f"<td>{html.escape(str(t[k]))}</td>"
                 for k in ("ts", "prix", "signal", "sma7", "sma25", "rsi", "cash", "btc", "valeur")) + "</tr>\n")

    page = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot BTC — Dashboard SIMULATION</title>
<style>
body{{font-family:sans-serif;max-width:900px;margin:1em auto;padding:0 1em;color:#0f172a}}
.card{{border:1px solid #e2e8f0;border-radius:8px;padding:1em;margin:1em 0}}
.badge{{background:#fef08a;padding:.2em .6em;border-radius:4px;font-weight:bold}}
table{{border-collapse:collapse;width:100%;font-size:.8em}}
td,th{{border:1px solid #e2e8f0;padding:4px 6px;text-align:right}}
th{{background:#f1f5f9}}td:first-child,th:first-child{{text-align:left}}
.muted{{color:#64748b}}
pre{{white-space:pre-wrap;background:#f8fafc;padding:.6em;border-radius:6px}}
</style></head>
<body>
<h1>Bot BTC — Dashboard <span class="badge">SIMULATION</span></h1>
<p class="muted">Trading simulé (SIMULATION) — aucun argent réel. Rafraîchi toutes les 60 s.</p>
<div class="card">
<h2>Prix actuel (SIMULATION) : <span style="color:{color}">{live:.2f} $ {arrow}</span></h2>
<p>Référence début de période : {ref:.2f} $ — <span style="color:{color}">{"en hausse" if up else "en baisse"}</span>.</p>
</div>
<div class="card">
<h2>Portefeuille simulé (SIMULATION) : {cur_val:.2f} $ <span style="color:{pnl_c}">({pnl:+.2f} $ vs {START_CAPITAL:.0f} $)</span></h2>
<p>Cash simulé : {cash:.2f} $ — BTC simulé : {btc:.6f} — Nombre de trades simulés : {html.escape(str(ntrades))}</p>
</div>
<div class="card">
<h2>Dernier signal (SIMULATION) : {html.escape(str(last_signal))}</h2>
<pre>{html.escape(expl) if expl else "Aucune explication pour le moment."}</pre>
</div>
<div class="card"><h2>Courbe prix (100 derniers ticks, SIMULATION)</h2>{svg_curve(prix_hist, color=color)}</div>
<div class="card"><h2>Courbe valeur portefeuille (SIMULATION)</h2>{svg_curve(val_hist, color="#7c3aed")}</div>
<div class="card"><h2>10 derniers ticks (SIMULATION)</h2>
<table><tr><th>heure</th><th>prix</th><th>signal</th><th>SMA7</th><th>SMA25</th><th>RSI</th><th>cash</th><th>btc</th><th>valeur</th></tr>
{rows if rows else "<tr><td colspan=9>Aucun tick.</td></tr>"}
</table></div>
<p class="muted">SIMULATION — débutant : le gain/perte affiché est fictif, aucun ordre réel n'est envoyé.</p>
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"dashboard SIMULATION ecrit: {OUT} (prix={live:.2f}, valeur={cur_val:.2f})")


if __name__ == "__main__":
    main()
