"""Check a built KeyStow.app really runs on both Intel and Apple Silicon Macs.

    python installer/audit_universal.py dist/KeyStow.app 14.0 evidence-dir

A universal launcher alone is not enough. Every Python extension module and
executable inside the app must carry both an arm64 and an x86_64 slice. A
shared library may be single-architecture only when the other architecture's
code never loads it: for example numpy's Intel slice links OpenBLAS while its
Apple Silicon slice uses Apple's Accelerate. No native file may need a newer
macOS than the app claims. Writes a report and fails otherwise.
macOS only (uses file, lipo, otool and vtool).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ARCHES = ("arm64", "x86_64")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def linked_names(file: Path, arch: str):
    """Base names of the libraries one slice of a binary loads."""
    out = run("otool", "-arch", arch, "-L", str(file)).splitlines()[1:]
    return {Path(line.strip().split(" (")[0]).name for line in out if line.strip()}


def main():
    app, floor, evidence = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    floor_v = tuple(int(x) for x in floor.split("."))
    evidence.mkdir(parents=True, exist_ok=True)
    natives = {}
    for file in sorted(app.rglob("*")):
        if file.is_file() and not file.is_symlink() and "Mach-O" in run("file", "-b", str(file)):
            natives[file] = set(run("lipo", "-archs", str(file)).split())
    # What each architecture actually loads, across every binary that has it.
    loads = {arch: set() for arch in ARCHES}
    for file, arches in natives.items():
        for arch in ARCHES:
            if arch in arches:
                loads[arch] |= linked_names(file, arch)
    rows, problems = [], []
    for file, arches in natives.items():
        rel = str(file.relative_to(app))
        build = run("vtool", "-show-build", str(file))
        minos = [tuple(int(x) for x in m.split(".")) for m in re.findall(r"minos (\d+(?:\.\d+)*)", build)]
        newest = max(minos) if minos else None
        rows.append({"file": rel, "arches": sorted(arches),
                     "minos": ".".join(map(str, newest)) if newest else None})
        missing = [a for a in ARCHES if a not in arches]
        if missing:
            is_library = file.suffix == ".dylib" or ".framework/" in rel
            if not is_library:  # extension modules (.so) and executables must be fat
                problems.append(f"{rel}: has only {sorted(arches)}")
            for arch in missing:
                if file.name in loads[arch]:
                    problems.append(f"{rel}: has no {arch} slice but {arch} code loads it")
        if newest and newest > floor_v:
            problems.append(f"{rel}: needs macOS {'.'.join(map(str, newest))}, above {floor}")
    if len(rows) < 10:
        problems.append(f"only {len(rows)} native files found; the scan looks wrong")
    report = {"native_files": len(rows), "floor": floor, "problems": problems, "files": rows}
    (evidence / "universal-audit.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"Audited {len(rows)} native files: both architectures where needed, macOS <= {floor}")
    if problems:
        print("\n".join(problems[:60]))
        sys.exit(1)


if __name__ == "__main__":
    main()
