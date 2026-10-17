"""Zip an agent folder for upload, check it against the submission rules, and smoke-test the zip.

    python tools/package.py my_team
    python tools/package.py my_team --games 20     # longer smoke test against F

Writes submissions/<folder>-<time>.zip (submissions/ is git-ignored), with agent.py at the top level.
Then it unzips that file into a fresh temporary folder and plays the extracted copy against F, so
what gets tested is exactly what gets uploaded. Upload it from the team machine with ~/upload.sh.

Checks (PROBLEM_STATEMENT.md, section 4): agent.py at the top, at most 100 MB, no compiled code or
executables, and imports only from the standard library, the pinned packages, or the folder itself.
"""
import argparse
import ast
import datetime
import os
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 100 * 1024 * 1024
ALLOWED = {"numpy", "scipy", "sklearn", "torch", "catanatron", "networkx"}
COMPILED = {".so", ".pyd", ".dll", ".dylib", ".exe", ".pyc", ".pyo", ".o", ".a", ".bin", ".out"}
SKIP_DIRS = {"__pycache__", ".git", ".ipynb_checkpoints"}
SKIP_FILES = {".DS_Store"}


def files_in(folder):
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name not in SKIP_FILES:
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, folder)


def check(folder):
    """Return (errors, warnings) for the folder."""
    errors, warnings = [], []
    if not os.path.isfile(os.path.join(folder, "agent.py")):
        errors.append("no agent.py at the top of the folder")
    local = set()
    for full, rel in files_in(folder):
        top = rel.split(os.sep)[0]
        local.add(top[:-3] if top.endswith(".py") else top)
    total = 0
    for full, rel in files_in(folder):
        total += os.path.getsize(full)
        ext = os.path.splitext(rel)[1].lower()
        if ext in COMPILED:
            errors.append(f"compiled or binary file not allowed: {rel}")
        elif os.stat(full).st_mode & stat.S_IXUSR and ext != ".py":
            warnings.append(f"executable bit set: {rel}")
        with open(full, "rb") as f:
            if f.read(4) == b"\x7fELF":
                errors.append(f"executable (ELF) file not allowed: {rel}")
        if ext == ".py":
            errors += [f"{rel}: {m}" for m in check_imports(full, local)]
            with open(full, encoding="utf-8", errors="replace") as f:
                src = f.read()
            if "HYDE_INFERENCE_API_KEY" in src:
                warnings.append(f"{rel}: looks like it may contain an API key")
    if total > MAX_BYTES:
        errors.append(f"folder is {total / 2**20:.1f} MB, over the 100 MB limit")
    return errors, warnings, total


def check_imports(path, local):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    bad = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for name in names:
            top = name.split(".")[0]
            if top in sys.stdlib_module_names or top in ALLOWED or top in local:
                continue
            if top == "catan_kit":
                bad.append("imports catan_kit, which is the harness, not part of your agent; "
                           "copy what you need into your folder")
            else:
                bad.append(f"imports '{top}', which is not installed on the scoring machine")
    return bad


def build(folder, out_path):
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in files_in(folder):
            z.write(full, rel.replace(os.sep, "/"))


def smoke(zip_path, games, opponent):
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        agent = os.path.join(tmp, "agent.py")
        cmd = [sys.executable, os.path.join(ROOT, "tools", "parallel_eval.py"), "--a", agent,
               "--b", opponent, "--games", str(games), "--no-log", "--strict",
               "--workers", "4"]
        return subprocess.run(cmd, cwd=ROOT).returncode


def main(argv=None):
    p = argparse.ArgumentParser(description="Zip, check and smoke-test an agent folder.")
    p.add_argument("folder", help="the agent folder, with agent.py at its top")
    p.add_argument("--games", type=int, default=4, help="smoke-test games against the opponent")
    p.add_argument("--opponent", default=os.path.join(ROOT, "examples", "f_agent.py"))
    p.add_argument("--out", help="zip path (default: submissions/<folder>-<time>.zip)")
    args = p.parse_args(argv)

    folder = os.path.abspath(args.folder)
    errors, warnings, total = check(folder)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print("not packaged: fix the errors above")
        return 1

    name = os.path.basename(folder.rstrip(os.sep))
    out = args.out or os.path.join(
        ROOT, "submissions", f"{name}-{datetime.datetime.now():%Y%m%d-%H%M%S}.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build(folder, out)
    print(f"packed {total / 2**20:.2f} MB of files into {out} ({os.path.getsize(out) / 2**20:.2f} MB)")

    if args.games > 0:
        print(f"smoke test: the unzipped copy against {os.path.relpath(args.opponent, ROOT)}, "
              f"{args.games} games\n")
        if smoke(out, args.games, args.opponent) != 0:
            print("smoke test FAILED: do not upload this zip")
            return 1
    print(f"ready: copy {out} to the team machine and run ~/upload.sh on it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
