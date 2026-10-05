# Publish the inspected source — live API execution is separate

**Status:** locally prepared, not publicly hosted. The source code and benchmark remain v0.2.0.
No live API request is necessary to publish or rerun the offline checks. No credential is included.

## Contents and review boundary

Upload the contents of the extracted `traceledger` directory so `README.md`, `pyproject.toml`,
`data`, `tests`, `traceledger`, `reports` and `docs` are at the repository root. Include `.gitignore`
and the hidden `.github` directory when using Git. This is a public-source publication candidate,
not a claim that a repository already exists or that an open-source license has been selected.

The raw private conversation export is excluded. Private message identifiers have been omitted from
`docs/CASE_REVIEW.md`; selected historical excerpts and dates remain for owner review. The aggregate
corpus audit remains, but a public reviewer cannot independently re-count the withheld source.
Older application documents have been excluded to avoid conflicting release claims.

## Preferred connection workflow

Connect GitHub in ChatGPT, then inspect the available repository-write actions. Choose the owner's
approved new repository destination and public visibility. No repository is created by connecting alone.
Publish only this inspected folder, not the working directory containing private source material.

## Local alternative with Git and GitHub CLI

Run these from the extracted `traceledger` folder, after reviewing its content and authenticating
GitHub CLI with `gh auth login`. Review `git status` before staging. These commands are instructions,
not a record of actions already performed.

```powershell
git init -b main
git status --short
git add .
git commit -m "Publish TraceLedger v0.2 work sample"
gh repo create traceledger-evals --public --source=. --remote=origin --push
gh repo view --json url --jq .url
```

The `gh repo create` command creates a public repository and pushes its source. Do not run it against
an unintended folder or an existing repository without inspecting that repository first. If the chosen
name already exists, stop and inspect; do not overwrite or force-push unrelated work.

## Verify before adding the URL to an application

Open the actual returned repository URL without signing in. Confirm the README, task data, graders
and local results are readable. From a fresh checkout, run:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
```

For Linux/macOS use `python3 -m venv .venv` and `.venv/bin/python` for the subsequent commands.
Review any hosted CI result before claiming it passed. Only then replace the repository-pending
line in the résumé, supplement and release status with the verified URL. Live SDK/service integration,
model benchmarking and training remain pending unless separately completed and documented.

GitHub Free includes public repositories. This guide does not enable API billing or paid testing.
A public repository is not automatically a licensed open-source release; the owner can choose a
license separately.

## Official documentation checked October 5, 2026

- Repository plans and visibility: https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories
- Importing local code: https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
