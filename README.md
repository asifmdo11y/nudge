# nudge

A no-nonsense GitHub notification digest. Instead of opening the GitHub notifications tab and losing 20 minutes, run this and see exactly what needs your attention.

```
$ python nudge.py

[nudge] fetching notifications from the last 24h...

  14 notification(s) across 5 repo(s)  |  3 need your attention

  myorg/api-service
    •! [PR] fix: handle null user in token refresh                    review requested      2h ago
    •  [IS] Add rate limiting to public endpoints                      you commented         5h ago
       [PR] chore: bump dependencies                                   watching              1d ago

  myorg/frontend
    •! [PR] feat: new dashboard layout                                 review requested      3h ago
       [IS] Safari CSS bug on login page                               mentioned you         6h ago

  ...
```

Notifications marked with `!` need something from you (review, mention, assignment, etc).

## usage

```bash
python nudge.py                     # last 24 hours (unread only)
python nudge.py --since 48          # last 48 hours
python nudge.py --all               # include already-read notifications
python nudge.py --actionable        # only show ones that need action
```

## setup

You need a GitHub token with `notifications` scope.

**Option 1**: if you have `gh` CLI installed and logged in, it works automatically.

**Option 2**: set `GITHUB_TOKEN` in your environment:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Then:

```bash
git clone https://github.com/asifmdo11y/nudge
cd nudge
python nudge.py
```

No dependencies beyond Python stdlib. (The `yaml` import is optional and only used if you have the gh CLI config — it falls back gracefully.)

## why

GitHub's notification UI is fine but I wanted something I could pipe into a script, run from cron, or just glance at in the terminal without context-switching to the browser. This does that.

---

authored by asif
