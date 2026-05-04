#!/usr/bin/env python3
"""
project_analytics.py

Generate a single text analytics report for the current project while honoring
.gitignore rules (top-level and nested).

Usage:
    ./project_analytics.py [--root /path/to/project]
                           [--outdir /dir/for/output]
                           [--top-level-gitignore-only]
                           [--quiet]
"""

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pathspec  # pip install pathspec

# Folders to always skip by name (in addition to .gitignore rules)
DEFAULT_FOLDER_IGNORES = {
    ".git", "node_modules", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
}

# Files/dirs that can mark a project root when walking upward (besides .git/)
ROOT_MARKERS = (
    ".git", "pyproject.toml", "package.json", "package-lock.json",
    "requirements.txt", "setup.cfg", "setup.py", "Pipfile", "poetry.lock",
)

SPECIAL_FILENAMES: Dict[str, str] = {
    ".env": "Env",
    ".gitignore": "GitIgnore",
    ".gitattributes": "GitAttributes",
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "license": "License",
    "readme": "Markdown",
}

LANGUAGE_MAP: Dict[str, str] = {
    ".py": "Python",
    ".ipynb": "Notebook",
    ".js": "JavaScript",
    ".jsx": "React/JSX",
    ".ts": "TypeScript",
    ".tsx": "TypeScript/TSX",
    ".cjs": "JavaScript",
    ".mjs": "JavaScript",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".md": "Markdown",
    ".txt": "Text",
    ".tex": "LaTeX",
    ".bib": "BibTeX",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".xml": "XML",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".sql": "SQL",
    ".log": "Log",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C/C++ Header",
    ".rs": "Rust",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".m": "MATLAB/Octave",
    ".jl": "Julia",
    ".lua": "Lua",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".lock": "Lockfile",
    ".pdf": "Asset/PDF",
    ".doc": "Asset/Doc",
    ".docx": "Asset/Doc",
    ".xls": "Asset/Spreadsheet",
    ".xlsx": "Asset/Spreadsheet",
    ".ppt": "Asset/Presentation",
    ".pptx": "Asset/Presentation",
    ".png": "Asset/Image",
    ".jpg": "Asset/Image",
    ".jpeg": "Asset/Image",
    ".gif": "Asset/Image",
    ".webp": "Asset/Image",
    ".svg": "Asset/Image",
    ".ico": "Asset/Image",
    ".bmp": "Asset/Image",
    ".tif": "Asset/Image",
    ".tiff": "Asset/Image",
    ".mp3": "Asset/Audio",
    ".wav": "Asset/Audio",
    ".mp4": "Asset/Video",
    ".mov": "Asset/Video",
    ".avi": "Asset/Video",
    ".zip": "Archive",
    ".tar": "Archive",
    ".gz": "Archive",
    ".bz2": "Archive",
    ".xz": "Archive",
    ".7z": "Archive",
}

BINARY_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".tif", ".tiff", ".mp3", ".wav", ".mp4", ".mov", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".pyc", ".pyo", ".so",
}


def find_project_root(start: Path) -> Path:
    """Prefer a git repo root; otherwise the first parent containing any root marker."""
    cur = start.resolve()

    p = cur
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent

    p = cur
    while p != p.parent:
        if any((p / marker).exists() for marker in ROOT_MARKERS if marker != ".git"):
            return p
        p = p.parent

    raise FileNotFoundError(f"Could not determine project root above {start}")


def _read_gitignore_file(gi_path: Path, rel_prefix: str) -> List[str]:
    """
    Read a .gitignore file and return patterns adjusted to be relative to the
    project root by prefixing with `rel_prefix` (POSIX-style).
    """
    pats: List[str] = []
    for raw in gi_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        def pref(pattern: str) -> str:
            pattern = pattern.lstrip("/")
            return f"{rel_prefix}/{pattern}" if rel_prefix else pattern

        if line.endswith("/"):
            dirname = line.rstrip("/")
            prefixed = pref(dirname)
            pats.append(prefixed)
            pats.append(f"{prefixed}/**")
        else:
            pats.append(pref(line))
    return pats


def load_gitignore_patterns(root: Path, top_level_only: bool) -> pathspec.PathSpec:
    """Build a gitwildmatch PathSpec from .gitignore files."""
    all_patterns: List[str] = []
    top = root / ".gitignore"

    if top.exists():
        all_patterns.extend(_read_gitignore_file(top, rel_prefix=""))

    if not top_level_only:
        for gi in root.rglob(".gitignore"):
            if gi == top:
                continue
            rel_dir = gi.parent.relative_to(root).as_posix()
            all_patterns.extend(_read_gitignore_file(gi, rel_prefix=rel_dir))

    return pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)


def collect_non_ignored(root: Path, ignore_spec: pathspec.PathSpec) -> List[Path]:
    """Collect all non-ignored entries under `root`, including `root` itself."""
    entries: List[Path] = []

    def recurse(path: Path) -> None:
        rel = path.relative_to(root).as_posix()
        if path.name in DEFAULT_FOLDER_IGNORES:
            return
        if rel and ignore_spec.match_file(rel):
            return

        entries.append(path)
        if path.is_dir():
            for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                recurse(child)

    recurse(root)
    return entries


def classify_path(path: Path) -> str:
    """Classify a file path into a language or asset bucket."""
    name_lower = path.name.lower()
    stem_lower = path.stem.lower()

    if name_lower in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[name_lower]
    if stem_lower in SPECIAL_FILENAMES and path.suffix.lower() == ".md":
        return SPECIAL_FILENAMES[stem_lower]

    suffixes = [suffix.lower() for suffix in path.suffixes]
    for suffix in reversed(suffixes):
        if suffix in LANGUAGE_MAP:
            return LANGUAGE_MAP[suffix]

    return "Other"


def count_file_lines(path: Path) -> int:
    """Count logical lines for text files and return 0 for likely-binary files."""
    if any(suffix.lower() in BINARY_EXTENSIONS for suffix in path.suffixes):
        return 0

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except Exception:
        return 0


def analyze_tree(
    root: Path,
    ignore_spec: pathspec.PathSpec,
    quiet: bool = False,
) -> Tuple[int, int, int, Dict[str, Tuple[int, int]], Set[str]]:
    """
    Count directories, files, total lines, and per-language file and line totals.
    """
    non_ignored = collect_non_ignored(root, ignore_spec)
    total_process = len(non_ignored)
    other_exts: Set[str] = set()

    if total_process == 0:
        return 1, 0, 0, {}, set()

    bar_length = 40
    total_dirs = 0
    total_files = 0
    total_lines = 0
    lang_stats: Dict[str, Tuple[int, int]] = {}
    next_update = 0.0

    if not quiet:
        print("Processing non-ignored entries...")

    for idx, path in enumerate(non_ignored):
        percent = (idx + 1) / total_process
        if not quiet and percent >= next_update:
            filled = int(bar_length * percent)
            bar = "#" * filled + " " * (bar_length - filled)
            print(f"\rProcessing:     [{bar}] {percent * 100:6.1f}%", end="", flush=True)
            next_update += 0.01

        if path.is_dir():
            total_dirs += 1
            continue

        total_files += 1
        language = classify_path(path)
        if language == "Other":
            ext = "".join(path.suffixes).lower() or "<no extension>"
            other_exts.add(ext)

        line_count = count_file_lines(path)
        total_lines += line_count
        prev_files, prev_lines = lang_stats.get(language, (0, 0))
        lang_stats[language] = (prev_files + 1, prev_lines + line_count)

    if not quiet:
        print(f"\rProcessing:     [{'#' * bar_length}] 100.0%")

    return total_dirs, total_files, total_lines, lang_stats, other_exts


def format_section_header(title: str) -> str:
    return f"{'=' * 5} {title} {'=' * 5}\n\n"


def format_report_block(
    total_dirs: int,
    total_files: int,
    total_lines: int,
    lang_stats: Dict[str, Tuple[int, int]],
    other_exts: Optional[Set[str]] = None,
) -> str:
    lines = [
        f"Total directories: {total_dirs:,}",
        f"Total files      : {total_files:,}",
        f"Total lines      : {total_lines:,}",
        "",
        "By language / type:",
    ]

    formatted_counts = [f"{file_count:,}" for file_count, _ in lang_stats.values()]
    max_fcount_width = max((len(value) for value in formatted_counts), default=0)

    for lang, (file_count, line_count) in sorted(lang_stats.items()):
        file_count_str = f"{file_count:,}".rjust(max_fcount_width)
        lines.append(f"  {lang:<20} Files: {file_count_str}  Lines: {line_count:,}")

    if other_exts:
        lines.append("")
        lines.append("Extensions grouped into Other:")
        for ext in sorted(other_exts):
            lines.append(f"  {ext}")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a .txt project analytics report that respects .gitignore."
    )
    parser.add_argument("--root", type=Path, default=None,
                        help="Project root. If omitted, detect via git or common markers.")
    parser.add_argument("--outdir", type=Path, default=None,
                        help="Output directory. Defaults to the script's folder.")
    parser.add_argument("--top-level-gitignore-only", action="store_true",
                        help="Honor only the top-level .gitignore.")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress the progress bar and informational console output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = args.root.resolve() if args.root else find_project_root(script_dir)
    ignore_spec = load_gitignore_patterns(project_root, top_level_only=args.top_level_gitignore_only)

    dirs_count, files_count, total_lines, lang_stats, other_exts = analyze_tree(
        project_root,
        ignore_spec,
        quiet=args.quiet,
    )

    report = (
        format_section_header("ANALYSIS (With .gitignore)") +
        format_report_block(dirs_count, files_count, total_lines, lang_stats, other_exts)
    )

    out_dir = args.outdir.resolve() if args.outdir else script_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / "project_analytics.txt"
    output_file.write_text(report, encoding="utf-8")

    if not args.quiet:
        print(f"\nProject root detected: {project_root}")
        print(f"Wrote analytics report to: {output_file}")


if __name__ == "__main__":
    main()
