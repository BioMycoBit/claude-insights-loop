# Insights Ledger

One row per ask that an `/insights` report has raised, kept forever. The triage command
(`.claude/commands/insights-triage.md`) reads this table **before** it opens a new report, so most
of each later pass becomes a lookup instead of a re-argument.

`scripts/check_ledger.py` enforces the rules below, and the six columns in this order. Run it after
every edit.

**The example rows are real decisions from the nine passes in `docs/nine-passes.md`, with their
sources removed.** Delete them when you start your own ledger, and keep the shape.

## The rules

- **Key**: `insight:pass-N:<slug>`, where N is the pass that resolved the ask. It never changes,
  and keys are unique. Use whatever pass label you like (a date, a sprint name); keep the
  `insight:` prefix so one grep finds every row.
- **Ask**: the report's request in its own words, never your verdict. The next pass matches on the
  request, so a verdict written here makes the row unfindable.
- **Pass**: every run that raised the ask, oldest first. A later pass that raises it again appends
  here and never opens a second row. An ask raised five times is one finding and a report with no
  memory.
- **Verdict**: one of four. LANDED is built and running. OPEN is real, not built, and planned
  somewhere. DEFER is not now. NO-GO is decided against.
- **Revisit**: for LANDED, what shipped. For DEFER and NO-GO, the fact about the world that would
  reverse the decision: a fact a command can check, or an event someone would notice. Never a
  date: "next quarter" is a deferral with no door. Put the measurement behind a refusal here too,
  because a refusal that rests on preference gets re-proposed by the next pass and wins. The
  checker refuses DEFER or NO-GO without a Revisit cell.
- **Source**: the commit that recorded the decision. A path alone goes stale; a commit answers
  anywhere the history exists. The checker refuses LANDED without a Source cell.

Only a fired Revisit condition reopens a closed row. The same ask appearing again does not.

## Ledger

| Key | Ask | Pass | Verdict | Revisit | Source |
|---|---|---|---|---|---|
| `insight:pass-1:premise-audit` | Audit a plan's premises before implementing it, not after the diff exists. | pass-1 (2026-08-12); raised again on passes 3, 4, 5, 6 and 7 | LANDED | A premise check runs before any edit. It later moved to the plan's author, so each plan carries the commands that settle its own premises. Raised five more times after it shipped. | (your commit) |
| `insight:pass-1:bare-commit-refusal` | Never commit without naming the files, because parallel sessions share one git index. | pass-1 (2026-08-12); raised again on passes 4, 5 and 6 | LANDED | A hook refuses a bare `git commit` and names the alternative. Proven by firing it live in the session, not by reading the script. | (your commit) |
| `insight:pass-3:no-text-mode-round-trip` | Never rewrite a file through a text-mode round trip that silently strips CRLF line endings. | pass-3 (2026-08-18); raised again on passes 4, 6, 7 and 9 | OPEN | Reopened on pass 9, when its condition fired. Until then a flip was detected at staging but not prevented, and the condition read "a flip lands without the detector seeing it". On pass 9 an 11-line flip, under the detector's 50-line floor, landed unseen. The commit tool now refuses any line whose ending changed while its text did not. | (your commit) |
| `insight:pass-4:worktree-per-session` | Give each parallel session its own worktree instead of sharing one editing tree. | declined a month before; pass-4 (2026-08-20); raised again on passes 5 and 6 | LANDED | The earlier decline priced it at "five branches and five merges", which was a different setup's cost. Reversed by measured write pressure: daily same-file commits on the two busiest shared files rose from 2.6 and 1.7 to 7.1 and 5.9. | (your commit) |
| `insight:pass-4:escape-hatches-in-claude-md` | Document the hook escape hatches in CLAUDE.md, so a blocked tool call has a documented next move. | pass-4 (2026-08-20); raised again on passes 5, 7, 8 and 9 | NO-GO | Reverses if a guard trip is traced to a session that did not have the rules file loaded. Refused by measurement: the hatches were already in an auto-loaded rules file, and the guard tripped twice during that planning session with the note in context. Later: 57 refusals in 7,674 Bash calls, each naming its next move and each recovered in one call. | (your commit) |
| `insight:pass-7:parallel-research-agents` | Fan planning research out to parallel agents, each returning a cited table. | pass-7 (2026-09-12); raised again on pass 8 | NO-GO | Reverses if the standing one-agent cap is lifted. One grep for the cap line settles it, and it still reads 1. Every ask for a swarm of parallel agents has met the same cap. | (your commit) |
