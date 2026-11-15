# Assignment 9: your module with an online AI tool

In this assignment your pair builds **the module assigned to you** in `Fusion-Integrated`. You
use online AI coding tools, run [`new-module-prompt.md`](new-module-prompt.md), and keep going
until an independent review scores the module **10/10 in all nine dimensions**.

## Read this first: two students, two AI models

You work as a pair on one module, in two phases. Both of you read this whole guide before
anything else.

1. **Student 1 builds, alone, until 10/10.** Steps 1 to 7 are Student 1's, exactly as written:
   build the module with one AI tool and review it until it scores 10/10. Student 2's only part
   before then is to approve, in writing, what Student 1's prompt asks to have approved, such as
   the blueprint (Step 6). Student 2 also reads the spec (Step 1), sets up (Step 2) and follows
   Steps 3 to 5 for Student 2's own tool.
2. **Then Student 2 tests and reviews, with a different AI model.** Student 2 starts only after
   that 10/10. Using a model from a **different provider** than Student 1's, Student 2 writes
   tests from the spec the way Assignment 8 did, runs them, and reviews the code (Step 8).
3. **Student 1 fixes, Student 2 checks again, until nothing is found.** Everything that fails
   goes back to Student 1. The loop ends only when all of Student 2's tests pass and Student 2's
   review finds nothing (Step 9).

Neither of you does the other's part. Student 1 never edits Student 2's tests, and Student 2
never edits the module's code. Git records who changed what, and the reviewer checks it.

**There is no mentor in this assignment.** Student 2 gives every approval Student 1's prompt
asks for, and the two of you settle every question between yourselves, from the spec. Wherever
`student-assignment-guide.md` or the prompts mention a mentor, read "Student 2" for an approval
and "both of you together" for a ruling. When the loop ends, Student 1 raises the pull
request.

`modules/placement` (Placement Cell) is the reference module. It is the only domain module
on `main`, because the ELM module from 6A has been removed. Do not look for ELM code, and do not
copy anything from a 6A pull request.

This is production work. If the review of your pull request agrees with your final score, it
is merged and deployed as it is. Nobody will rewrite it after you.
[`student-assignment-guide.md`](student-assignment-guide.md) still applies wherever this
guide does not say otherwise. Where `definition-of-done.md` differs from the prompt, the
prompt governs: it already includes everything from that document that still applies.

## What changes from 6A

| | Assignment 6A | This assignment |
|---|---|---|
| Module | ELM, the same for everyone | the module assigned to your pair |
| People | one student | a pair: Student 1 builds, then Student 2 tests and reviews |
| AI | a local model through Ollama | two online AI tools from different providers, one per student |
| Prompt | `new-module-prompt.md` | the same prompt, now with stricter tests and a review loop (§10), plus Assignment 8's prompts for Student 2 ([`spec-test-prompts.md`](spec-test-prompts.md)) |
| Finish line | the prompt's §8 | §8, then **10/10 in all nine dimensions** from [`module-review-prompt.md`](module-review-prompt.md), then every one of Student 2's spec tests passing and Student 2's review at 10/10 |
| Who scores it | your mentor | a fresh review session each round, Student 2's model after the 10/10, then the review is re-run on the pull request before merging |
| Who approves | your mentor | Student 2, for Student 1's blueprint and other approvals; both students together for any ruling |

## Your branch and your pull request: every command

`main` on `FusionIIIT/Fusion-Integrated` is the **production branch**: what is on it is what
gets deployed. You never commit to it. Student 1 makes the pair's branch from the latest `main`
on Student 1's fork. Both of you work there, and Student 1 raises one pull request from that
branch back into `main`. This replaces the student guide's rule that you do not share a branch
with another student.

Parts 1 to 7 are Student 1's. Part 8 is how Student 2 joins the same branch. In every command,
replace `<your-username>` with your GitHub username and `<module_code>` with your module code.

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
`git diff --cached --stat` output every time: nothing else should be in it. From Step 9 on, it
must list nothing under `modules/<module_code>/tests/spec/` or
`docs/<NN>-<module_code>/spec-tests/`, which are Student 2's. If it does, run
`git restore --staged <path>` for that path.

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

Push for the first time when your module reaches 10/10 at the end of Step 7, so that Student 2
can start:

```bash
git push -u origin module/<module_code>
```

After that, pick up Student 2's commits before every push:

```bash
git pull --rebase origin module/<module_code>
git push
```

A rebase onto `upstream/main` (part 4) changes the branch's history, so do it in this order:

1. Student 2 pushes everything and stops committing.
2. Student 1 runs `git pull --rebase origin module/<module_code>`, then part 4, then pushes
   straight away, with no pull in between:

   ```bash
   git push --force-with-lease origin module/<module_code>
   ```

3. Student 2, with nothing unpushed, runs `git pull --rebase origin module/<module_code>`. A
   rebase gives every commit a new hash, so Student 2 then updates the hashes in `triage.md`.

Never force-push anything except your own branch. Pushing to your fork is not a pull request:
open that only in Step 11.

### 6. Raise the pull request into the production branch

Write the description (Step 11) in a file outside the repository, so it is never committed.
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

### 8. Student 2: join the branch

Student 1 adds Student 2 as a collaborator on Student 1's fork, once. On GitHub, use
**Settings → Collaborators → Add people**, or the GitHub CLI:

```bash
gh api -X PUT repos/<student-1-username>/Fusion-Integrated/collaborators/<student-2-username> \
  -f permission=push
```

Student 2 accepts the invitation from the email or the GitHub notification, then clones the
branch and sets up as in part 1:

```bash
git clone --branch module/<module_code> \
  https://github.com/<student-1-username>/Fusion-Integrated.git
cd Fusion-Integrated
git remote add upstream https://github.com/FusionIIIT/Fusion-Integrated.git
git config user.name "<your name>"
git config user.email "<the email on your GitHub account>"
```

Student 2 commits only the spec tests and their documents, by name, and pulls before every push:

```bash
git add docs/<NN>-<module_code>/spec-tests
git add modules/<module_code>/tests/spec      # once the tests exist (Step 8, item 5)
git diff --cached --stat
git commit -m "<what changed, and why>"
git pull --rebase origin module/<module_code>
git push origin module/<module_code>
```

`git diff --cached --stat` must list nothing outside those two folders.

## Step 1: Confirm your assignment and read your spec

These are Steps 1 and 2 of the student guide, unchanged.

Write these down before you open anything else. They fill the prompt's six blanks:

- your **module name**, from your assignment
- your **spec folder path**, from your assignment
- your **module code**, from your assignment
- your **docs folder number** (`NN`, as in `docs/NN-<module_code>/`), from your assignment
- your **spec id prefix** (for example `PC-BR-` and `PC-UC-` for Placement), which you
  read off your spec documents
- the **environment**, which is always `module-only` for this assignment

Then read every business rule (BR), use case (UC) and workflow document in your spec folder
yourself. Do this before you open the prompt. The AI will ask you questions only you can
answer, and you approve its blueprint. You cannot do either properly for a spec you have
not read. Student 2 reads the same documents before Step 8, plus the Problem Statement and the
requirements (CFR/AFR), which Student 2's tests are designed from.

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

## Step 3: Pick your tools

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

**Student 1 uses one tool for two kinds of session:**

- **The builder:** one long session that runs `new-module-prompt.md` and writes the code.
- **The reviewer:** a **brand-new** session for every review round, which runs
  `module-review-prompt.md`. It must never be the builder's session.

**Student 2 uses a different model, from a different provider.** For example, if Student 1
builds with a Claude model, Student 2 uses a Gemini or GPT model. Student 2's tool writes the
spec tests and runs every review from Step 8 on. A model goes easy on work that reads like its
own, so Student 2's model must never be the one that built the module.

Before you start, write down for the run record (Step 12):

- Student 1's tool and its exact model name
- Student 2's tool and its exact model name
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
  machine. Do not commit the spec folder. Student 2's Prompt A
  sessions are the one exception: they get only a folder of spec documents (Step 8).
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
- **No application code is written until Student 2 approves the blueprint.**
- When the prompt says to stop and report, you stop and report.

Every approval the prompt asks for comes from Student 2, in writing. Student 2 reads the
blueprint against the spec before approving it. That means:

- the blueprint
- any known gap
- any change outside your module's own folders
- any new dependency

Keep a link to, or an exact dated copy of, each approval, and say where it was given. The
quality report records them. The reviewer treats an approval with no record as missing, and
Student 2 checks each one against their own messages.

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
   mentor says": here you commit locally before every round, and you push for the first time
   when the module reaches 10/10, in item 7.)
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
   round. Then push the branch (part 5 of "Your branch and your pull request") and tell
   Student 2 the commit hash: Step 8 starts from it. If your pair's decision after round 7
   replaced the 10/10, Step 8 starts from the commit that decision covers.

**Rebase before your last Step 7 round, not after it.** Use part 4 of "Your branch and your
pull request": rebase onto `upstream/main`, then regenerate the schema and the permission
manifest (Step 7.10 of the prompt). If `upstream/main` moves during Steps 8 and 9, Student 1
rebases again, in the order part 5 gives, before the Q round you expect to be the last. Then:

- If you resolved conflicts only in the registration lines and the regenerated files, and
  changed nothing in your module's own folders, re-run the gates (`make check`,
  `make check-client`, `make e2e`, both coverage runs). Record their output in the pull request
  description. You do not need a new round.
- Otherwise, run one more round: Student 1's in Step 7, or Student 2's in Step 9.

Six rules keep the loop honest:

- **Every round counts. Never re-run a round to get a better score.** Save every
  reviewer's full output, unedited, and hand them all in with your run record. A round you
  ran but did not hand in counts as failed.

- **Do not edit the review prompt, and do not ask the reviewer to be lenient.** Do not hand
  it the builder's opinion of the findings. A 10 that you talked a model into is worthless,
  and the review of your pull request will not repeat it.
- **If the builder disagrees with a finding, take it to Student 2.** Bring the evidence and
  decide together. Do not drop the finding quietly.
- **If the same finding comes back three rounds in a row, stop and settle it with Student 2.**
  It is a disagreement about the spec or the architecture, and patching will not end it.
- **If round 6 is not 10/10, stop.** Go through every review with Student 2. Together, in
  writing, mark each open finding "fix" or "waive" and answer each open question. Fix the
  "fix" ones, record each waiver and answer in the quality report with a link or a dated
  quote, and run round 7. After round 7, your pair's written decision on whatever is still
  open replaces the 10/10, and the review of the pull request checks the "fix" items. A
  security Blocker is always "fix".
- **Never run tests in the builder while a review is running.** Both use the same Postgres,
  and two test runs at once destroy each other's test database.

## Step 8: Student 2 tests the module from the spec

Student 2 starts here, from the commit that scored 10/10 in Step 7, with Student 2's own AI
tool. Every prompt is in [`spec-test-prompts.md`](spec-test-prompts.md). This is Assignment 8's
method: the tests are designed from the spec alone, before your AI sees any code.

1. **Join the branch and set up.** Use part 8 of "Your branch and your pull request". Then set
   up your environment as in Step 2, except its fork-and-branch paragraph, which part 8
   replaces. Check that `make check` passes on Student 1's commit.
2. **Design the tests from the spec, one strategy at a time.** For FR, UC, BR and WF in turn,
   open a brand-new session in a folder that holds only the Problem Statement and that
   strategy's documents. Turn the tool's memory off and move instruction files aside first, as
   in Step 7, item 2. Run Prompt A there. Save each output unchanged as
   `docs/<NN>-<module_code>/spec-tests/<STRATEGY>_DESIGN.json`.
3. **Freeze the design and commit it on its own.** Check that each file covers every obligation
   its strategy requires, and that every `source_id` starts with an id exactly as the spec
   writes it. If a file fails either check, delete it and run Prompt A again in a new session.
   Then commit the four design files, and nothing else, and push (part 8). This commit is the
   record that the design came before your AI saw any code. From now on, no test case is added,
   removed or rewritten.
4. **Turn each design into tests.** For each strategy, open a brand-new session in your checkout
   and run Prompt B.
5. **Run every suite, and commit before anything is fixed.** Use the run command in
   `spec-test-prompts.md`. If an error stops a suite from running at all, use Prompt C, at most
   twice per strategy. The first run in which every suite runs is the **baseline**. Commit the
   tests and `triage.md` with the baseline numbers, then push. Student 1 changes nothing until
   this commit is pushed.
6. **Sort every failure and every skip.** Apply the four conditions in `spec-test-prompts.md` to
   each failing test, and give each failing or `NOT_AUTOMATED` test a category in `triage.md`.
   Commit `triage.md` and push.
7. **Review the code with your model.** Make a clean copy of the branch's latest commit and run
   a review session exactly as in Step 7, items 2 to 4, with `ROUND=Q1`.
8. **Split the findings.** A finding in `modules/<module_code>/tests/spec/` or
   `docs/<NN>-<module_code>/spec-tests/` is yours: fix it as Step 9 allows. Send Student 1
   every other finding and every confirmed defect, each with its test id and the spec sentence
   it rests on.

## Step 9: Fix and check again until nothing is found

1. **Student 1 fixes.** Pull Student 2's commits. Paste the findings and the failing test ids
   into a builder session (the prompt's Step 10.5). The builder fixes the code, re-runs every
   gate, including Student 2's tests, and updates the quality report. Commit, then push (parts
   3 and 5).
2. **Student 2 checks again.** Pull. Re-run all four suites, labelled with the next round
   (`Q2`, `Q3` and so on). Update `triage.md`, fix anything of yours that a finding named, then
   commit and push. Then run a brand-new review session on the branch's latest commit, with the
   same `ROUND` label, and split its findings as in Step 8, item 8.
3. **Repeat until all four of these hold on the branch's latest commit:**
   - every spec test passes
   - no spec test is skipped
   - `triage.md` has no open row
   - Student 2's review returns `VERDICT: 10/10 in all nine dimensions`

   That last run is the final one. Student 1 then opens the pull request (Step 11).

The two of you run this loop on your own. These rules keep it honest:

- **Student 1 never edits `modules/<module_code>/tests/spec/` or
  `docs/<NN>-<module_code>/spec-tests/`. Student 2 never edits anything else.** The reviewer
  checks both against `git log`.
- **Student 2 changes how a test is written only where it is needed.** That means a row
  `triage.md` marks as a test-implementation or environment/setup problem, or a review finding
  on a spec test. Student 2 never changes an expected result to match the code. The one
  exception is when both of you agree the spec does not say what the test expects, recorded
  in `triage.md` with the spec sentence.
- **No spec test may stay skipped.** Each `NOT_AUTOMATED` test ends one of three ways:
  - Student 1 builds what is missing, and Student 2 automates the test.
  - The behaviour is already tested another way, for example by a Playwright spec. `triage.md`
    names that test, and Student 2 deletes the skipped one.
  - Both of you agree the spec does not require it. `triage.md` quotes the spec sentence, and
    Student 2 deletes the test.

  The frozen design keeps the case either way.
- **Settle disagreements between yourselves, from the spec.** A finding that rests on a rule
  from the spec or the prompts gets fixed, not argued. Where the spec itself is unclear, agree
  on a reading, record it in `triage.md` with the spec sentence, and list it in the pull request
  description.
- **If the same finding comes back three rounds in a row, stop patching.** Read the spec
  together, decide, and record the decision in `triage.md`.
- **Step 7's rules on every round apply here too:** every round counts, keep every reviewer's
  full output, never edit the review prompt, and never run tests while a review is running on
  the same machine.

## Step 10: Check it yourselves

The tool wrote the code, but you are the ones submitting it. Before the pull request:

- Student 1 runs `make check`, `make check-client` and `make e2e` on the final commit, and
  reads the output.
- Read the whole diff. Student 1 must be able to explain any file in the module, and Student 2
  any spec test, because you will be asked.
- Walk your module in the browser as each role and as the plain user.

## Step 11: Student 1 opens the pull request

- Each of you commits under your own GitHub identity. **No AI attribution anywhere:** not in code,
  comments, commit messages, docs or the pull request. Some tools add a co-author line or
  change the author name by default. Run these three checks:

  ```bash
  git log --format=%B upstream/main..HEAD | grep -i -E 'co-authored|generated (with|by)|aider|copilot|claude|gemini|chatgpt|deepseek|codex|opencode|openai|anthropic'
  git log --format='%an <%ae> | %cn <%ce>' upstream/main..HEAD | sort -u
  git diff --name-only upstream/main...HEAD | grep -i -E '(CLAUDE|GEMINI|AGENTS)\.md|\.cursorrules|\.aider|\.(cursor|claude|gemini|codex|opencode)/|opencode\.json|copilot-instructions'
  ```

  The first and third must print nothing. The second must show only the two of you.
- Student 1 opens the pull request when Step 9 ends, with parts 5 and 6 of "Your branch and
  your pull request".
- Open the pull request from `module/<module_code>` into the production branch, `main`, on
  `FusionIIIT/Fusion-Integrated`. In the description, give:
  - your spec folder
  - a link to the blueprint
  - a link to the quality report
  - a link to `docs/<NN>-<module_code>/spec-tests/triage.md`, and its results table: the
    baseline run and the last run for each strategy
  - every reading of an unclear spec rule that the two of you agreed in `triage.md`
  - the final scorecard, from Student 2's last review
  - any change outside your module's own folders, and who approved it

  Do not name the AI tools.

After you open it, the pull request is reviewed again with `module-review-prompt.md` before it
is merged. A pull request that does not score 10 in all nine dimensions comes back to you with
the findings.

## Step 12: Hand in your run record

The run record is one Markdown file for the pair. Hand it in with your pull request link. **Do not commit it,** because it names the AI tools.

```markdown
# Run record: <module_code>

Student 1, builds (roll number):
Student 2, spec tests and review (roll number):
Pull request:

## Tools
- Student 1 (builder and reviewer sessions): tool, exact model, plan (free / paid), cost
- Student 2 (spec tests and review): tool, exact model, plan (free / paid), cost
- Web search: off / on (if on, every URL it fetched)

## Review rounds
Student 1's rounds are 1, 2, 3…; Student 2's are Q1, Q2, Q3…
| Round | Spec | Arch | Code | Security | Tests | E2E | Frontend | Ops | Hygiene | Open findings |
|-------|------|------|------|----------|-------|-----|----------|-----|---------|---------------|

## Spec tests
| Strategy | Cases designed | Repair prompts (0-2) | Baseline passed / failed / skipped | Final passed / failed / skipped | Final line % / branch % | Confirmed defects |
|----------|----------------|----------------------|------------------------------------|---------------------------------|-------------------------|-------------------|

## Builder sessions (Student 1)
| # | Date | Prompt steps covered | Why it ended (done / context full / rate limit / crash) |
|---|------|----------------------|----------------------------------------------------------|

## Spec-test sessions (Student 2)
| # | Date | Prompt A, B, C or review | Strategy or round | Why it ended |
|---|------|--------------------------|-------------------|--------------|

## Things you did by hand
| Prompt step | What you changed or re-prompted | Why |
|-------------|---------------------------------|-----|

## Things the tool made up, and how you caught them
| What (file, function, package, endpoint, role, spec id) | Caught by | Round |
|----------------------------------------------------------|-----------|-------|

## What you learned (5 to 10 lines)
```

Attach, unedited:

- every reviewer's full output, round by round, from both students
- the `../spec-results/` folders from Student 2's runs: `junit.xml`, `coverage.xml` and
  `pytest.log` for each strategy, at least for the baseline run and the last run

## Self-check before you ask for review

- [ ] The module is your assigned one, built on a branch from the latest `main`, with
      nothing taken from a 6A pull request or another team
- [ ] The prompt went in unchanged, with your six blanks filled in everywhere they appear
- [ ] Student 2 approved the blueprint, in writing, before any application code was written
- [ ] Student 2's model is from a different provider than Student 1's
- [ ] Student 2's four design files were committed and pushed before Prompt B ran, and the
      baseline commit came before any fix
- [ ] On the final commit, every spec test passes, none is skipped, and `triage.md` has no
      open row
- [ ] `git log` shows that only Student 2 changed the spec tests and `spec-tests/`, and that
      Student 2 changed nothing else
- [ ] The final review was Student 2's, made in a fresh session on your latest commit, or on
      the commit before a registration-only rebase (Step 7), and says
      `VERDICT: 10/10 in all nine dimensions`
- [ ] Every approval (blueprint, gaps, shared-file changes, dependencies) is recorded in the
      quality report with a link or a dated quote
- [ ] You ran `make check` and `make check-client` yourself, and both are green
- [ ] The quality report is committed, its numbers came from runs after the last change, and
      it names no AI tool
- [ ] No auto-approve mode was used, and the tool made no commit or push itself
- [ ] The three attribution checks in Step 11 come out clean, and `git diff` shows no key,
      `.env` file, tool config file or real person's data
- [ ] You can explain every file in the diff
- [ ] Your run record is complete and handed in, not committed
