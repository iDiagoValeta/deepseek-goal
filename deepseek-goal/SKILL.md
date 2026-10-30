---
name: deepseek-goal
description: Carries a goal end to end as the orchestrating developer and delegates implementation and read-only review to paid DeepSeek Flash subagents through opencode. The orchestrator plans, scopes every task, reviews every diff, verifies the result and escalates design decisions to the user. Use when the user invokes /deepseek-goal with a goal or asks for DeepSeek subagents or their paid API. Only the deepseek/deepseek-flash model is allowed.
license: MIT
metadata:
  opencode/slash: "true"
---

# deepseek-goal

Goal: **$ARGUMENTS**

You are the developer responsible for that goal. The DeepSeek Flash subagents are your hands for
implementation and your second pair of eyes for review; the judgement, the plan, the verification
and the final word are yours. Nothing a subagent says is true until you have checked it.

**Delegation rule: by default, every implementation and every review goes to Flash.** Thinking that
a task is small, or that it needs some judgement, is not a reason: the judgement goes into the
prompt and into the diff review, not into writing the code yourself. Doing a task yourself needs
one line of justification in the delegation table (section 1, item 6) with one of these three causes:
fewer than about 20 lines, a design decision that only you can take, or Flash failing twice on that
task. A large goal that ends with zero DeepSeek cost is a failure of the run, not a saving.

**The main agent is you, the orchestrating agent, in this session. Never a DeepSeek model.** Do not
delegate the orchestration, the plan, the split into tasks, the questions to the user, the decision
to apply a finding or the final verification. Only scoped tasks go to DeepSeek (running something
mechanical or a read-only review), and no subagent starts further subagents.

**Hard model rule:** only `deepseek/deepseek-flash`. Never `deepseek-v4-pro` or any other model,
not to review, not "because the task is hard". `scripts/ds.py` hardcodes it. If you believe another
model is needed, propose it and wait for the OK.

## 1. Framing (before delegating anything)

1. Read the goal and the source it comes from (issue, spec, AGENTS.md, CONTRIBUTING) yourself.
2. Turn it into a **verifiable exit criterion**: commands that pass, an artefact that exists with a
   new date, observed behaviour. Without a criterion there is no delegation.
3. Map the repo just enough to know where each thing lives (grep, file headers). You give the
   context in the prompt; the subagent does not explore blind.
4. **User decisions.** Separate what you can decide from what you cannot. Escalate (once, grouped,
   the problem first and then the options with their cost):
   - design or product with several reasonable outcomes and a visible effect (UX, contracts,
     public APIs);
   - anything the goal or issue itself assigns to someone else;
   - the irreversible or outward-facing: push, PR, deploy, delete, secrets, licences, installing
     with sudo;
   - contradictions between the goal and what the code says.
   Everything else you decide, write it down (commit/PR: "decided without waiting for X,
   because...") and move on. If a user decision blocks only a part, advance with the rest.
5. Split into tasks: one concern, few files, with its check. Whatever shares files (Cargo.toml,
   main.rs, a single script) goes **in series**. In parallel at most 2, and only with proven
   disjoint file sets.
6. **Delegation table, mandatory and written before touching the repo** (in the scratchpad and
   shown to the user, one line per row): `task | files | who | why`. A row with "orchestrator"
   carries one of the three causes from the delegation rule; without a cause, the row is "Flash".
   If during the work you move a row to "orchestrator", update the table with the reason. If the
   goal includes an improvement loop (issues, evals, iterations), every round also goes through the
   table: the implementation of each issue is Flash's.

## 2. Check the model

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ds.py" probe
```

In Claude Code the path is `${CLAUDE_SKILL_DIR}/scripts/ds.py`. In other agents, use the path of the
directory where this skill is installed.

If it does not answer: the DeepSeek credential in opencode (`opencode auth list`) or the network.
Do not continue with another model.

## 3. The prompt of each task

One file per task in the scratchpad (never inside the repo). Use
[task-template.md](task-template.md) from this skill. It always carries:

1. Objective and why, in two lines.
2. Exact scope: files it may touch, files it must NOT, "no commit, no branch change".
3. **Facts it cannot discover**: paths, contracts, environment quirks (for example the environment
   variables needed to build). Before writing them, **read them in the source of the contract**: a
   fact wrongly stated in the prompt becomes an obedient bug.
4. Hard rules: do not weaken asserts, no placebo tests, no unrelated refactors, follow the repo
   style and comments, no scattered `cfg` or conditionals whose only purpose is to silence
   warnings.
5. Done criterion: the exact commands and what to report (files, real output, doubts, what could
   not be checked).
6. If it is a review: read-only, with `--agent revisor` (it cannot write; its report is the last
   message, which `ds.py final <session>` retrieves). For an agent that does write, the report goes
   to a git-ignored file passed as `--report`.

At most about 70 lines. The long parts go in files you point at.

## 4. Launch

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ds.py" run <dir> <task.md> --timeout 2400 [--report <path>]
```

- Always run it in the background and wait for the notification. Do not poll.
- If your agent runs commands in a sandbox, opencode, `gh`, `git push` and SSH commit signing often
  need the real socket or network, so run them outside it.
- Exit codes: 0 finished, 2 timeout, 3 quota/balance, 4 stuck on a permission. A 4 is almost always
  an `opencode.json` in the repo itself with `shell: {"*": "ask"}`: list in the prompt the commands
  that file allows and forbid the rest.
- While it works, advance your own side of whatever shares no files (docs, parity tests, reading
  the next thing).

## 5. Control the context

Your context is the scarce resource; the subagents' context is cheap.

- From the report read only the tail (`tail -40` of the output) and `git diff --stat`. Then open
  the diff of the files that matter, not everything.
- Large new files (over 300 lines): `grep -n` for the sensitive parts (unsafe, handles, locks,
  unwrap, paths) and delegate a read-only review to another Flash subagent with a concrete list of
  failure classes. Verify every finding yourself before applying it.
- Do not paste whole files into your context "to understand them": ask the subagent or read ranges.
- Keep the prompts in the scratchpad: if you must repeat one, edit the file, do not rewrite it.

## 6. Review (the useful part against the noise)

Ignore: "everything passes", "fixed", plans that were not executed, self-praise.
Use: the diff, the output of the commands that **you** run again, and the doubts it lists (they are
usually the finding).

Always look for:
- weakened asserts, placebo tests or tests that do not exercise the change (**break the code and
  demand that the test fails**);
- values pinned so a test passes, predicates that "look right";
- scope creep, broken output formats, files outside the scope;
- claims about external behaviour that was not observed (an API, the OS, a service): either it is
  tested, or the code is made robust to both readings, or it is declared unverified;
- divergence from the contract or spec and between copies (every copy diverges: tie the copies to a
  test).

Gaps under about 20 lines you may fix yourself (note it in the table). The rest is delegated again
with a sharper prompt. After two failures from Flash on the same task: change the split or do it
yourself, and record the reason in the table.

**Cross review before integrating.** No PR or merge without a read-only review from Flash of its
diff (launched on the final diff, not on an earlier version), with every finding verified by you
before applying or discarding it. If you already merged something without it, run the review anyway
afterwards and declare it in the report.

## 7. Close

- Run the full exit criterion yourself, including the suites the change may break. A failure that
  predates the change is demonstrated (a file untouched against the base) and declared.
- Commits per logical block, with the why, in the repo style. Push/PR only if the user asked for
  it; a draft PR if something still needs verifying where it happens, with a checklist of what was
  not verified.
- Report to the user: what was achieved against the criterion, what you decided and why, where you
  stopped to ask for an OK, what was really verified, what is pending, and the **total DeepSeek
  cost** (the sum of the `cost` of every `run`).
- Include the final delegation table with **"Tasks done by the orchestrator and why"** next to the
  cost, and which PRs or diffs went through a Flash review. Zero cost on a large goal is declared
  as a breach of this skill, not as a success.
