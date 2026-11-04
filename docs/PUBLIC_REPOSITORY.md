# Preparing a public source repository

The source tree contains the local Forma application and retained research modules. Create a fresh Python 3.12 virtual environment and install `requirements-forma.txt` as described in the root README. Dependency installation requires network access and native binary support; the ignored development runtime is not a distributable installation.

Manual CAD editing and deterministic exports do not need API credentials. For optional live proposals, copy `.env.example` to `.env` and fill the appropriate key locally. Studio's design planner uses Muse Wonder; the Spark variables in the example configure the independent API preflight helpers, not a verified provider switch for Studio. Provider adapters and model comparisons are separate work. Calling live verification or evaluation helpers may incur API usage; the normal offline test commands do not need a live provider.

## Source and local state

Keep source, tests, public examples, dependency specifications, browser assets and their licenses. Keep `.env`, credentials, local editor settings, virtual environments, generated projects, conversations, CAD exports, recordings, API receipts, caches, downloaded repositories and private engineering notes out of Git. The ignore rules cover the existing project locations and common alternate environments. Put ad-hoc private files in `local/` or `private/`, generated artifacts in `output/`, and downloaded source/runtime dependencies in `research/vendor/`.

An ignore rule does not remove an already tracked file or erase it from earlier commits. Inspect the candidate changes and the history before publishing:

```powershell
git status --short
git diff --check
git diff --cached --name-only
git ls-files
git log --all --stat
```

Use a secret scanner on both the working tree and reachable history. Pattern scans are a useful check, not proof that a repository contains no secrets. If a credential was committed, revoke it and assess history cleanup before publication. Never attach an evidence ZIP or a full workspace backup merely because the source tree passes a scan; archives need their own member and content review.

The intended public repository retains the complete development commit history. Historical commits and reports can contain workstation paths or account context removed from the current files; the owner has chosen to preserve that history. Do not rewrite, squash, discard commits or create an orphan publication branch. A source-review ZIP is only a review artifact: it does not contain or replace Git history. Private generated state remains excluded by the ignore rules.

Local evidence is intentionally absent from a normal clone. `/evaluation`, `/full17`, `/performance` and some historical report links require their locally generated ignored reports; source availability does not reproduce their recorded outcomes. The tracked protocols identify their own scope and limitations. Do not substitute replayed development results for untouched evaluation.

## Licensing and publication

Review `THIRD_PARTY_NOTICES.md` and retain the included component notices. The owner must choose a project-wide license if reuse rights beyond ordinary public GitHub viewing are intended. A public repository alone does not make the original source open source. Review branded demonstration examples before redistributing them commercially.

Preparing this checkout does not configure a remote, push commits, upload private state or deploy a server. The app remains local and has no production multi-user security boundary. Publication, public hosting, release archives and a production deployment are separate actions.
