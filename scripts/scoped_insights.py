#!/usr/bin/env python3
"""Run Claude Code's official /insights report over ONE repository's sessions.

A reference copy for an agent fitting it to another setup: Linux-tested, standard library, Python 3.11+.
Needed only when Claude Code runs in more than one repository here, since a plain /insights reads them all.

The trick: hard link this repo's session folders into a private config folder, point CLAUDE_CONFIG_DIR at it,
and run `claude -p /insights` there. Four details are the method, not this repo's choices:
1. is_kept_folder: a project folder is named after its working directory, every character that is not a
   letter or digit replaced by '-'. List ~/.claude/projects first; add worktrees or subfolders you work from.
2. Hard links, never symlinks: /insights silently skips a symlinked folder. Links cannot cross filesystems.
3. seed_cache: /insights analyses in detail only sessions with no cached summary. Copy the cached ones, then
   clear the newest unanalysed ones, up to Claude Code's own 50 per run. Each run analyses up to 50 sessions.
4. SCOPED_SETTINGS: without it, Claude Code's startup cleanup unlinks aged transcripts from the scope.

The token `claude setup-token` prints comes through the environment, never as an argument:
    read -rs CLAUDE_CODE_OAUTH_TOKEN && export CLAUDE_CODE_OAUTH_TOKEN
    python3 scripts/scoped_insights.py [--out DIR]
A report quotes your session text, so --out (default <repo>/insights/) must be ignored by git, and the script
refuses before running anything if it is not. After the run, any analysed session whose recorded folder is
outside this repo refuses the report: that is the proof the scope held. Exit 0 written, 1 refused, 2 misuse.
"""
import argparse
import errno
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RUN_TIMEOUT_S = 3600
SCOPED_SETTINGS = {'cleanupPeriodDays': 36500}
ANALYSES_PER_RUN = 50
SUBTITLE_RE = re.compile(r'across ([\d,]+) sessions(?: \(([\d,]+) total\))?')


class Refusal(Exception):
    """The run stops here; the message names what happened and the next action."""


@dataclass(frozen=True)
class Scope:
    root: Path
    slug: str
    real: Path
    dir: Path
    projects: Path
    usage: Path


def check_out_dir(out: Path, root: Path) -> None:
    if not out.is_relative_to(root):
        return
    # Probe a file inside: a trailing-slash pattern misses a folder that does not exist yet.
    result = subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', str(out / 'report-probe.html')],
                            capture_output=True, text=True, check=False)
    if result.returncode == 1:
        raise Refusal(f'{out} is not ignored by git, and a report quotes your session text. Add the line '
                      f'/{out.relative_to(root).as_posix()}/ to {root / ".gitignore"}, then re-run.')
    if result.returncode != 0:
        raise Refusal(f'git check-ignore failed: {result.stderr.strip()}')


def is_kept_folder(name: str, slug: str, uid: int) -> bool:
    scratchpad = rf'-tmp-claude-{uid}-{re.escape(slug)}-.+-scratchpad(-.*)?'
    return name == slug or re.fullmatch(scratchpad, name) is not None


def is_kept_path(project_path: str, scope: Scope, uid: int) -> bool:
    path = os.path.normpath(project_path)
    scratchpad = rf'/tmp/claude-{uid}/{re.escape(scope.slug)}/[^/]+/scratchpad(/.*)?'
    inside = path == str(scope.root) or path.startswith(f'{scope.root}/')
    return inside or re.fullmatch(scratchpad, path) is not None


def stray_sessions(scope: Scope, uid: int) -> list[str]:
    """Analysed sessions whose recorded folder is outside this repo: the proof that the scope held."""
    stray = []
    for path in sorted((scope.usage / 'session-meta').glob('*.json')):
        try:
            project_path = json.loads(path.read_text(encoding='utf-8')).get('project_path')
        except (OSError, ValueError, AttributeError):
            project_path = None
        if not isinstance(project_path, str) or not is_kept_path(project_path, scope, uid):
            stray.append(f'{path.name}: {project_path}')
    return stray


def kept_folders(scope: Scope, uid: int) -> list[Path]:
    """This repo's session folders, refusing any symlink: /insights skips one, and one inside could lead out."""
    projects = scope.real / 'projects'
    entries = sorted(os.scandir(projects), key=lambda entry: entry.name) if projects.is_dir() else []
    folders = [Path(entry.path) for entry in entries if is_kept_folder(entry.name, scope.slug, uid)]
    for folder in folders:
        for dirpath, dirs, names in os.walk(folder):
            if Path(dirpath) == folder and 'memory' in dirs:
                dirs.remove('memory')
            for path in (folder, *(Path(dirpath, name) for name in (*dirs, *names))):
                if path.is_symlink():
                    raise Refusal(f'{path} is a symlink in a kept folder. Replace or remove it, then re-run.')
    return [folder for folder in folders if folder.is_dir()]


def remove_scoped_projects(scope: Scope) -> None:
    if os.path.lexists(scope.projects):
        if (resolved := scope.projects.resolve()) != scope.dir.resolve() / 'projects':
            raise Refusal(f'{scope.projects} resolves to {resolved}, outside the scope. Remove that link by hand.')
        shutil.rmtree(resolved)


def _link(source: Path, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except FileNotFoundError:
        return False
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            raise Refusal(f'{target} is on another filesystem from {source}. Keep both on one disk.') from exc
        raise
    return True


def build_link_farm(folders: list[Path], scope: Scope) -> list[str]:
    """Hard link every transcript and its side folder into the scope; return the linked session ids."""
    remove_scoped_projects(scope)
    linked = []
    for folder in folders:
        for transcript in sorted(folder.glob('*.jsonl')):
            if not _link(transcript, scope.projects / folder.name / transcript.name):
                continue
            linked.append(transcript.stem)
            for dirpath, _dirs, names in os.walk(transcript.with_suffix('')):
                for source in (Path(dirpath, name) for name in names):
                    _link(source, scope.projects / folder.name / source.relative_to(folder))
    return linked


def qualifies(meta: dict) -> bool:
    """Claude Code's own bar for a detailed analysis: two user messages and a minute."""
    count, minutes = meta.get('user_message_count'), meta.get('duration_minutes')
    return isinstance(count, (int, float)) and isinstance(minutes, (int, float)) and count >= 2 and minutes >= 1


def seed_cache(scope: Scope, session_ids: list[str]) -> None:
    for kind in ('session-meta', 'facets'):
        (scope.usage / kind).mkdir(parents=True, exist_ok=True)
        for session_id in session_ids:
            source = scope.real / 'usage-data' / kind / f'{session_id}.json'
            target = scope.usage / kind / source.name
            if source.exists() and not target.exists():
                shutil.copyfile(source, target)
                target.chmod(0o600)
    waiting = []
    for session_id in session_ids:
        path = scope.usage / 'session-meta' / f'{session_id}.json'
        try:
            meta = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and qualifies(meta) and not (scope.usage / 'facets' / path.name).exists():
            waiting.append((str(meta.get('start_time', '')), path))
    for _start, path in sorted(waiting, reverse=True)[:ANALYSES_PER_RUN]:
        path.unlink()


def child_env(config_dir: Path, token: str) -> dict[str, str]:
    # Drop the caller's own Claude Code variables, so a run started from inside a session starts clean.
    env = {key: value for key, value in os.environ.items() if not key.startswith(('ANTHROPIC_', 'CLAUDE'))}
    return {**env, 'CLAUDE_CONFIG_DIR': str(config_dir), 'CLAUDE_CODE_OAUTH_TOKEN': token}


def run_claude(scope: Scope, token: str, *args: str, timeout: int = RUN_TIMEOUT_S) -> str:
    try:
        result = subprocess.run(['claude', *args], cwd=scope.dir / 'cwd', env=child_env(scope.dir, token),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, errors='replace',
                                timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise Refusal('`claude` is not on PATH. Install Claude Code, then re-run.') from exc
    except subprocess.TimeoutExpired as exc:
        raise Refusal(f'claude {" ".join(args)} ran past {timeout} s. Check your usage limit, then re-run.') from exc
    if result.returncode != 0:
        detail = f'{result.stdout}\n{result.stderr}'.replace(token, '[token removed]').strip()[-2000:]
        raise Refusal(f'claude exited {result.returncode}:\n{detail}\n'
                      'If it refused the login, run `claude setup-token` again.')
    return result.stdout.replace(token, '[token removed]')


def report_counts(html: str) -> tuple[int, int]:
    """(analysed, listed) as the report states them; it omits the total when the two match."""
    match = SUBTITLE_RE.search(html)
    if match is None:
        raise Refusal('The report states no session counts, so Claude Code changed its layout. Update SUBTITLE_RE.')
    analysed = int(match.group(1).replace(',', ''))
    return analysed, int(match.group(2).replace(',', '')) if match.group(2) else analysed


def run(scope: Scope, out: Path, token: str) -> None:
    scope.dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(scope.dir / '.lock', 'w', encoding='utf-8') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise Refusal('Another run holds this scope folder. Wait for it to finish, then re-run.') from exc
        folders = kept_folders(scope, os.getuid())
        if not folders:
            raise Refusal(f'No folder in {scope.real / "projects"} is named {scope.slug}. Start a Claude Code '
                          'session in this repo first, or fix is_kept_folder.')
        try:
            linked = build_link_farm(folders, scope)
            if not linked:
                raise Refusal('The kept folders hold no sessions, so there is nothing to report on.')
            seed_cache(scope, linked)
            (scope.dir / 'settings.json').write_text(json.dumps(SCOPED_SETTINGS), encoding='utf-8')
            (scope.dir / 'cwd').mkdir(exist_ok=True)
            before = {path.name for path in scope.usage.glob('report-*.html')}
            analyses_before = len(list((scope.usage / 'facets').glob('*.json')))
            print(f'Running /insights on {len(linked)} sessions. It prints nothing for several minutes.', flush=True)
            output = run_claude(scope, token, '-p', '/insights')
            if stray := stray_sessions(scope, os.getuid()):
                raise Refusal('These analysed sessions are not from this repo, so no report was kept:\n  '
                              + '\n  '.join(stray) + f'\nDelete them from {scope.usage / "session-meta"}, then re-run.')
            new = sorted({path.name for path in scope.usage.glob('report-*.html')} - before)
            report = scope.usage / new[-1] if new else None
            if report is None or report.stat().st_size == 0:
                raise Refusal('/insights left no report, or an empty one. Check `claude --version` for a change.')
            analysed, listed = report_counts(report.read_text(encoding='utf-8', errors='replace'))
            if listed < len(linked) or listed == 0:
                raise Refusal(f'/insights listed {listed} of the {len(linked)} sessions linked, so it no longer '
                              'reads the scope in full. Check `claude --version` for a change in how it lists.')
            version = run_claude(scope, token, '--version', timeout=60).strip()
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(report, out / report.name)
            (out / report.name).chmod(0o600)
        finally:
            remove_scoped_projects(scope)
        added = len(list((scope.usage / 'facets').glob('*.json'))) - analyses_before
    print(f'{output.strip()}\n\nSessions analysed: {analysed} of {listed} listed ({len(linked)} linked).\n'
          f'Detailed analyses: {added} new this run. Each run adds up to {ANALYSES_PER_RUN}.\n'
          f'Claude Code: {version}\nReport: {out / report.name}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claude Code's /insights report, from one repo's sessions.")
    parser.add_argument('--out', type=Path, help='folder the report is copied to (default: <repo>/insights/)')
    args = parser.parse_args(argv)
    try:
        # The common dir, so a run from a linked worktree still scopes to the main checkout.
        result = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise Refusal(f'Not inside a git repository ({result.stderr.strip()}). Run this from your repo.')
        root = Path(result.stdout.strip()).parent
        out = (args.out or root / 'insights').resolve()
        check_out_dir(out, root)
        token = os.environ.get('CLAUDE_CODE_OAUTH_TOKEN', '')
        if not token:
            raise Refusal('CLAUDE_CODE_OAUTH_TOKEN is not set. Run `claude setup-token` in a terminal, then '
                          '`read -rs CLAUDE_CODE_OAUTH_TOKEN && export CLAUDE_CODE_OAUTH_TOKEN`.')
        config, slug = Path.home() / '.claude', re.sub(r'[^a-zA-Z0-9]', '-', str(root))
        scope_dir = config / 'insights-loop-scope' / root.name
        run(Scope(root, slug, config, scope_dir, scope_dir / 'projects', scope_dir / 'usage-data'), out, token)
    except Refusal as exc:
        print(f'\nREFUSED: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
