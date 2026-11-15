# Spec tests: the Assignment 8 prompts, for Assignment 9

In Assignment 9, Student 2 uses these prompts in Step 8 of
[`online-ai-assignment-guide.md`](online-ai-assignment-guide.md), after Student 1's module has
reached 10/10. They are Assignment 8's Prompts A, B and C. The text inside each prompt is
unchanged, except that Prompt A says "the adequacy rule below" where Assignment 8 said "in
Section 7", and except for the lines marked **Fusion-Integrated**. Those lines add this
repository's file locations and four rules Assignment 8 did not need:

- every `source_id` starts with the spec's own id (Prompt A)
- how to check a refusal when the spec names no HTTP status (Prompt B)
- the tests must pass `ruff` (Prompt B)
- the AI never commits or pushes (Prompt B)

The tests are written in two stages. First an AI that sees **only the spec** decides what to
test and what the right answer is. Then a second session, which can see the code, turns that
frozen design into pytest tests. The builder's own tests were written by the AI that wrote the
code, so they share its reading of the spec. These do not.

## The four strategies

Run each strategy on its own, in its own fresh session, in this order: FR, UC, BR, WF.

| Strategy | Give the session only | Instruction to append to Prompt A |
|---|---|---|
| FR | Problem Statement + CFR/AFR | Cover every testable CFR/AFR with at least one test. Add a separate negative/boundary/validation/authorization case only where the requirement explicitly defines such a condition or outcome. |
| UC | Problem Statement + Use Cases | Cover the main success flow of every Use Case and every explicitly specified alternative/exception flow with at least one test. Do not invent additional flows. |
| BR | Problem Statement + Business Rules | Cover every Business Rule with at least one test. Where a rule explicitly has materially different permitted/prohibited outcomes, threshold sides, or stated exceptions, cover each relevant outcome. |
| WF | Problem Statement + Workflows | Cover every explicitly specified distinct workflow path/decision outcome. Ensure every important stated transition is exercised at least once; do not enumerate unsupported combinations. |

Test obligation = one explicitly specified behavior/flow/rule/path that the corresponding rule
above requires to be tested. A single test may cover more than one closely related obligation,
but unrelated obligations should not be merged merely to reduce the number of tests.

## Prompt A: design the tests from the spec

**Fusion-Integrated:** copy the Problem Statement and this strategy's documents into an empty
folder outside the repository, for example `../spec-br/`, and open a brand-new session there.
Give it nothing else: no repository, no code, no tests. Save its output unchanged as
`docs/<NN>-<module_code>/spec-tests/<STRATEGY>_DESIGN.json`, for example `BR_DESIGN.json`.

Replace only `<MODULE NAME>` and `<STRATEGY SPECIFICATION>`, then append the strategy's
instruction from the table above.

```text
You are designing automated specification-based tests for the <MODULE NAME> Fusion ERP module.
Source of truth: Use ONLY the supplied Problem Statement and <STRATEGY SPECIFICATION>.
Do NOT inspect implementation code.
Do NOT infer behavior from implementation.
Do NOT introduce behavior unsupported by the supplied specification.
Generate the minimum non-redundant set of test cases needed to satisfy the strategy-specific
adequacy rule below. Do not stop at an arbitrary number, do not omit an explicit test
obligation to reduce the test count, and do not invent unsupported behavior. Prefer observable
behavior that can subsequently be automated using pytest/pytest-django.
For every test case output exactly these fields:
- test_id
- source_id
- purpose
- preconditions
- action_or_input
- expected_result
- test_type
source_id must identify the exact obligation covered (for example: AFR-03, UC-05 Main Flow,
UC-05 Alternative A1, BR-07 condition-false, WF-02 approval-rejected path).
Output ONLY a valid JSON array. Do not provide explanation or additional prose.

Fusion-Integrated: every source_id starts with the specification's own id, written exactly as
the specification writes it (for example PC-BR-007), followed by the part covered.
```

**Freeze the design.** Check that every obligation the strategy's rule requires is in the file,
and that every `source_id` starts with an id exactly as the spec writes it. If a file fails
either check, delete it and run Prompt A again in a new session. Then commit the four design
files, and nothing else, and push, before you start Prompt B. That commit is the record that
the design came before your AI saw the code. After it, never add, remove or rewrite a test
case.

## Prompt B: turn the frozen design into tests

**Fusion-Integrated:** open a brand-new session in your checkout of the module's branch. Give it
that checkout and the one frozen design file. Run it once per strategy. Fill in `<STRATEGY>`
with `FR`, `UC`, `BR` or `WF`, `<strategy>` with the same in lower case (`fr`, `uc`, `br` or
`wf`, which is also the folder name), and `<module_code>` with your module code.

```text
You are given:
1. the frozen A8_BASE Fusion implementation, and
2. the frozen <STRATEGY>_DESIGN.json.
Convert these test designs into executable automated backend tests using pytest/pytest-django.
Rules:
- Implement exactly the supplied test cases.
- Do not add, remove, merge or reinterpret test cases.
- Preserve each specified expected result.
- Do not modify production code.
- Use the Django isolated test database.
- Reuse existing Fusion test infrastructure where appropriate.
- Do not mock the behavior being tested; mocks may be used only for unavailable external
  dependencies.
- Do not use xfail to hide failures.
- Every test must contain its test_id and source_id in its name or docstring.
- Store generated tests only under tests/a8/<strategy>/.
If a test genuinely cannot be automated using the available interfaces, create it as a skipped
pytest test with: NOT_AUTOMATED: <reason>. Do not replace it with a different test.

Fusion-Integrated:
- "A8_BASE" is this checkout, and "tests/a8/<strategy>/" is
  modules/<module_code>/tests/spec/<strategy>/, with an empty __init__.py in tests/spec/ and in
  each strategy folder. Name every file test_*.py.
- Where an expected result is a refusal and the specification names no HTTP status or error
  code, assert that the action was refused and changed nothing, and take the status from
  docs/01-architecture/api-conventions.md, "Status codes". This is how the expected result is
  checked; it is not a change to it.
- .venv/bin/ruff check modules/<module_code>/tests/spec must print nothing.
- Do not run git commit or git push.
```

## Prompt C: repair, and only repair

Use this only when an error stops the tests from running at all: a syntax error, an import, a
fixture or setup. A `ruff` error that `ruff check --fix` cannot fix counts as well. At most two
repair prompts per strategy, and only before the baseline: the first run in which every suite
runs (Step 8 of the guide).

```text
The generated test suite cannot execute because of the following test-code/setup error:
<PASTE EXACT ERROR>
Repair the TEST CODE/TEST SETUP only.
Do not modify production code.
Do not alter test intent or expected results.
Do not add or remove test cases.
Do not introduce new specification information.
Make only the minimum changes required to make the frozen tests executable.
Maximum: two repair prompts per strategy.
```

## Run each suite

Run each strategy on its own, from the root of your checkout. Results go **outside** the
repository, into `../spec-results/<label>/`. The label is `baseline` for the baseline, which
goes with review round `Q1`, and after that the label of the review round it goes with (`Q2`,
`Q3` and so on). The last run is the final one. You hand the results in with the run record;
never commit them.

```bash
label=baseline   # then Q2, Q3, ...
s=br             # then fr, uc, wf
out=../spec-results/$label/$s
mkdir -p $out
.venv/bin/pytest modules/<module_code>/tests/spec/$s \
  --junitxml=$out/junit.xml \
  --cov=modules/<module_code> --cov-branch \
  --cov-report=xml:$out/coverage.xml \
  --cov-report=term-missing \
  > $out/pytest.log 2>&1
tail -3 $out/pytest.log
```

## When a failing test is a defect

A failing test is a candidate defect, not a defect. All four of these must hold before you
call it an implementation defect:

1. The expected behavior is directly supported by the cited specification.
2. The test itself is correctly implemented and set up.
3. The failure is reproducible.
4. The observed implementation behavior contradicts the expected behavior.

If the same underlying problem is exposed by several tests or several strategies, record it
once and mark every strategy that exposed it.

Every failing or skipped test gets one of these categories:

| Category | What happens next |
|---|---|
| Confirmed implementation defect | Student 1 fixes the code |
| Test-generation / test-implementation problem | Student 2 fixes the test's code, never its expected result |
| Environment / setup problem | Student 2 fixes the setup |
| Specification ambiguity | both students agree on a reading and record it, with the spec sentence |
| Unresolved | both students look again until it fits one of the categories above |

## The triage log

`docs/<NN>-<module_code>/spec-tests/triage.md` is committed with the tests, and Student 2 keeps it
current. It names no AI tool.

```markdown
# Spec tests: <module_code>

Student 1 (git author name):
Student 2 (git author name):
Design commit (hash and subject):
Baseline commit (hash and subject):
Student 1's 10/10 commit the baseline ran on (hash):

## Results
| Run | Strategy | Cases | Passed | Failed | Skipped | Line % | Branch % |
|-----|----------|-------|--------|--------|---------|--------|----------|

## Failures and skips
| Test id | Source id | Strategies | Category | Evidence | Outcome (fixing commit, covering test, or agreed reading with the spec sentence) | Open? |
|---------|-----------|------------|----------|----------|-----------------------------------------------------------------------------------|-------|
```

A rebase gives every commit a new hash. After one, update every hash in this file.
