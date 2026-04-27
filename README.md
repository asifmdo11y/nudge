# nudge

GitHub notification digest with AI triage.

Fetches your notifications and uses Claude to sort them into three buckets: what needs a response today, what's worth reading later, and what you can skip. No more opening 40 notifications to find the 3 that actually matter.

```
$ python nudge.py

[nudge] fetching notifications from the last 24h...
[nudge] 31 notification(s) found
[nudge] triaging with Claude...

  You have a review request on the auth refactor that's blocking a deploy,
  and a direct mention on a prod incident thread that needs your input.

  Needs response today (3)

    [PR] myorg/api-service  —  feat: refactor token auth middleware
         review requested
    [IS] myorg/infra         —  prod: elevated 5xx rate on payment service
         mentioned you
    [PR] myorg/frontend      —  fix: CORS headers missing on /api/v2
         assigned to you

  Worth reading (8)
    [PR] myorg/api-service  —  chore: bump dependencies to latest
    [IS] myorg/docs          —  Update OAuth2 integration guide
    [PR] myorg/frontend      —  feat: dark mode toggle in settings
    ...

  Can skip (20) — workflows, api-service, infra, frontend, ...
```

## setup

```bash
git clone https://github.com/asifmdo11y/nudge
cd nudge
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...       # or: already logged in via gh CLI
python nudge.py
```

## usage

```bash
python nudge.py                  # last 24h, unread only, with AI triage
python nudge.py --since 48       # last 48 hours
python nudge.py --all            # include already-read
python nudge.py --no-ai          # raw list without Claude triage
```

## how it works

1. fetches notifications from the GitHub API (last N hours)
2. strips each notification down to: repo, title, type, reason, read status
3. sends the full list to Claude and asks it to triage into today / later / skip
4. Claude uses the notification reason (review_requested, mention, assign, etc.) plus title context to decide urgency
5. prints the triage in order of priority

## GitHub token

You need a token with `notifications` scope.

**Option 1**: already using `gh` CLI? nudge reads its token automatically.

**Option 2**: set `GITHUB_TOKEN` in your environment:
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

## requirements

- Python 3.10+
- `ANTHROPIC_API_KEY` environment variable
- `GITHUB_TOKEN` or `GH_TOKEN` (or `gh` CLI logged in)
