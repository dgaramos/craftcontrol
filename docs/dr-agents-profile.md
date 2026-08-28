# CraftControl agent review profile

The tool-neutral profile at `.dr-agents/craftcontrol/PROFILE.md` is the
source of CraftControl-specific review safeguards. It stays in this repository
so it evolves with its architecture, quality gates, and operational rules.

## Repository-native reviewers

The Cody DR and Claudio DR `review-pr` entry points load the local profile
before evaluating a PR or ref. They remain manually invoked and retain their
incremental re-review behavior.

## Portable reviewers

When using an installed Cody DR or Claudio DR plugin, provide the profile path
explicitly with the requested PR/ref:

```text
Review https://github.com/dgaramos/craftcontrol/pull/123 using
.dr-agents/craftcontrol/PROFILE.md.
```

The profile does not contain publisher credentials. If an adapter or the local
profile is unavailable, use the repository-native `review-pr` entry point; no
GitHub App, plugin installation, or PR history is changed by this fallback.
