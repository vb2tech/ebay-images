#!/usr/bin/env python3
"""Price proposals for items in the repo.

Subcommands (run from the repo root):
  pricing.py todo   [--status new]                      list items that need a price (JSON)
  pricing.py propose proposals.json                      write proposals into each listing.json
  pricing.py report [--status new] [--sku ...] --out pricing/review.html
                                                         numbered review page + pricing/review-<date>.json (# -> SKU)
  pricing.py apply  --review pricing/review-<date>.json [--accept-all] [--set 3=45 CGC-123=19.99 ...]
                    [--hold 5 ...] [--accept 1 2 ...]    approve -> pricing.final, status 'priced'

proposals.json (written by Claude after researching sold comps):
[{"sku": "CGC-4402325019", "proposed": 29.99, "low": 24, "high": 35, "confidence": "high|medium|low",
  "basis": "9.2 sold $24-35 (2026); 9.4 ~$32",
  "comps": [{"source": "eBay sold", "grade": "9.2", "price": 27.5, "date": "2026-09", "url": "https://..."}]}]
"""
import argparse, datetime as dt, html, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../tools"))
import ebaylib as L  # noqa: E402


def charm(p):
    """Round to a .99 price point the way the shop prices (e.g. 31.20 -> 30.99, 47 -> 46.99)."""
    p = float(p)
    if p < 10:
        return round(max(0.99, round(p) - 0.01), 2)
    return round(round(p) - 0.01, 2)


def cmd_todo(a):
    items = L.load_items(status=a.status)
    out = [{"sku": d["sku"], "title": d.get("listing", {}).get("title"), "grade": d["item"]["grade"],
            "has_proposal": bool((d.get("pricing") or {}).get("proposed"))} for d in items]
    print(json.dumps(out, indent=1))


def cmd_propose(a):
    props = json.load(open(a.file))
    by = {d["sku"]: d for d in L.load_items()}
    for p in props:
        d = by.get(p["sku"])
        if not d:
            print(f"skip {p['sku']}: not in repo"); continue
        pr = d.setdefault("pricing", {})
        pr.update({k: p[k] for k in ("proposed", "low", "high", "confidence", "basis", "comps") if k in p})
        pr["proposed"] = charm(pr["proposed"]) if a.charm else float(pr["proposed"])
        pr["proposed_at"] = L.today()
        L.log(d, "price_proposed", price=pr["proposed"])
        L.save_item(d)
        print(f"{d['sku']}: proposed {pr['proposed']}")


def cmd_report(a):
    items = L.load_items(sku=a.sku) if a.sku else L.load_items(status=a.status)
    items = [d for d in items if (d.get("pricing") or {}).get("proposed")]
    if not items:
        sys.exit("No items with proposals to report.")
    items.sort(key=lambda d: (d["item"]["series"], str(d["item"]["issue"]), float(d["item"]["grade"])))
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    os.makedirs(os.path.join(L.ROOT, "pricing"), exist_ok=True)
    review = {"created": stamp, "items": {str(i + 1): d["sku"] for i, d in enumerate(items)}}
    rpath = os.path.join(L.ROOT, "pricing", f"review-{stamp}.json")
    json.dump(review, open(rpath, "w"), indent=1)

    e = html.escape
    total = sum(d["pricing"]["proposed"] for d in items)
    rows = []
    for i, d in enumerate(items, 1):
        it, pr = d["item"], d["pricing"]
        photo = L.photos_of(d)[0] if L.photos_of(d) else ""
        comps = "".join(
            f"<li>{e(str(c.get('grade','')))} · ${e(str(c.get('price','')))} · {e(c.get('date',''))} · "
            + (f"<a href='{e(c['url'])}' target='_blank' rel='noopener'>{e(c.get('source','link'))}</a>" if c.get('url') else e(c.get('source', '')))
            + "</li>" for c in pr.get("comps", [])[:6])
        flags = "".join(f"<span class='flag'>{e(x)}</span>" for x in d.get("needs_review", []))
        rows.append(f"""<tr data-conf="{e(pr.get('confidence','') or '')}">
<td class="n">{i}</td>
<td class="ph">{f"<img src='{e(photo)}' alt='' loading='lazy'>" if photo else ''}</td>
<td><div class="t">{e(d.get('listing',{}).get('title',''))}</div><div class="s">{e(d['sku'])} · {e(it['grader'])} {e(str(it['grade']))}</div>{flags}</td>
<td class="p">${pr['proposed']:.2f}</td>
<td class="r">{'$%s–$%s' % (pr.get('low','?'), pr.get('high','?'))}</td>
<td><span class="conf {e(pr.get('confidence','') or '')}">{e(pr.get('confidence','') or '–')}</span></td>
<td class="b">{e(pr.get('basis',''))}<ul>{comps}</ul></td></tr>""")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pricing Review</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--line:#e4e0d8;--acc:#9a3412;--hi:#166534;--md:#a16207;--lo:#b91c1c;--card:#fff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161513;--fg:#ece9e3;--mut:#a29d93;--line:#34312c;--acc:#fb923c;--hi:#4ade80;--md:#facc15;--lo:#f87171;--card:#1f1d1a}}}}
:root[data-theme="dark"]{{--bg:#161513;--fg:#ece9e3;--mut:#a29d93;--line:#34312c;--acc:#fb923c;--hi:#4ade80;--md:#facc15;--lo:#f87171;--card:#1f1d1a}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}h1{{font-size:22px;margin:0 0 4px}}.sub{{color:var(--mut);margin-bottom:16px}}
.how{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:16px}}
.how code{{background:var(--bg);padding:1px 5px;border-radius:4px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
td,th{{padding:10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}th{{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}}
.n{{font-weight:700;color:var(--acc);font-size:18px}}.ph img{{width:56px;border-radius:4px}}.t{{font-weight:600}}.s{{color:var(--mut);font-size:13px}}
.p{{font-weight:700;font-size:17px;white-space:nowrap}}.r{{white-space:nowrap;color:var(--mut)}}.b{{font-size:13px;color:var(--mut);max-width:320px}}.b ul{{margin:4px 0 0;padding-left:16px}}
.conf{{font-size:12px;font-weight:600;text-transform:uppercase}}.conf.high{{color:var(--hi)}}.conf.medium{{color:var(--md)}}.conf.low{{color:var(--lo)}}
.flag{{display:inline-block;margin-top:4px;font-size:12px;color:var(--lo);border:1px solid var(--lo);border-radius:999px;padding:0 8px}}
a{{color:var(--acc)}}
@media (max-width:700px){{.ph,.b,th:nth-child(2),th:nth-child(7){{display:none}}td,th{{padding:8px 6px}}}}
</style></head><body><main>
<h1>Pricing review</h1><div class="sub">{len(items)} items · proposed total ${total:,.2f} · review {stamp}</div>
<div class="how">Reply in chat using the numbers: <code>approve all</code>, <code>#3 = 45</code>, <code>hold #5</code>, or <code>approve all except #2, #7</code>. Low-confidence rows are worth a second look.</div>
<table><thead><tr><th>#</th><th></th><th>Item</th><th>Proposed</th><th>Range</th><th>Confidence</th><th>Basis</th></tr></thead><tbody>
{''.join(rows)}</tbody></table></main></body></html>"""
    out = os.path.join(L.ROOT, a.out) if not os.path.isabs(a.out) else a.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(page)
    print(json.dumps({"report": out, "review": rpath, "items": len(items), "total": round(total, 2)}, indent=1))


def cmd_apply(a):
    review = json.load(open(a.review))
    ref = review["items"]
    by = {d["sku"]: d for d in L.load_items()}

    def resolve(k):
        k = k.lstrip("#")
        return ref.get(k) or (k if k in by else None)

    sets, holds, accept = {}, set(), set()
    for s in a.set or []:
        k, v = s.split("=", 1)
        sku = resolve(k)
        if not sku:
            sys.exit(f"Unknown item '{k}'")
        sets[sku] = float(v.replace("$", ""))
    for k in a.hold or []:
        holds.add(resolve(k) or sys.exit(f"Unknown item '{k}'"))
    for k in a.accept or []:
        accept.add(resolve(k) or sys.exit(f"Unknown item '{k}'"))
    if a.accept_all:
        accept |= set(ref.values())
    done = []
    for sku in set(ref.values()):
        d = by[sku]
        pr = d.setdefault("pricing", {})
        if sku in holds:
            d["status"] = "hold"; L.log(d, "held"); L.save_item(d); done.append((sku, "hold")); continue
        if sku in sets:
            pr["final"] = sets[sku]
        elif sku in accept:
            pr["final"] = pr.get("proposed")
        else:
            continue
        pr["approved_at"] = L.today()
        if d.get("status") in ("new", "hold", None):
            d["status"] = "priced"
        L.log(d, "price_approved", price=pr["final"])
        L.save_item(d)
        done.append((sku, pr["final"]))
    L.rebuild_index()
    for sku, v in sorted(done):
        print(f"{sku}: {v}")
    left = [f"#{n} {s}" for n, s in ref.items() if s not in {x for x, _ in done}]
    if left:
        print("Not yet decided: " + ", ".join(left))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("todo"); t.add_argument("--status", default="new")
    p = sp.add_parser("propose"); p.add_argument("file"); p.add_argument("--no-charm", dest="charm", action="store_false")
    r = sp.add_parser("report"); r.add_argument("--status", default="new"); r.add_argument("--sku", nargs="*"); r.add_argument("--out", default="pricing/review.html")
    x = sp.add_parser("apply"); x.add_argument("--review", required=True); x.add_argument("--set", nargs="*")
    x.add_argument("--hold", nargs="*"); x.add_argument("--accept", nargs="*"); x.add_argument("--accept-all", action="store_true")
    a = ap.parse_args()
    {"todo": cmd_todo, "propose": cmd_propose, "report": cmd_report, "apply": cmd_apply}[a.cmd](a)


if __name__ == "__main__":
    main()
