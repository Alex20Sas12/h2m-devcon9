"""CLI: python h2m.py "headline" [--snippet TEXT] [--approve ID] [--list]

Headless twin of the web desk — same pipeline, same store.
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Headline to Market — draft settleable prediction markets")
    ap.add_argument("headline", nargs="?", help="news headline to turn into a market")
    ap.add_argument("--snippet", default="", help="optional article snippet for context")
    ap.add_argument("--model", default=None, help="override LLM model name")
    ap.add_argument("--list", action="store_true", help="list saved drafts")
    ap.add_argument("--approve", metavar="ID", help="approve a pending draft")
    ap.add_argument("--discard", metavar="ID", help="discard a pending draft")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    import store
    from pipeline import draft_market

    if args.list:
        rows = store.list_drafts()
        print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else
              "\n".join(f"{r['id']}  {r['status']:9}  {r['kind']:6}  {r['headline'][:60]}" for r in rows))
        return 0
    if args.approve or args.discard:
        did = args.approve or args.discard
        ok = store.decide(did, "approved" if args.approve else "discarded")
        print("decided:", did, ok)
        return 0 if ok else 1
    if not args.headline:
        ap.print_help()
        return 2

    res = draft_market(args.headline, args.snippet, model=args.model)
    did = store.save(args.headline, args.snippet, res.verdict.kind,
                     res.verdict.model_dump(mode="json"), res.model)
    payload = {"id": did, **res.model_dump(mode="json")}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        v = res.verdict
        print(f"[{v.kind.upper()}] saved as {did}")
        if v.kind == "draft":
            print(f"  Q:        {v.question}")
            print(f"  closes:   {v.close_date}")
            print(f"  source:   {v.resolution_source_name} <{v.resolution_source_url}>")
            print(f"  rule:     {v.resolution_rule}")
            print(f"  YES:      {v.yes_criteria}")
            print(f"  NO:       {v.no_criteria}")
            print("  edge cases:")
            for e in v.edge_cases:
                print(f"    - {e}")
            print(f"  why:      {v.rationale}")
        else:
            for r in v.reasons:
                print(f"  reason:   {r}")
            print(f"  rewrite:  {v.rewrite_hint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
