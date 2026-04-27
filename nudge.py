#!/usr/bin/env python3
"""
nudge - a daily digest of your GitHub notifications
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path


CACHE_FILE = Path.home() / ".nudge_cache.json"

REASON_LABELS = {
    "assign": "assigned to you",
    "author": "you opened this",
    "comment": "you commented",
    "invitation": "invitation",
    "manual": "you subscribed",
    "mention": "mentioned you",
    "review_requested": "review requested",
    "security_alert": "security alert",
    "state_change": "state changed",
    "subscribed": "watching",
    "team_mention": "team mentioned",
    "ci_activity": "CI activity",
}

# notification types that usually need action from you
NEEDS_ACTION = {"mention", "review_requested", "assign", "security_alert", "invitation"}


def get_token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        # try reading from gh cli config — this is what gh stores it as
        config_path = Path.home() / ".config" / "gh" / "hosts.yml"
        if config_path.exists():
            try:
                import yaml  # type: ignore
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                token = config.get("github.com", {}).get("oauth_token")
            except Exception:
                pass

    if not token:
        print("[nudge] no GitHub token found")
        print("[nudge] set GITHUB_TOKEN or run: gh auth login")
        sys.exit(1)

    return token


def gh_request(path, token, params=None):
    url = f"https://api.github.com{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("[nudge] authentication failed — check your token")
            sys.exit(1)
        raise


def fetch_notifications(token, since=None, include_read=False):
    params = {"per_page": "100", "all": str(include_read).lower()}
    if since:
        params["since"] = since.isoformat()
    return gh_request("/notifications", token, params)


def group_by_repo(notifications):
    groups = defaultdict(list)
    for n in notifications:
        repo = n["repository"]["full_name"]
        groups[repo].append(n)
    return dict(groups)


def parse_time(s):
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def format_age(dt):
    if dt is None:
        return "?"
    now = datetime.now(timezone.utc)
    delta = now - dt
    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    return f"{days // 7}w ago"


def print_digest(groups, only_actionable=False):
    total = sum(len(v) for v in groups.values())
    if total == 0:
        print("\n  you're all caught up.")
        return

    action_count = sum(
        1 for ns in groups.values()
        for n in ns
        if n.get("reason") in NEEDS_ACTION
    )

    print(f"\n  {total} notification(s) across {len(groups)} repo(s)", end="")
    if action_count:
        print(f"  |  {action_count} need your attention")
    else:
        print()
    print()

    for repo, notifications in sorted(groups.items()):
        # filter if needed
        if only_actionable:
            notifications = [n for n in notifications if n.get("reason") in NEEDS_ACTION]
            if not notifications:
                continue

        print(f"  {repo}")

        for n in notifications:
            title = n["subject"]["title"]
            ntype = n["subject"]["type"]  # PullRequest, Issue, etc.
            reason = n.get("reason", "")
            reason_label = REASON_LABELS.get(reason, reason)
            updated = parse_time(n.get("updated_at"))
            age = format_age(updated)
            unread = "•" if n.get("unread") else " "
            needs = "!" if reason in NEEDS_ACTION else " "

            # truncate long titles
            if len(title) > 55:
                title = title[:52] + "..."

            type_abbr = {"PullRequest": "PR", "Issue": "IS", "Release": "RL", "Commit": "CM"}.get(ntype, ntype[:2])
            print(f"    {unread}{needs} [{type_abbr}] {title:<55}  {reason_label:<20}  {age}")

        print()


def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


def main():
    parser = argparse.ArgumentParser(
        description="nudge - GitHub notification digest"
    )
    parser.add_argument(
        "--since",
        type=int,
        default=24,
        metavar="HOURS",
        help="show notifications from the last N hours (default: 24)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="include already-read notifications"
    )
    parser.add_argument(
        "--actionable",
        action="store_true",
        help="only show notifications that need your action"
    )
    parser.add_argument(
        "--mark-read",
        action="store_true",
        help="mark all shown notifications as read (not implemented yet)"
    )
    args = parser.parse_args()

    token = get_token()

    since_dt = None
    if args.since:
        since_dt = datetime.now(timezone.utc) - timedelta(hours=args.since)

    print(f"[nudge] fetching notifications", end="")
    if since_dt:
        print(f" from the last {args.since}h...", end="")
    print()

    notifications = fetch_notifications(token, since=since_dt, include_read=args.all)

    if not isinstance(notifications, list):
        print(f"[nudge] unexpected response: {notifications}")
        sys.exit(1)

    groups = group_by_repo(notifications)
    print_digest(groups, only_actionable=args.actionable)

    if args.mark_read:
        # TODO: implement mark-as-read via PATCH /notifications
        print("[nudge] --mark-read not implemented yet")


if __name__ == "__main__":
    main()
