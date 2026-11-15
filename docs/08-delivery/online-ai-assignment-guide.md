# Assignment 9: your module with an online AI tool

In this assignment you build **the module assigned to you** in `Fusion-Integrated`. You use
an online AI coding tool, run [`new-module-prompt.md`](new-module-prompt.md), and keep going
until an independent review scores the module **10/10 in all nine dimensions**.

`modules/placement` (Placement Cell) is the reference module. It is the only domain module
on `main`, because the ELM module from 6A has been removed. Do not look for ELM code, and do not
copy anything from a 6A pull request.

This is production work. If your mentor's own review agrees with your final score, your pull
request is merged and deployed as it is. Nobody will rewrite it after you.
[`student-assignment-guide.md`](student-assignment-guide.md) still applies wherever this
guide does not say otherwise. Where `definition-of-done.md` differs from the prompt, the
prompt governs: it already includes everything from that document that still applies.

## What changes from 6A

| | Assignment 6A | This assignment |
|---|---|---|
| Module | ELM, the same for everyone | the module assigned to you |
| AI | a local model through Ollama | an online AI tool that works inside your checkout |
| Prompt | `new-module-prompt.md` | the same prompt, now with stricter tests and a review loop (§10) |
| Finish line | the prompt's §8 | §8, then **10/10 in all nine dimensions** from [`module-review-prompt.md`](module-review-prompt.md) |
| Who scores it | your mentor | a fresh review session each round, then your mentor re-runs the review before merging |

## Your branch and your pull request: every command

`main` on `FusionIIIT/Fusion-Integrated` is the **production branch**: what is on it is what
gets deployed. You never commit to it. You make your own branch from the latest `main`, do all
your work there, and raise one pull request from that branch back into `main`.

In every command, replace `<your-username>` with your GitHub username and `<module_code>` with
your module code.

### 1. Once: fork and clone

Fork `FusionIIIT/Fusion-Integrated` on GitHub with the **Fork** button, or with the GitHub CLI:

```bash
gh repo fork FusionIIIT/Fusion-Integrated --clone=false
```

Clone your fork and connect it to the institute's repository:

```bash
git clone https://github.com/<your-username>/Fusion-Integrated.git
cd Fusion-Integrated
git remote add upstream https://github.com/FusionIIIT/Fusion-Integrated.git
git remote -v
```

`git remote -v` must show `origin` as your fork and `upstream` as `FusionIIIT`. Then make every
commit in this repository yours:

```bash
git config user.name "<your name>"
git config user.email "<the email on your GitHub account>"
```

### 2. Make your branch from the production branch

```bash
git fetch upstream
git checkout -b module/<module_code> upstream/main
git branch --show-current
```

The last command must print `module/<module_code>`. Never work on `main`, and never branch from
your fork's `main`, which falls behind.

### 3. Work and commit on your branch

Commit before every review round (Step 7). Add files by name, never with `git add .`: that is
how a `.env`, a key or a tool's files end up in a commit.

```bash
git status
git add modules/<module_code> client/src/modules/<module_code>
git add client/e2e/<module_code> docs/<NN>-<module_code>
git diff --cached --stat
git commit -m "<what changed, and why>"
```

When you change them, add the registration lines and generated files by name as well:
`config/settings/base.py`, `config/urls.py`, `config/celery.py`, `.importlinter`,
`client/src/app/registry.ts`, `client/e2e/accounts.ts`, `openapi/fusion-integrated.v1.yaml`,
`registry/permissions.json` and `docs/02-iam/permission-catalog.generated.md`. Read the
`git diff --cached --stat` output every time: nothing else should be in it.

### 4. Bring your branch up to date before the last review round

```bash
git fetch upstream
git rebase upstream/main
```

If a generated file conflicts (`openapi/fusion-integrated.v1.yaml`,
`registry/permissions.json` or `docs/02-iam/permission-catalog.generated.md`), take `main`'s
version and carry on. You regenerate it at the end:

```bash
git checkout upstream/main -- <the generated file>
git add <the generated file>
git rebase --continue
```

For any other conflict, edit the file until it is right, then run `git add <file>` and
`git rebase --continue`. To give up and go back to where you were, run `git rebase --abort`.

When the rebase has finished, regenerate and commit whatever changed:

```bash
make schema
make permissions
git add openapi/fusion-integrated.v1.yaml registry/permissions.json
git add docs/02-iam/permission-catalog.generated.md
git diff --cached --quiet || git commit -m "Regenerate the schema and permission manifest"
```

Then run every gate again, because a rebase is a change.

### 5. Push your branch to your fork

Only when your mentor says the module is ready (Step 9):

```bash
git push -u origin module/<module_code>
```

After a rebase your branch's history has changed, so push it with:

```bash
git push --force-with-lease origin module/<module_code>
```

Never force-push anything except your own branch.

### 6. Raise the pull request into the production branch

Write the description (Step 9) in a file outside the repository, so it is never committed.
Then, with the GitHub CLI:

```bash
gh pr create --repo FusionIIIT/Fusion-Integrated --base main \
  --head <your-username>:module/<module_code> \
  --title "<Module name>: <what it does, in one line>" \
  --body-file ../pr-description.md
```

Or on GitHub: open your fork, choose **Compare & pull request**, and check all four fields
before you create it:

- base repository: `FusionIIIT/Fusion-Integrated`
- base: `main`
- head repository: `<your-username>/Fusion-Integrated`
- compare: `module/<module_code>`

Never open it against your fork's `main` or another student's branch.

### 7. After review comments

Fix them on the same branch, then commit and push. The pull request updates itself:

```bash
git add <the files you changed>
git commit -m "<what you fixed>"
git push
```

Never open a second pull request for the same module.

## Step 1: Confirm your assignment and read your spec

These are Steps 1 and 2 of the student guide, unchanged.

Write these down before you open anything else. They fill the prompt's six blanks:

- your **module name**, from your mentor
- your **spec folder path**, from your mentor
- your **module code**, from your mentor
- your **docs folder number** (`NN`, as in `docs/NN-<module_code>/`), from your mentor
- your **spec id prefix** (for example `PC-BR-` and `PC-UC-` for Placement), which you
  read off your spec documents
- the **environment**, which is always `module-only` for this assignment

Then read every business rule (BR), use case (UC) and workflow document in your spec folder
yourself. Do this before you open the prompt. The AI will ask you questions only you can
answer, and you approve its blueprint. You cannot do either properly for a spec you have
not read.

## Step 2: Set up a clean environment and branch

Set up the `module-only` environment as in Step 3 of the student guide, with `fusionlab`
restored fresh from `fusion-dev.dump`:

- `docker compose up -d` starts Postgres and both Redis instances.
- The IAM runs separately, from `Fusion_System_Administrator`.
- `make dev` starts the platform.

Fork, clone and make your branch from the production branch, `main`, exactly as parts 1 and 2
of "Your branch and your pull request" above say.

Then install the browser the end-to-end tests use, once per machine:
`cd client && npx playwright install chromium`. Log in and check that Placement Cell works,
and that `make e2e` passes on `main`, before you start.

If a test account gets locked after too many failed sign-ins, release it from
`Fusion_System_Administrator/Backend/backend` with
`./../venv/bin/python manage.py unlock_login --user <username>`.

## Step 3: Pick your tools and tell your mentor

Both of your tools must meet four conditions:

- **It reads files and runs shell commands itself.** Chat-only web apps do not qualify.
- **It has a context window of at least 200k tokens.** The prompt alone is about 1,000
  lines.
- **Your plan's per-minute token limit allows one long request.** Some free tiers cap below
  that.
- **It runs on your machine, not in a cloud sandbox.** It must be able to run
  `docker compose`, reach `localhost` ports 5432, 6379, 6380 and 8001 (the IAM), and fetch
  from GitHub. Prove it before you start: ask it to run `make check` and
  `git fetch upstream`.

Tools that meet these:

- Claude Code
- Gemini CLI
- OpenAI Codex CLI
- GitHub Copilot in agent mode
- Cursor
- OpenCode, pointed at a hosted model that meets the context-window and token-limit conditions

Check GitHub Education's student benefits for free access to some of these.

You will use **two kinds of session**:

- **The builder:** one long session that runs `new-module-prompt.md` and writes the code.
- **The reviewer:** a **brand-new** session for every review round, which runs
  `module-review-prompt.md`. It must never be the builder's session.

If you can, use a different model for the reviewer than for the builder. For example,
build with one provider and review with another. A model goes easy on work that reads like
its own.

Before you start, tell your mentor:

- your builder tool and its exact model name
- your reviewer tool and its exact model name
- whether each one is on a free or paid plan

## Step 4: Keep secrets and real data out of the tool

Everything you paste or upload goes to the provider's servers.

**You may give the tool:**

- the `Fusion-Integrated` repository
- your own spec documents
- the synthetic `fusion-dev.dump` accounts

**You must never give it:**

- a `.env` file
- an API key, token or password
- anything from the production ERP, including screenshots
- any real person's data

`docker compose` reads `DB_PASSWORD` from a `.env` file in your checkout, which the tool can
see. Keep only local throwaway values in that file, never a password you use anywhere else.
Add `.env` to the tool's ignore or deny list as well.

**Put your API key in an environment variable, never in a file.** Run `git diff --cached`
before every commit. If a key reaches a commit, a chat or a screenshot, revoke it at the
provider straight away. Deleting the commit is not enough.

## Step 5: Stay in control of the agent

The tool runs real commands as you on your machine.

- **Read each command before you approve it.** You may always-allow only these:
  - `make check`
  - `make check-client`
  - `.venv/bin/pytest`
  - `npm test`
  - `git status`
  - `git diff`

  Approve everything else one command at a time.
- **Do not use auto-approve modes**, such as `--dangerously-skip-permissions`, `--yolo` or
  `--full-auto`.
- **Give the tool exactly three folders:**
  - your `Fusion-Integrated` checkout
  - your `Fusion_System_Administrator` checkout, which the tool needs to read the IAM and
    seed permissions
  - your spec folder, if it is not already inside the repository

  Start in `Fusion-Integrated` and add the others, for example with Claude Code's
  `--add-dir` or Gemini CLI's `--include-directories`. Give it nothing else from your
  machine. Do not commit the spec folder unless your mentor says so.
- **Never let the tool run `git commit`, `git push` or `gh pr create`.** You do those
  yourself.
- **Never commit the tool's own files,** such as `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`,
  `.cursorrules`, `.claude/`, `.cursor/`, `.gemini/`, `.codex/`, `.opencode/`,
  `opencode.json`, `.github/copilot-instructions.md` or `.github/instructions/`.
- **Turn web search off where the tool lets you.** Other students' pull requests are public,
  and a module copied from one is not yours.

## Step 6: Build with the prompt

1. Fill in the six blanks of `new-module-prompt.md` with your Step 1 values. Replace each
   one everywhere it appears, not only in §0.
2. Paste everything from `--- PROMPT BEGINS ---` to `--- PROMPT ENDS ---` into a fresh
   builder session.
3. Do not trim, summarise or add to the prompt.

From there the prompt drives itself, with the same gates as 6A:

- You answer Phase 1's questions from your own reading of the spec.
- **No application code is written until your mentor approves the blueprint.**
- When the prompt says to stop and report, you stop and report.

Every approval the prompt asks for comes from your mentor, in writing. That means:

- the blueprint
- any known gap
- any change outside your module's own folders
- any new dependency

Keep a link to, or an exact dated copy of, each approval, and say where it was given. The
quality report records them. The reviewer treats an approval with no record as missing, and
your mentor checks each one against their own messages.

**When the session runs out of context or hits a rate limit,** start a new builder session
with:

- the prompt (with the blanks filled in)
- the approved blueprint
- the latest review findings, if there are any
- a three-line note on where you stopped

## Step 7: Review, fix, repeat until 10/10

When the builder says the module is ready and the quality report
(`docs/<NN>-<module_code>/<module_code>-quality-report.md`) is written:

1. **Commit everything locally on `module/<module_code>`, but do not push.** Use part 3 of
   "Your branch and your pull request". The reviewer only reads committed code, and stops if
   it finds uncommitted changes. (This replaces the student guide's "do not commit until your
   mentor says": here you commit locally before every round, and you push only when your
   mentor says.)
2. **Make a clean copy for the reviewer.** Clone your branch into a new folder for each
   round, so the reviewer never shares a folder, a memory or an instruction file with the
   builder:

   ```bash
   git clone --branch module/<module_code> <path-to-your-checkout> ../review-r<N>
   cd ../review-r<N>
   git remote add upstream https://github.com/FusionIIIT/Fusion-Integrated.git
   git fetch upstream
   cp <path-to-your-checkout>/.env .
   make install
   cd client && npm ci && cd ..
   ```

   Stop the builder's `make dev` and `npm run dev` before the round. The reviewer starts its
   own from the clone, and refuses to run `make e2e` if something else is already serving.

   Turn off the tool's memory feature for the reviewer session. Move any global or
   parent-folder instruction file aside, such as `~/.claude/CLAUDE.md`,
   `~/.gemini/GEMINI.md`, `~/.codex/AGENTS.md` or `~/.config/opencode/AGENTS.md`. Clear
   Cursor's User Rules. The reviewer checks for these files and stops if it finds one.
3. **Open a brand-new reviewer session in that folder.** Give it the folder, your spec folder
   and your `Fusion_System_Administrator` checkout. Do not paste the review prompt itself.
   Send only this, with the six values filled in:

   ```text
   Run `git fetch upstream`. Then follow, exactly, the text between the PROMPT markers of
   `git show upstream/main:docs/08-delivery/module-review-prompt.md`, with these blanks:
   MODULE_NAME=… BRANCH=… SPEC_FOLDER_PATH=… module_code=… NN=… ROUND=1
   ```

   The reviewer then reads the rules from `main`, where nobody can trim them.
4. **Let the reviewer finish.** It re-runs every check itself and returns a scorecard,
   numbered findings and a verdict.
5. **Paste the findings into the builder session.** The builder fixes every one, re-runs
   every gate and updates the quality report.
6. **Commit the fixes, then run the next round in a new clone and another brand-new reviewer
   session,** with `[ROUND]` increased by
   one. Never reuse a reviewer session. It remembers its own findings and only re-checks
   those.
7. **Stop only when a review of your latest commit returns**
   `VERDICT: 10/10 in all nine dimensions`. Even a one-line change after that needs another
   round.

**Rebase before the round you expect to be the last, not after it.** Use part 4 of "Your
branch and your pull request": rebase onto `upstream/main`, then regenerate the schema and the
permission manifest (Step 7.10 of the prompt). If `upstream/main` moves after you get a 10/10, rebase again. Then:

- If you resolved conflicts only in the registration lines and the regenerated files, and
  changed nothing in your module's own folders, re-run the gates (`make check`,
  `make check-client`, `make e2e`, both coverage runs). Record their output in the pull request
  description. You do not need a new round.
- Otherwise, run one more round.

Six rules keep the loop honest:

- **Every round counts. Never re-run a round to get a better score.** Save every
  reviewer's full output, unedited, and hand them all in with your run record. A round you
  ran but did not hand in counts as failed.

- **Do not edit the review prompt, and do not ask the reviewer to be lenient.** Do not hand
  it the builder's opinion of the findings. A 10 that you talked a model into is worthless,
  and your mentor's own review will not repeat it.
- **If the builder disagrees with a finding, take it to your mentor.** Bring the evidence.
  Do not drop the finding quietly.
- **If the same finding comes back three rounds in a row, stop and ask your mentor.** It is
  a disagreement about the spec or the architecture, and patching will not end it.
- **If round 6 is not 10/10, stop.** Send every review to your mentor. In writing, they mark
  each open finding "fix" or "waive" and answer each open question. Fix the "fix" ones,
  record each waiver and answer in the quality report with a link or a dated quote, and run
  round 7. After round 7, your mentor's written ruling on whatever is still open replaces
  the 10/10, and their own review of the pull request checks the "fix" items. A security
  Blocker is always "fix".
- **Never run tests in the builder while a review is running.** Both use the same Postgres,
  and two test runs at once destroy each other's test database.

## Step 8: Check it yourself

The tool wrote the code, but you are the one submitting it. Before the pull request:

- Run `make check`, `make check-client` and `make e2e` yourself, and read the output.
- Read the whole diff. You must be able to explain any file in it, because your mentor will
  ask.
- Walk your module in the browser as each role and as the plain user.

## Step 9: Commit and open the pull request

- Commit under your own GitHub identity. **No AI attribution anywhere:** not in code,
  comments, commit messages, docs or the pull request. Some tools add a co-author line or
  change the author name by default. Run these three checks:

  ```bash
  git log --format=%B upstream/main..HEAD | grep -i -E 'co-authored|generated (with|by)|aider|copilot|claude|gemini|chatgpt|deepseek|codex|opencode|openai|anthropic'
  git log --format='%an <%ae> | %cn <%ce>' upstream/main..HEAD | sort -u
  git diff --name-only upstream/main...HEAD | grep -i -E '(CLAUDE|GEMINI|AGENTS)\.md|\.cursorrules|\.aider|\.(cursor|claude|gemini|codex|opencode)/|opencode\.json|copilot-instructions'
  ```

  The first and third must print nothing. The second must show only you.
- Push and open the pull request only when your mentor says the module is ready, with parts 5
  and 6 of "Your branch and your pull request".
- Open the pull request from `module/<module_code>` into the production branch, `main`, on
  `FusionIIIT/Fusion-Integrated`. In the description, give:
  - your spec folder
  - a link to the blueprint
  - a link to the quality report
  - the final scorecard
  - any change outside your module's own folders, and who approved it

  Do not name the AI tool.

After you open it, your mentor runs `module-review-prompt.md` again in their own session. A
pull request that does not score 10 in all nine dimensions comes back to you with the
findings.

## Step 10: Hand in your run record

The run record is one Markdown file. Give it to your mentor with your pull request link.
**Do not commit it,** because it names the AI tools.

```markdown
# Run record: <module_code>

Team (roll numbers):
Pull request:

## Tools
- Builder: tool, exact model, plan (free / paid), cost
- Reviewer: tool, exact model, plan (free / paid), cost
- Web search: off / on (if on, every URL it fetched)

## Review rounds
| Round | Spec | Arch | Code | Security | Tests | E2E | Frontend | Ops | Hygiene | Open findings |
|-------|------|------|------|----------|-------|-----|----------|-----|---------|---------------|

## Builder sessions
| # | Date | Prompt steps covered | Why it ended (done / context full / rate limit / crash) |
|---|------|----------------------|----------------------------------------------------------|

## Things you did by hand
| Prompt step | What you changed or re-prompted | Why |
|-------------|---------------------------------|-----|

## Things the tool made up, and how you caught them
| What (file, function, package, endpoint, role, spec id) | Caught by | Round |
|----------------------------------------------------------|-----------|-------|

## What you learned (5 to 10 lines)
```

Attach every reviewer's full output, round by round, unedited.

## Self-check before you ask for review

- [ ] The module is your assigned one, built on a branch from the latest `main`, with
      nothing taken from a 6A pull request or another team
- [ ] The prompt went in unchanged, with your six blanks filled in everywhere they appear
- [ ] Your mentor approved the blueprint before any application code was written
- [ ] The final review was made in a fresh session on your latest commit, or on the commit
      before a registration-only rebase (Step 7), and says
      `VERDICT: 10/10 in all nine dimensions`
- [ ] Every approval (blueprint, gaps, shared-file changes, dependencies) is recorded in the
      quality report with a link or a dated quote
- [ ] You ran `make check` and `make check-client` yourself, and both are green
- [ ] The quality report is committed, its numbers came from runs after the last change, and
      it names no AI tool
- [ ] No auto-approve mode was used, and the tool made no commit or push itself
- [ ] The three attribution checks in Step 9 come out clean, and `git diff` shows no key,
      `.env` file, tool config file or real person's data
- [ ] You can explain every file in the diff
- [ ] Your run record is complete and handed to your mentor, not committed
