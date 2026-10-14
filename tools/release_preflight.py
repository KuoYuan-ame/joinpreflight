"""Offline, read-only release preflight audit for JoinPreflight.

Python >=3.10, standard library only. This tool never changes repository files.
Run from any directory:
    python tools/release_preflight.py --json reports/release_preflight.json
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REQUIRED = (
    'pyproject.toml', 'README.md', 'LICENSE', '.gitignore',
    'src/joinpreflight/__init__.py', 'src/joinpreflight/cli.py',
    'src/joinpreflight/joins.py',
)
RECOMMENDED = (
    'CONTRIBUTING.md', 'CHANGELOG.md',
    '.github/workflows/ci.yml', '.github/workflows/release.yml',
    'docs/REPRODUCIBILITY.md',
    'examples/sample_data/orders.csv',
    'examples/sample_data/order_items.csv',
    'examples/sample_data/payments.csv',
    'tools/smoke_demo.py',
)
ADVANCED = (
    'src/joinpreflight/relationship_matrix.py',
    'src/joinpreflight/segmented_analysis.py',
    'src/joinpreflight/bootstrap_inference.py',
)
SECRET_NAME_PATTERN = re.compile(
    r'(^|/)(\.env($|\.)|id_rsa|id_ed25519|.*\.(pem|p12|pfx|key)$|credentials\.json$|token\.txt$)',
    re.I,
)
BAD_NAME_PATTERN = re.compile(r'(^|/)(\.venv|venv|__pycache__|\.pytest_cache|reports|data)/', re.I)
IMAGE_PATTERN = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
SENSITIVE_TEXT = re.compile(
    r'(?i)(?:github_pat_[A-Za-z0-9_]{15,}|ghp_[A-Za-z0-9]{20,}|'
    r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|'
    r'(?:api[_-]?key|access[_-]?token)\s*[=:]\s*[\"\']?[A-Za-z0-9_\-]{24,})'
)


def get_project_fields(text: str) -> dict:
    """Read key packaging fields without installing another TOML dependency."""
    try:
        import tomllib  # Python 3.11+
        config = tomllib.loads(text)
        proj = config.get('project', {})
        return {
            'name': proj.get('name'),
            'version': proj.get('version'),
            'python': proj.get('requires-python'),
            'dependencies': list(proj.get('dependencies', [])),
            'extras': dict(proj.get('optional-dependencies', {})),
            'entrypoints': dict(proj.get('scripts', {})),
        }
    except ImportError:
        # Minimal text fallback for Python 3.10; native packaging/build validates TOML.
        def section(name: str) -> str:
            m = re.search(r'(?ms)^\[' + re.escape(name) + r'\]\s*(.*?)(?=^\[|\Z)', text)
            return m.group(1) if m else ''
        def scalar(s: str, name: str) -> str | None:
            m = re.search(r'(?m)^\s*' + re.escape(name) + r'\s*=\s*[\"\']([^\"\']+)', s)
            return m.group(1) if m else None
        proj = section('project')
        extras = section('project.optional-dependencies')
        dep_section = proj + '\n' + extras
        return {
            'name': scalar(proj, 'name'),
            'version': scalar(proj, 'version'),
            'python': scalar(proj, 'requires-python'),
            'dependencies': [dep_section],
            'extras': {'raw': dep_section},
            'entrypoints': {'joinpreflight': scalar(section('project.scripts'), 'joinpreflight')},
        }


def git_cmd(root: Path, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ['git', '-C', str(root), *args], capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=15, check=False,
        )
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ''


def examine(root: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    passes: list[str] = []
    missing = [f for f in REQUIRED if not (root / f).is_file()]
    if missing:
        errors.append('Required files are missing: ' + ', '.join(missing))
    else:
        passes.append('Required packaging, package, and repository files exist')
    missing_recommended = [f for f in RECOMMENDED if not (root / f).is_file()]
    if missing_recommended:
        warnings.append('Recommended release files missing: ' + ', '.join(missing_recommended))
    else:
        passes.append('Recommended release files exist')

    pyproject = root / 'pyproject.toml'
    metadata: dict = {}
    if pyproject.exists():
        try:
            metadata = get_project_fields(pyproject.read_text(encoding='utf-8'))
            if metadata.get('name') != 'joinpreflight':
                errors.append('pyproject [project].name must be joinpreflight')
            else:
                passes.append('Package name is joinpreflight')
            if not metadata.get('version'):
                errors.append('pyproject version missing or dynamic: verify packaging metadata')
            entry = metadata.get('entrypoints', {}).get('joinpreflight')
            if entry != 'joinpreflight.cli:main':
                errors.append('CLI entry point must be joinpreflight = "joinpreflight.cli:main"')
            else:
                passes.append('CLI entry point looks correct')
            all_deps = ' '.join(str(x) for x in metadata.get('dependencies', []))
            all_deps += ' ' + ' '.join(str(x) for v in metadata.get('extras', {}).values() for x in (v if isinstance(v,list) else [v]))
            for dep in ('matplotlib', 'scipy'):
                if not re.search(r'\b' + dep + r'\b', all_deps, re.I):
                    warnings.append(f'{dep} is not declared in dependencies/extras; v7.x visual/inference paths need it')
        except (OSError, ValueError) as exc:
            errors.append(f'Cannot read packaging fields: {type(exc).__name__}: {exc}')

    readme = root / 'README.md'
    if readme.is_file():
        content = readme.read_text(encoding='utf-8', errors='replace')
        for raw in IMAGE_PATTERN.findall(content):
            path = raw.strip().split(' ', 1)[0].strip('<>')
            if path.startswith(('http:', 'https:', 'data:', '#')):
                continue
            if not (root / path.split('#', 1)[0]).is_file():
                errors.append(f'README image file missing: {path}')
        if 'YOUR_GITHUB_USERNAME' in content:
            warnings.append('README contains YOUR_GITHUB_USERNAME placeholder')
        if 'bootstrap' not in content.lower():
            warnings.append('README does not describe v7.3 Bootstrap analysis')
        if not errors or not any(s.startswith('README image') for s in errors):
            passes.append('README local image references checked')

    status, branch = git_cmd(root, 'branch', '--show-current')
    git_info: dict = {'branch': branch if status == 0 else None, 'head': None, 'tracked_files': 0, 'untracked_files': []}
    if status != 0:
        errors.append('Git repository is not initialized or git command is unavailable')
    else:
        _, head = git_cmd(root, 'rev-parse', '--short', 'HEAD')
        git_info['head'] = head
        if branch != 'main':
            warnings.append(f'Current Git branch is {branch or "(detached)"}, expected main for proposed release flow')
        code, tracked = git_cmd(root, 'ls-files')
        if code == 0:
            paths = [s for s in tracked.splitlines() if s]
            git_info['tracked_files'] = len(paths)
            for rel in paths:
                item = root / rel
                normalized = rel.replace('\\', '/')
                if BAD_NAME_PATTERN.search(normalized):
                    errors.append(f'Unwanted generated/private directory tracked: {rel}')
                if SECRET_NAME_PATTERN.search(normalized):
                    errors.append(f'Potential secret file tracked: {rel}')
                if item.is_file() and item.stat().st_size > 20 * 1024 * 1024:
                    warnings.append(f'Large tracked file (>20 MiB): {rel}')
                if item.is_file() and item.suffix.lower() in ('.py', '.toml', '.yml', '.yaml', '.md', '.txt', '.json') and item.stat().st_size < 1024*1024:
                    try:
                        if SENSITIVE_TEXT.search(item.read_text(encoding='utf-8', errors='replace')):
                            errors.append(f'Possible embedded credential in tracked text file: {rel} (review manually)')
                    except OSError:
                        pass
        code, others = git_cmd(root, 'ls-files', '--others', '--exclude-standard')
        if code == 0 and others:
            git_info['untracked_files'] = others.splitlines()
            warnings.append(f'{len(git_info["untracked_files"])} untracked files remain; review before publishing')
        code, changes = git_cmd(root, 'status', '--porcelain', '--untracked-files=no')
        if code == 0 and changes:
            warnings.append('Tracked files contain uncommitted changes; create a reviewed commit before release')
        if code == 0 and not changes and not git_info['untracked_files']:
            passes.append('Git worktree clean')
        code, remotes = git_cmd(root, 'remote', '-v')
        git_info['remote_configured'] = bool(remotes) if code == 0 else False
        if not git_info['remote_configured']:
            warnings.append('No Git remote configured; this is normal before creating the GitHub repository')
        # Inspect ignore rules without relying on shell expansion.
        for rel in ('.venv/x.py', 'reports/x.png', 'data/olist_orders_dataset.csv'):
            code, ignored = git_cmd(root, 'check-ignore', rel)
            if code != 0 or not ignored:
                warnings.append(f'Ignore rule not confirmed for: {rel}')

    absent_advanced = [p for p in ADVANCED if not (root / p).is_file()]
    if absent_advanced:
        warnings.append('v7.x advanced modules not found: ' + ', '.join(absent_advanced))
    else:
        passes.append('Adaptive matrix, segmented analysis and Bootstrap modules found')
    if not (root / 'tests').is_dir():
        errors.append('tests/ directory missing')
    if not (root / 'examples').is_dir():
        warnings.append('examples/ directory missing')

    return {
        'project_root': str(root),
        'package': {'name': metadata.get('name'), 'version': metadata.get('version'), 'requires_python': metadata.get('python')},
        'git': git_info,
        'checks': {'passed': passes, 'warnings': warnings, 'errors': errors},
        'summary': {'passed_checks': len(passes), 'warnings': len(warnings), 'errors': len(errors)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Read-only preflight audit for JoinPreflight releases')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--json', type=Path, help='Write machine-readable audit report (e.g. reports/release_preflight.json)')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors (optional, use after cleanup)')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report = examine(root)
    for label, category in (('PASS', 'passed'), ('WARN', 'warnings'), ('FAIL', 'errors')):
        for msg in report['checks'][category]:
            print(f'[{label}] {msg}')
    print('Summary:', json.dumps(report['summary'], ensure_ascii=False))
    print('Git:', json.dumps(report['git'], ensure_ascii=False))
    if args.json:
        out = args.json if args.json.is_absolute() else root / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Saved audit JSON:', out)
    return 1 if report['checks']['errors'] or (args.strict and report['checks']['warnings']) else 0

if __name__ == '__main__':
    sys.exit(main())
