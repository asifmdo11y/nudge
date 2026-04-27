#!/usr/bin/env python3
"""
nudge - GitHub notification digest with AI triage

fetches your GitHub notifications and uses Claude to prioritize them:
what actually needs a response today, what can wait, and what you can ignore.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

import anthropic


TRIAGE_PROMPT = """You are a software engineer helping triage GitHub notifications.

Here are the current GitHub notifications for this developer:

{notifications}

Triage these into three buckets:

1. **Needs response today** — you're blocked, someone is waiting, review requested, direct mention
2. **Worth reading** — relevant but not urgent, can wait until tomorrow
3. **Can skip** — subscribed by default, automated noise, already resolved context

For each notification, give:
- Which bucket it belongs to
- One-line reason

Then write a brief summary at the top: what's the most important thing to deal with right now?

Be direct. Engineers are busy. Don't over-explain.

Return a JSON object:
{{
  "headline": "1-2 sentence summary of what actually needs attention",
  "today": [
    {{ "repo": "...", "title": "...", "type": "PR/Issue/etc", "reason": "why now" }}
  ],
  "later": [
    {{ "repo": "...", "title": "...", "type": "...", "reason": "..." }}
  ],
  "skip": [
    {{ "repo": "...", "title": "...", "type": "...", "reason": "..." }}
  ]
}}

Return only valid JSON.
"""


REASON_LABELS = {
    "assign": "assigned to you",
    "author": "you opened this",
    "comment": "you commented",
    "mention": "mentioned you",
    "review_requested": "review requested",
    "security_alert": "security alert",
    "state_change": "state changed",
    "subscribed": "watching",
    "team_mention": "team mentioned",
    "ci_activity": "CI activity",
}


def get_token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        # try gh CLI config
        from pathlib import Path
        config = Path.home() / ".config" / "gh" / "hosts.yml"
        if config.exists():
            try:
                import yaml
                with open(config) as f:
                    data = yaml.safe_load(f)
                token = data.get("github.com", {}).get("oauth_token")
            except Exception:
                pass

    if not token:
        print("[nudge] no GitHub token found")
        print("[nudge] set GITHUB_TOKEN or run: gh auth login")
        sys.exit(1)

    return token


def gh_get(path, token, params=None):
    url = f"https://api.github.com{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("[nudge] auth failed — check your GitHub token")
            sys.exit(1)
        raise


def fetch_notifications(token, since_hours=24, include_read=False):
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    params = {
        "per_page": "50",
        "all": str(include_read).lower(),
        "since": since.isoformat(),
    }
    return gh_get("/notifications", token, params)


def flatten_for_llm(notifications: list) -> list[dict]:
    """Reduce notification objects to what Claude actually needs."""
    items = []
    for n in notifications:
        items.append({
            "repo": n["repository"]["full_name"],
            "title": n["subject"]["title"],
            "type": n["subject"]["type"],
            "reason": REASON_LABELS.get(n.get("reason", ""), n.get("reason", "")),
            "unread": n.get("unread", False),
            "updated": n.get("updated_at", ""),
        })
    return items


def triage_with_claude(client: anthropic.Anthropic, notifications: list) -> dict:
    flat = flatten_for_llm(notifications)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": TRIAGE_PROMPT.format(notifications=json.dumps(flat, indent=2))
        }]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"headline": raw, "today": [], "later": [], "skip": []}


def print_triage(triage: dict, total: int):
    headline = triage.get("headline", "")
    if headline:
        print(f"\n  {headline}\n")

    today = triage.get("today", [])
    later = triage.get("later", [])
    skip = triage.get("skip", [])

    if today:
        print(f"  Needs response today ({len(today)})")
        print()
        for item in today:
            print(f"    [{item.get('type', '?')[:2].upper()}] {item['repo']}  —  {item['title'][:60]}")
            print(f"         {item.get('reason', '')}")
        print()

    if later:
        print(f"  Worth reading ({len(later)})")
        for item in later:
            print(f"    [{item.get('type', '?')[:2].upper()}] {item['repo']}  —  {item['title'][:60]}")
        print()

    if skip:
        print(f"  Can skip ({len(skip)}) — {', '.join(set(i['repo'].split('/')[1] for i in skip[:5]))}, ...")
        print()


def print_raw(notifications: list):
    """Fallback table view without AI."""
    if not notifications:
        print("\n  you're all caught up.")
        return

    from collections import defaultdict
    by_repo = defaultdict(list)
    for n in notifications:
        by_repo[n["repository"]["full_name"]].append(n)

    print(f"\n  {len(notifications)} notification(s) across {len(by_repo)} repo(s)\n")

    for repo, items in sorted(by_repo.items()):
        print(f"  {repo}")
        for n in items:
            title = n["subject"]["title"][:55]
            reason = REASON_LABELS.get(n.get("reason", ""), "")
            unread = "•" if n.get("unread") else " "
            ntype = n["subject"]["type"][:2]
            print(f"    {unread} [{ntype}] {title:<55}  {reason}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="nudge - GitHub notification digest with AI triage"
    )
    parser.add_argument("--since", type=int, default=24, metavar="HOURS",
                        help="look back N hours (default: 24)")
    parser.add_argument("--all", action="store_true",
                        help="include already-read notifications")
    parser.add_argument("--no-ai", action="store_true",
                        help="show raw notification list without triage")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.no_ai:
        print("[nudge] ANTHROPIC_API_KEY not set — use --no-ai for raw list")
        sys.exit(1)

    token = get_token()

    print(f"[nudge] fetching notifications from the last {args.since}h...", flush=True)
    notifications = fetch_notifications(token, since_hours=args.since, include_read=args.all)

    if not isinstance(notifications, list):
        print(f"[nudge] unexpected response: {notifications}")
        sys.exit(1)

    if not notifications:
        print("[nudge] no notifications — you're all caught up.")
        sys.exit(0)

    print(f"[nudge] {len(notifications)} notification(s) found")

    if args.no_ai:
        print_raw(notifications)
        return

    print("[nudge] triaging with Claude...\n")
    client = anthropic.Anthropic(api_key=api_key)
    triage = triage_with_claude(client, notifications)
    print_triage(triage, total=len(notifications))


if __name__ == "__main__":
    main()
