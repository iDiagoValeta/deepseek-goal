# deepseek-goal

[![CI](https://github.com/iDiagoValeta/deepseek-goal/actions/workflows/ci.yml/badge.svg)](https://github.com/iDiagoValeta/deepseek-goal/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An agent skill for AI coding agents that carries a goal end to end while the orchestrating agent keeps the judgement and delegates the work to paid DeepSeek Flash subagents through opencode. It works in Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Windsurf, ZCode and any agent that reads the open [SKILL.md format](https://agentskills.io). It is for anyone who wants an agent to implement, review and verify a real goal in a repo with a second model doing the hands-on work, while the orchestrating agent plans, scopes, reviews every diff and reports the cost.

## What it does

- **Frames the goal first.** The orchestrating agent reads the source of the goal, turns it into a verifiable exit criterion (commands that pass, an artefact, observed behaviour), maps the repo and writes a delegation table (`task | files | who | why`) before touching anything.
- **Delegates by default.** Every implementation and every review goes to `deepseek/deepseek-flash`; doing a task in the orchestrator needs one of three written causes (fewer than about 20 lines, a design decision only it can take, or Flash failing twice on that task).
- **Writes one prompt per task.** Scope, files it may not touch, facts it cannot discover, hard rules and the done criterion, from `task-template.md`, capped at about 70 lines.
- **Runs the subagent in the background.** `ds.py` opens an opencode session pinned to `deepseek/deepseek-flash`, waits for it to settle, reports the outcome and the cost, and tells timeout, quota and permission stalls apart by exit code.
- **Reviews what came back.** The orchestrator reads the diff, reruns the commands itself and breaks the code to check that the tests fail. A read-only `revisor` agent does the cross review of the final diff before any merge.
- **Closes with the numbers.** The report compares the result with the exit criterion, lists what the orchestrator decided and where it stopped to ask, and gives the total DeepSeek cost.

It never runs another model. `deepseek/deepseek-flash` is hardcoded in `scripts/ds.py`, and a subagent cannot start further subagents.

## What it sends and where

- `ds.py` makes no network calls itself. It runs `opencode api` against the local opencode server, or the one in `OC_SERVER`.
- opencode sends each task file, and every file or command output the subagent reads or runs, to DeepSeek's API as `deepseek/deepseek-flash`, billed to your DeepSeek key. DeepSeek's own terms govern that data.
- What a subagent reads is not confined to the target directory: implementation tasks run opencode's default agent with its normal permissions, and the `revisor` agent limits the shell but not file reads.
- Nothing else leaves the machine through this skill: no telemetry, no other endpoints. The skill stores nothing; opencode keeps the session history on the machine that runs the opencode server, which is another host if you set `OC_SERVER`.
- Do not run it on a repo whose contents you may not send to DeepSeek.

## Requirements

- An agent that supports Agent Skills and can run shell commands in the background, such as any of the agents listed below.
- [opencode](https://opencode.ai) with the `opencode api` command, tested on 2.2.3. `ds.py` talks to the local opencode server; `OC_SERVER=http://host:port` points it at another one, and a server with a password needs `OPENCODE_PASSWORD` in the environment.
- A DeepSeek provider authenticated in opencode (`opencode auth login`) with `deepseek/deepseek-flash` available. This is your paid DeepSeek API: every `run` costs money, and the skill reports the cost per task and in total.
- The `revisor` opencode agent for read-only reviews, installed as described in [Set up the subagents](#set-up-the-subagents).
- Python 3, standard library only, for `ds.py`. CI tests on Python 3.12.
- `git`, to read the status and the diff of the target repo.
- `bash` for `install.sh`, and Node.js 22.20 or later with `npx` for the skills CLI, or the GitHub CLI with the skill command in preview for `gh skill`.

## Quick start

Install with the skills CLI, naming your agent:

```bash
npx skills add iDiagoValeta/deepseek-goal -a <agent>
```

Or with the GitHub CLI, which needs a recent `gh` with the skill command in preview:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent <agent> --scope user
```

`gh skill` supports every listed agent except Windsurf and ZCode, which use the skills CLI or `install.sh`.

`<agent>` is one of `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot`, `opencode`, `windsurf` or `zcode`. Then set up the subagents as described below and invoke the skill with a goal.

See [Install](#install) for the install options for each agent, the manual symlink and how to invoke the skill.

## Install

Every agent reads the same `deepseek-goal/` folder and the same `SKILL.md`; only the skills directory and the install command change. The table summarises the paths; the sections below give the commands for each agent, alphabetically.

| Agent | `--agent` value | User dir | Project dir | How to invoke |
|---|---|---|---|---|
| Claude Code | `claude-code` | `~/.claude/skills` | `.claude/skills` | `/deepseek-goal`, or `/deepseek-goal:deepseek-goal` as a plugin |
| Codex | `codex` | `~/.agents/skills` | `.agents/skills` | `$deepseek-goal`, or `/skills` to pick it |
| Cursor | `cursor` | `~/.cursor/skills` | `.cursor/skills` or `.agents/skills` | type `/` in the Agent chat and pick `deepseek-goal` |
| Gemini CLI | `gemini-cli` | `~/.gemini/skills` | `.gemini/skills` or `.agents/skills` | activated from the description; `/skills list` shows it |
| GitHub Copilot | `github-copilot` | `~/.copilot/skills` | `.github/skills`, `.claude/skills` or `.agents/skills` | loaded automatically when relevant |
| OpenCode | `opencode` | `~/.config/opencode/skills` | `.opencode/skills`, `.claude/skills` or `.agents/skills` | `/deepseek-goal` |
| Windsurf | `windsurf` | `~/.codeium/windsurf/skills` | `.windsurf/skills` or `.agents/skills` | `/deepseek-goal` |
| ZCode | `zcode` | `~/.zcode/skills` | `.zcode/skills` | ask in natural language |

Codex installs into the shared `~/.agents/skills`, which Cursor, Gemini CLI, GitHub Copilot, OpenCode and Windsurf also read. `pnpm dlx skills add` does the same as `npx skills add`; without `-g` the skills CLI installs into the project, and `-g` selects the user scope.

### Claude Code

Native plugin, one step on Claude Code 2.1.275 or later:

```text
/plugin install deepseek-goal --marketplace iDiagoValeta/deepseek-goal
```

Two steps on any version with plugins:

```bash
claude plugin marketplace add iDiagoValeta/deepseek-goal
claude plugin install deepseek-goal@deepseek-goal
```

The marketplace is the repo itself, so there is nothing else to host. To remove the plugin and its marketplace entry:

```bash
claude plugin marketplace remove deepseek-goal
```

It also uninstalls the plugins it provided and deletes their saved options and data.

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a claude-code
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent claude-code --scope user
```

Manual:

```bash
./install.sh claude-code
```

It creates the symlink `~/.claude/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.claude/skills/`.

Invoke it as `/deepseek-goal`, or as `/deepseek-goal:deepseek-goal` when installed as a plugin.

### Codex

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a codex
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent codex --scope user
```

Manual:

```bash
./install.sh codex
```

Codex reads the shared `~/.agents/skills`, so the link lives there. For one project, copy `deepseek-goal/` into `.agents/skills/`.

Invoke it as `$deepseek-goal`, or run `/skills` and pick it from the list.

### Cursor

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a cursor
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent cursor --scope user
```

Manual:

```bash
./install.sh cursor
```

It creates the symlink `~/.cursor/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.cursor/skills/` or `.agents/skills/`.

Invoke it by typing `/` in the Agent chat and picking `deepseek-goal`.

### Gemini CLI

Native installer:

```bash
gemini skills install https://github.com/iDiagoValeta/deepseek-goal.git --consent
```

Add `--scope workspace` for the project. It finds the skill in the repo subfolder on its own.

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a gemini-cli
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent gemini-cli --scope user
```

Manual:

```bash
./install.sh gemini-cli
```

It creates the symlink `~/.gemini/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.gemini/skills/` or `.agents/skills/`.

Gemini CLI activates it from the description when the request matches; `/skills list` shows it.

### GitHub Copilot

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a github-copilot
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent github-copilot --scope user
```

Manual:

```bash
./install.sh github-copilot
```

It creates the symlink `~/.copilot/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.github/skills/`, `.claude/skills/` or `.agents/skills/`.

GitHub Copilot loads it automatically when relevant.

### OpenCode

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a opencode
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/deepseek-goal deepseek-goal --agent opencode --scope user
```

Manual:

```bash
./install.sh opencode
```

It creates the symlink `~/.config/opencode/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.opencode/skills/`, `.claude/skills/` or `.agents/skills/`.

OpenCode also reads `~/.claude/skills/` and `~/.agents/skills/`. Invoke it as `/deepseek-goal`.

### Windsurf

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a windsurf
```

`gh skill` does not support Windsurf; use the skills CLI or the manual install.

Manual:

```bash
./install.sh windsurf
```

It creates the symlink `~/.codeium/windsurf/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.windsurf/skills/` or `.agents/skills/`.

Invoke it as `/deepseek-goal`.

### ZCode

Skills CLI:

```bash
npx skills add iDiagoValeta/deepseek-goal -a zcode
```

`gh skill` does not support ZCode; use the skills CLI or the manual install.

Manual:

```bash
./install.sh zcode
```

It creates the symlink `~/.zcode/skills/deepseek-goal`. For one project, copy `deepseek-goal/` into `.zcode/skills/`.

Ask ZCode in natural language, for example "run this goal with DeepSeek Flash".

### Any other agent

Any agent that reads the open SKILL.md format works the same way: copy the `deepseek-goal/` folder into the skills directory your agent documents.

```bash
git clone https://github.com/iDiagoValeta/deepseek-goal.git
cp -r deepseek-goal/deepseek-goal <agent-skills-dir>/
```

### install.sh

From a clone of this repo:

```bash
git clone https://github.com/iDiagoValeta/deepseek-goal.git
cd deepseek-goal
./install.sh AGENT...
./install.sh --uninstall AGENT...
./install.sh --list
```

`AGENT` is one of `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot`, `opencode`, `windsurf` or `zcode`. It creates a symlink to `deepseek-goal/` in this repo at the user directory of the agent; `codex` targets the shared `~/.agents/skills`. `--list` prints every agent with the path it uses.

It is idempotent: if the link already exists and points here, it does nothing; if something else exists at that path, it aborts without deleting it. Several agents in one call are all processed, and the exit status is 1 if any failed. No arguments or an unknown agent print the usage on stderr and exit 2.

Uninstall removes the symlink only if it points to this repo. If it points elsewhere, or the path holds a real directory or file, it aborts without touching it:

```bash
./install.sh --uninstall claude-code
```

## Set up the subagents

The skill only orchestrates. The subagents are opencode sessions running `deepseek/deepseek-flash`, so the next three steps happen once per machine, before the first goal.

`<skill-dir>` is the folder where the skill was installed, for example `~/.claude/skills/deepseek-goal` or `~/.agents/skills/deepseek-goal`, or `deepseek-goal/` in a clone of this repo.

1. **Authenticate DeepSeek in opencode.**

   ```bash
   opencode auth login
   ```

   Pick DeepSeek and paste the API key. The provider is the user's: the runs are billed to that account.

2. **Install the read-only reviewer.** `ds.py run ... --agent revisor` needs the agent file in the opencode agents directory, for the user or for one project:

   ```bash
   mkdir -p ~/.config/opencode/agents
   cp <skill-dir>/assets/opencode-agents/revisor.md ~/.config/opencode/agents/revisor.md
   ```

   For a single project, copy it to `.opencode/agents/revisor.md` inside that project. The file pins `deepseek/deepseek-flash` and denies edits, network access and every shell command except those starting with `git diff`, `git log`, `git show` and `git status`.

3. **Check the model with one short call.** It costs a fraction of a cent and says whether the credential, the network and the model are in place:

   ```bash
   python3 <skill-dir>/scripts/ds.py probe
   ```

   It prints a line such as `deepseek/deepseek-flash: ok (12s)`, or `quota`, or an error. Inside Claude Code the skill calls the script as `${CLAUDE_SKILL_DIR}/scripts/ds.py`; in any other agent, use the directory where the skill is installed.

## Usage

Invoke the skill the way your agent does, as the table above says, or ask in natural language: "run this goal with DeepSeek Flash", "take this issue from open to merged with Flash subagents".

The flow is always the same: frame the goal into a verifiable exit criterion, write the delegation table, write one prompt file per task outside the repo, launch Flash, review the diff and rerun the checks yourself, delegate the cross review, and close with the cost.

`ds.py` has four commands:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ds.py" probe
python3 "${CLAUDE_SKILL_DIR}/scripts/ds.py" run <dir> <task.md> [--timeout 2400] [--report <path>] [--agent <id>]
python3 "${CLAUDE_SKILL_DIR}/scripts/ds.py" status <session-id>
python3 "${CLAUDE_SKILL_DIR}/scripts/ds.py" final <session-id>
```

In Claude Code those paths work as written; in any other agent, replace `${CLAUDE_SKILL_DIR}` with the directory where the skill is installed.

- `probe` makes one short call and reports ok, quota or error.
- `run` creates the session with the model pinned, sends the task file, waits for the session to settle and prints the session id, the outcome, the seconds, the cost, the last text, the report file if it exists and `git status --short`. It gives up after about `--timeout` seconds (2400 by default; checks run every 15 seconds). `--report` names the git-ignored file where the task told the subagent to write its report, useful when the last message arrives empty. `--agent` selects an opencode agent such as `revisor`; the model stays Flash.
- `status` prints the outcome, the cost, whether the session has settled, the number of subsessions, the last error and any pending permission or form.
- `final` prints the last text of the subagent.

Exit codes of `run`:

| Code | Meaning |
|---|---|
| 0 | The session settled |
| 2 | Timeout |
| 3 | Quota or balance exhausted |
| 4 | Stuck on a permission or a form |

A 4 is almost always an `opencode.json` in the repo with `shell: {"*": "ask"}`: list in the prompt the commands that file allows and forbid the rest.

## Structure

```text
.
├── .claude-plugin/                 Claude Code plugin and marketplace manifests
├── deepseek-goal/
│   ├── SKILL.md                    Entry point: framing, delegation, review and close
│   ├── task-template.md            Prompt template for one subagent task
│   ├── scripts/
│   │   └── ds.py                   Launches and inspects opencode subagent sessions
│   └── assets/
│       └── opencode-agents/
│           └── revisor.md          Read-only opencode review agent
├── tests/
│   ├── test_ds.py                  Model pin, settled(), as_list() and usage text
│   ├── test_install.py             Installer and safe uninstall
│   └── test_skill_format.py        Frontmatter, size, links and forbidden characters
├── .github/workflows/ci.yml        Python 3.12 tests and install.sh syntax
├── install.sh                      Symlink installer for every agent and safe uninstaller
├── LICENSE
└── README.md
```

## Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
```

The tests need no network and no DeepSeek credit. They check the model pin, the `settled()` and `as_list()` helpers and the usage text of `ds.py`, the installer and uninstaller in temporary directories, and the format of `SKILL.md` (frontmatter, size, links, and forbidden characters). `bash -n install.sh` checks the installer syntax. CI runs both on Python 3.12.

## License

MIT. See [LICENSE](LICENSE).
