# ReidCLI

Terminal-native personal intelligence and coding CLI with an agent-first runtime.

A real runtime — not a chat wrapper. Sessions, tasks, tools, policy gates, and
persistence are first-class. A genuine full-screen TUI (not an inline redraw
hack) with a locked-to-bottom footer, scrollable history, collapsible
reasoning/tool-call output, and a live "/" command menu. Built to grow into a
durable operator surface.

**Status:** Phase 5 complete (correctness fixes + real resume + interaction
upgrade), plus a full-screen TUI rewrite, web search, and workflows on top.
See `docs/` for the architecture audit and phase plans.

---

## Target stack

- **Python** 3.12+
- **Typer** — CLI command surface
- **Pydantic v2** — schemas and validation
- **Rich** — terminal rendering (markdown, tables, panels)
- **prompt_toolkit** — the full-screen TUI (layout, input, completion, mouse)

---

## Quick start

### 1. Create a venv and install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

> On macOS/Linux: `source .venv/bin/activate` instead of the PowerShell line.

### 2. Verify the install

```powershell
reidcli doctor
```

Expected output:

```
reidcli 0.1.0
python    <path> (3.13.x)
workspace <cwd>
storage   ~/.reidcli
provider  stub
mode      balanced
providers ['stub']
ok runtime importable; stub provider available
```

### 3. Run it

```powershell
reidcli
```

Drops you into the interactive TUI with a fresh session. Type `/` to see every
available command with descriptions, or just start talking. The stub provider
is offline and exercisable without API keys.

---

## The interactive TUI

`reidcli` (with no subcommand, or `reidcli interactive`) launches a real
full-screen `prompt_toolkit` application — the same style of terminal
ownership as `vim`/`htop` (alternate screen; your native scrollback is
untouched and restored exactly as it was on exit). Rich handles all the
actual rendering (markdown, tables, panels); prompt_toolkit owns the screen,
input, and layout around it.

- **Locked-to-bottom footer** — a spinner row, the input box, and a status
  line (app name · mode · model · effort · token/context-window usage ·
  workspace · task count) are always pinned to the terminal's actual last
  rows. The scrollable output pane fills everything above it.
- **Mouse-wheel scroll** — scroll up to read history without losing your
  place; new replies keep arriving below the fold instead of yanking you back
  down. Scroll back to the bottom (or far enough) and it re-locks
  automatically. (Hold **Shift** while click-dragging for native text
  selection/copy — mouse support for scrolling means the terminal hands mouse
  events to the app, and Shift is the standard bypass every terminal supports
  for that.)
- **Collapsible reasoning + tool calls (Ctrl+O)** — chain-of-thought shows as
  a grayed-out `✻ Thought for Ns` line and each tool call as a one-line
  `● tool(args) ok/error` summary, collapsed by default. `Ctrl+O` toggles
  every collapsed block open at once to see the full detail.
- **`/` completion menu** — type `/` for a live menu of every slash command
  with its description (Tab/↓/↑ to navigate, Enter to accept); no need to run
  `/help` first, though `/help` still works and shows the same list grouped
  by category.
- **Large/multi-line pastes collapse** to a placeholder like
  `[Pasted text #1 +42 lines]` (same idea as Claude Code's own input box) —
  the full text is still sent when you submit, only the box display is
  compact.
- **Keyboard shortcuts in the input box:**
  - `↑` / `↓` — input history
  - `←` / `→` — cycle reasoning effort (`low → medium → high → xhigh`) when
    the box is empty; otherwise they move the cursor normally
  - `Ctrl+O` — toggle collapsed/expanded reasoning + tool calls
  - `Ctrl+C` — clear the current line; `Ctrl+D` — exit
- **DeepReid trigger** — type `deepread`/`deep reid` (a few spellings
  accepted) at the very start of the box: it pulses green, and your message
  runs through the real Researcher→Planner→Critic pipeline instead of a
  normal turn. See "DeepReid" under Tools/What works now below.
- A small mascot renders next to the welcome banner on launch
  (`render.py::banner`/`_MASCOT`) — purely cosmetic, easy to swap out.

---

## Command surface

### Top-level CLI commands

| Command | Purpose |
|---|---|
| `reidcli` | Launch the interactive TUI (default — no subcommand needed) |
| `reidcli interactive "<prompt>"` | Launch interactive mode and immediately submit `<prompt>` as the first turn — session stays open afterward |
| `reidcli --file <path>` / `-f` | Same idea, but read the initial prompt from a text file — works with `interactive`, `exec`, and the bare/no-subcommand form |
| `<cmd> \| reidcli` | Pipe a prompt via stdin as the initial turn (only applies to the bare/no-subcommand form) |
| `reidcli exec "<prompt>"` | Run a single prompt non-interactively (headless) |
| `reidcli deepreid "<task>"` | Plan + review `<task>` via the Researcher/Planner/Critic pipeline (headless, like `exec`) — no code changes, saves a Markdown plan |
| `reidcli resume <session-id>` | Resume a prior session, then enter interactive mode |
| `reidcli sessions` | List all sessions |
| `reidcli config-show` | Show the effective (merged) configuration |
| `reidcli tools` | List registered tools with risk levels |
| `reidcli doctor` | Run environment diagnostics |
| `reidcli version` | Show version and runtime info |
| `reidcli --help` | Show the command surface |

### Slash commands (inside the TUI)

Type `/` in the input box for a live completion menu of all of these with
descriptions — the table below is the same information, grouped.

**Session**

| Command | Purpose |
|---|---|
| `/status` | Show current session, mode, model, task count, workspace |
| `/sessions` | List all sessions with freshness |
| `/resume <id>` | Resume a prior session (restores message history) |
| `/transcript [n]` | Show last n messages (default 20) |
| `/rewind` | Drop the last turn from state |

**Tasks**

| Command | Purpose |
|---|---|
| `/tasks [status]` | List tasks; filter by `pending` `active` `completed` `failed` `blocked` |

**Config & Policy**

| Command | Purpose |
|---|---|
| `/model <name>` | Set the model for the session |
| `/effort <level>` | Set reasoning effort: `low` `medium` `high` `xhigh` |
| `/mode <mode>` | Set permission mode: `strict` `balanced` `autonomous` `custom` |
| `/permissions` | Show current policy: mode, blocked/allowed commands, writable roots, timeouts |
| `/tools` | List registered tools with risk-level badges |

**Workflows**

| Command | Purpose |
|---|---|
| `/workflows` | List saved workflows |
| `/workflow save <name> [n]` | Save the last `n` user turns as a reusable workflow (default 5) |
| `/workflow show <name>` | Show a workflow's steps |
| `/workflow run <name>` | Run a workflow's steps in sequence — each step gets the same handling as typing it directly (slash commands and prompts both work, spinner/approval included) |
| `/workflow delete <name>` | Delete a workflow |

Workflows are global (not tied to a session or workspace) and persist to
`~/.reidcli/workflows.json`, so a workflow saved in one session is runnable
from any other.

**Meta**

| Command | Purpose |
|---|---|
| `/help` | Show grouped help |
| `/clear` | Clear the output pane |
| `/exit` | Quit ReidCLI (also `Ctrl+D`; `Ctrl+C` clears the current input line) |

---

## Configuration

Config is merged in this precedence order (low → high):

1. **Built-in defaults** — a stub provider, balanced mode
2. **Global config** — `~/.reidcli/config.json`
3. **Project config** — `./.reidcli/config.json`
4. **Environment variables** (highest)

### Environment variables

| Variable | Effect |
|---|---|
| `REIDCLI_PROVIDER` | Default provider name (e.g. `stub`) |
| `REIDCLI_WORKSPACE` | Workspace root path |
| `REIDCLI_STORAGE` | Storage root path (defaults to `~/.reidcli`) |
| `REIDCLI_PERMISSION_MODE` | Permission mode: `strict` `balanced` `autonomous` `custom` |
| `REIDCLI_LOG_LEVEL` | Log level: `INFO` `DEBUG` `WARNING` `ERROR` |

### Config file example

`~/.reidcli/config.json`:

```json
{
  "default_provider": "stub",
  "policy": {
    "default_mode": "balanced",
    "allowed_commands": ["git", "ls", "pwd"],
    "shell_timeout_seconds": 30
  }
}
```

View the effective merged config:

```powershell
reidcli config-show
```

---

## Permission modes

The policy engine gates every tool call. Pick a mode that matches your trust level.

| Mode | Behavior |
|---|---|
| `strict` | Approve nearly everything. File reads allowed; writes prompt; shell denied. |
| `balanced` | (Default) Low-risk allowed; medium and high risk prompt for approval. |
| `autonomous` | Low and medium allowed without prompts; high risk still prompts. |
| `custom` | Only explicit allowlists permit; everything else prompts. |

Path confinement is enforced in all modes — file tools cannot read or write outside
the workspace root (plus any configured `additional_writable_roots`). Shell commands
in the default denylist (`rm`, `rmdir`, `del`, `format`, `shutdown`, `reboot`, `mkfs`)
are always blocked.

Switch modes at runtime:

```
/mode strict
/mode autonomous
```

---

## Tools

The agent loop calls tools through the registry. Each tool is policy-gated.

| Tool | Risk | Purpose |
|---|---|---|
| `read_file` | low | Read a file's text content |
| `write_file` | medium | Create or overwrite a file |
| `patch_file` | medium | Replace one exact substring occurrence (unique match required) |
| `list_dir` | low | List entries in a directory |
| `find_files` | low | Find files matching a glob pattern |
| `grep_files` | low | Search file contents with a regex |
| `run_command` | high | Run a shell command with policy approval and timeout |
| `web_search` | high | Search the web (DuckDuckGo, free, no API key) — see below |

All file tools confine access to the workspace root. Traversal outside is denied.

### `web_search`

Free, no API key, stdlib-only (`urllib` + `re`). Two DuckDuckGo sources, tried
in order:

1. The official Instant Answer JSON API — fast (~0.3s), but only populated
   for factual/entity queries ("what is X").
2. The HTML-only search endpoint — slower and more exposed to DuckDuckGo's
   anti-bot rate limiting, but covers general search queries the fast path
   doesn't.

Results are cached in-memory per session (5 minute TTL) so repeated queries
don't re-hit the network. Sponsored/ad results are filtered out rather than
surfaced as raw tracking links. Gated as `ActionKind.NETWORK` (HIGH risk by
default) through the same policy engine as every other tool — expect an
approval prompt in `balanced`/`strict` mode.

---

## Sessions and persistence

Each session gets a structured directory under `~/.reidcli/sessions/<id>/`:

```
~/.reidcli/sessions/<session-id>/
  meta.json         # Session record (id, workspace, model, mode, status, timestamps)
  transcript.jsonl  # One Message per line (restorable into state on resume)
  tasks.json        # Task state for the session
  events.jsonl      # Runtime action log (turn summaries, lifecycle events)
```

Workflows live one level up, outside any single session:

```
~/.reidcli/workflows.json   # {"workflows": [{name, description, steps, created_at}, ...]}
```

**Resume is real:** `reidcli resume <id>` reloads the transcript into the agent's
message history so the conversation continues with full context (capped at the 100
most recent messages).

List sessions:

```powershell
reidcli sessions
```

---

## Headless / exec mode

Run a single prompt without entering the TUI:

```powershell
reidcli exec "list the current dir"
reidcli exec "read README.md"
reidcli exec --file prompt.txt
```

Output goes to stdout; tool-call count goes to stderr. Exit code is `0` on success,
`1` if no text was produced. The approver auto-allows in exec mode — set
`REIDCLI_PERMISSION_MODE=autonomous` for unattended runs, or `strict` to deny all
risky actions silently.

---

## Development

### Run the test suite

```powershell
pytest
```

24 focused tests across policy, tools, session, reasoning, and the agent loop.

### Lint

```powershell
ruff check src
ruff check --fix src   # auto-fix
```

### Project structure

```
ReidCLI/
  pyproject.toml
  src/reidcli/
    app/         # Typer CLI commands, dependency wiring
    config/      # Pydantic config models + loader (global/project/env merge)
    diagnostics/ # logger + JSONL event log
    session/     # Session model + structured per-session store
    tasks/       # Task model + store (state machine)
    policy/      # PermissionMode, decisions, risk, PolicyEngine
    provider/    # BaseProvider + StubProvider + registry
    tools/       # ToolDefinition/Result, registry, file/shell/web-search tools
    workflows/   # Workflow model + global WorkflowStore (~/.reidcli/workflows.json)
    runtime/     # RuntimeState, agent loop, orchestrator (composition root)
    integrations/# MCP foundation (config-driven, stubbed lifecycle)
    automation/  # exec mode (headless)
    ui/          # theme, render (Rich), app (full-screen prompt_toolkit TUI),
                 # commands (slash-command routing + completion source), repl (entry point)
  tests/         # policy, tools, session, reasoning, agent loop
  docs/          # architecture audit, phase plans
```

### Architecture intent

See the parent repo's design docs:

- `reidcli-build-plan.md` — full product definition and phase plan
- `agent-first-cli-spec.md` — generic agent-first CLI specification
- `docs/reidcli-architecture-audit.md` — file-aware critique of this scaffold
- `docs/reidcli-phase-5-plan.md` — correctness fixes + interaction upgrade
- `../deepreid-spec.md` — spec for DeepReid, the planning/review multi-agent
  subsystem, now implemented (see below)

---

## What works now

- Full-screen TUI (prompt_toolkit): locked-to-bottom footer, mouse-wheel
  scrollable history, collapsible reasoning/tool-call output (`Ctrl+O`), live
  `/` completion menu
- Real agent loop with tool calls (StubProvider, no API keys needed)
- Session create / list / resume with message history restoration
- Task tracking with status state machine (pending → active → completed/failed)
- Policy engine with 4 modes, path confinement, command allowlist/denylist
- 8 tools (file read/write/patch/list/find/grep + shell + free web search) all policy-gated
- Workflows: save/list/show/run/delete reusable multi-step command sequences
- **DeepReid** (`src/reidcli/deepreid/`): a real Researcher→Planner→Critic
  subagent pipeline — each role is an independent `Agent`/`PolicyEngine`
  (Planner/Critic get zero tools; Researcher gets read-only file tools +
  `web_search` only), sequential, with a Critic-driven revision loop capped
  at 2 rounds. Never writes files or runs commands — output is a Markdown
  plan+critique, saved to `~/.reidcli/deepreid/<run-id>.md`. Two entry
  points: `reidcli deepreid "<task>"` (headless CLI, like `exec`) and typing
  `deepread`/`deep reid` at the start of the TUI's input box (border pulses
  green while active, real-time progress shown per stage).
- Prompt injection at launch: literal argument, `--file`, or piped stdin
- Headless exec mode
- Structured persistence (meta / transcript / tasks / events per session; global workflows and DeepReid runs)
- 28 passing tests, ruff clean

## What is stubbed (extension-ready)

- **Real providers** — OpenAI/Anthropic clients plug into `ProviderRegistry`
- **MCP** — config schema + lifecycle slots; stdio/JSON-RPC is TODO
- **Patch tool** — single exact-match replace; structured edits + diff preview TODO
- **Automation** — one-shot exec; scheduling/background TODO
- **DeepReid Builder role** — a subagent that actually implements an
  approved plan is explicitly out of scope for v1 (per `../deepreid-spec.md`);
  building is still the regular single-agent loop, or a human, for now.

---

## License

MIT
