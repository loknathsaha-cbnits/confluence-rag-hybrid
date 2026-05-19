#!/usr/bin/env python3
"""
Hybrid RAG Dependency Auditor
-------------------------------
Run this inside your project root (where pyproject.toml lives):

    uv run python audit_deps.py

Or with a plain venv:

    pip install pip-audit pipdeptree
    python audit_deps.py

It will:
  1. Parse your pyproject.toml direct dependencies
  2. Run `uv pip tree` (or pipdeptree fallback) to get the full transitive tree
  3. Flag GPU/CUDA bloat specifically
  4. Suggest the minimal CPU-safe replacements
"""

import subprocess
import sys
import json
import re
from pathlib import Path

# ── colour helpers ────────────────────────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def h(text, colour=BOLD):   return f"{colour}{text}{RESET}"

# ── known GPU/CUDA bloat packages ─────────────────────────────────────────────
GPU_BLOAT = {
    "nvidia-nvjitlink",
    "nvidia-curand",
    "nvidia-nvshmem-cu13", "nvidia-nvshmem-cu12",
    "nvidia-cuda-nvrtc",
    "nvidia-cusparse",
    "nvidia-cusparselt-cu13", "nvidia-cusparselt-cu12",
    "nvidia-cusolver",
    "nvidia-nccl-cu13",    "nvidia-nccl-cu12",
    "nvidia-cufft",
    "nvidia-cudnn-cu13",   "nvidia-cudnn-cu12",
    "nvidia-cublas",
    "triton",
    "onnxruntime-gpu",
}

# packages that *pull in* GPU torch unless you pin the CPU wheel first
GPU_TRIGGERS = {
    "torch":               "https://download.pytorch.org/whl/cpu",
    "torchvision":         "https://download.pytorch.org/whl/cpu",
    "torchaudio":          "https://download.pytorch.org/whl/cpu",
    "sentence-transformers": None,   # fine once torch is CPU-pinned
    "transformers":          None,
    "onnxruntime":           None,   # CPU version is just onnxruntime (no -gpu)
}

# safe CPU-only alternatives / install notes
CPU_ALTERNATIVES = {
    "torch":         'torch --index-url https://download.pytorch.org/whl/cpu',
    "torchvision":   'torchvision --index-url https://download.pytorch.org/whl/cpu',
    "torchaudio":    'torchaudio --index-url https://download.pytorch.org/whl/cpu',
    "onnxruntime-gpu": "onnxruntime  # drop the -gpu suffix",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def run(cmd: list[str]) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def parse_pyproject(path: Path) -> list[str]:
    """Very lightweight toml parser – avoids requiring tomllib on older Pythons."""
    try:
        if sys.version_info >= (3, 11):
            import tomllib
            data = tomllib.loads(path.read_text())
        else:
            import tomli  # uv installs this automatically
            data = tomli.loads(path.read_text())
        deps = data.get("project", {}).get("dependencies", [])
        # also check tool.uv.sources or tool.poetry.dependencies
        return deps
    except Exception:
        # fallback: regex grab
        text = path.read_text()
        block = re.search(r'dependencies\s*=\s*\[(.*?)\]', text, re.S)
        if not block:
            return []
        raw = block.group(1)
        return [m.group(1) for m in re.finditer(r'"([^"]+)"', raw)]


def pkg_name(dep_str: str) -> str:
    """Strip version specifiers from a dependency string."""
    return re.split(r'[>=<!;\[\s]', dep_str.strip())[0].lower().replace("_", "-")


def get_dep_tree() -> str:
    """Try uv pip tree first, fall back to pipdeptree."""
    code, out, _ = run(["uv", "pip", "tree"])
    if code == 0 and out.strip():
        return out
    code, out, _ = run(["pipdeptree"])
    if code == 0:
        return out
    # last resort: uv pip list
    _, out, _ = run(["uv", "pip", "list"])
    return out


def get_installed_packages() -> dict[str, str]:
    """Returns {name: version} for everything currently installed."""
    code, out, _ = run(["uv", "pip", "list", "--format", "json"])
    if code == 0:
        try:
            return {p["name"].lower(): p["version"] for p in json.loads(out)}
        except Exception:
            pass
    # fallback
    installed = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            installed[parts[0].lower()] = parts[1]
    return installed


def size_of(pkg: str) -> str:
    """Best-effort: ask pip for the dist-info directory size."""
    code, out, _ = run(["uv", "pip", "show", pkg])
    if code != 0:
        return "?"
    for line in out.splitlines():
        if line.lower().startswith("location:"):
            loc = Path(line.split(":", 1)[1].strip())
            # look for dist-info
            norm = pkg.replace("-", "_")
            for d in loc.glob(f"{norm}-*.dist-info"):
                record = d / "RECORD"
                if record.exists():
                    # sum up all files
                    total = 0
                    for entry in record.read_text(errors="ignore").splitlines():
                        parts = entry.split(",")
                        if len(parts) >= 3 and parts[2].strip().isdigit():
                            total += int(parts[2].strip())
                    if total:
                        return f"{total / 1_048_576:.1f} MiB"
    return "?"

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print(h("\n╔══════════════════════════════════════════════╗"))
    print(h("║   Hybrid RAG Dependency Auditor              ║"))
    print(h("╚══════════════════════════════════════════════╝\n"))

    # 1. Parse pyproject.toml
    toml_path = Path("pyproject.toml")
    if not toml_path.exists():
        print(h("✗ pyproject.toml not found. Run this from your project root.", RED))
        sys.exit(1)

    direct_deps = [pkg_name(d) for d in parse_pyproject(toml_path)]
    print(h("📦 Direct dependencies in pyproject.toml:", CYAN))
    for d in direct_deps:
        print(f"   • {d}")
    print()

    # 2. Get installed packages
    installed = get_installed_packages()
    print(h(f"🔍 Total installed packages: {len(installed)}", CYAN))
    print()

    # 3. Flag GPU bloat
    found_bloat = [p for p in GPU_BLOAT if p in installed]
    if found_bloat:
        print(h("🚨 GPU/CUDA bloat detected (safe to eliminate for RAG):", RED))
        for p in sorted(found_bloat):
            sz = size_of(p)
            print(f"   {h('✗', RED)} {p:<40} {h(sz, YELLOW)}")
        print()
    else:
        print(h("✓ No GPU/CUDA bloat detected.\n", GREEN))

    # 4. Flag GPU-trigger packages
    print(h("⚠️  GPU-trigger packages (need CPU pinning):", YELLOW))
    triggers_found = []
    for pkg, idx_url in GPU_TRIGGERS.items():
        if pkg in installed:
            ver = installed[pkg]
            note = f"  → pin via: {idx_url}" if idx_url else "  → OK once torch is CPU-pinned"
            triggers_found.append(pkg)
            colour = YELLOW if pkg in ("torch", "torchvision", "torchaudio") else GREEN
            print(f"   {h('⚠', colour)} {pkg:<35} {ver:<15} {note}")
    if not triggers_found:
        print("   (none found)")
    print()

    # 5. Dependency tree (trimmed)
    print(h("🌲 Dependency tree (torch subtree highlighted):", CYAN))
    tree = get_dep_tree()
    for line in tree.splitlines():
        lower = line.lower()
        if any(b in lower for b in GPU_BLOAT):
            print(f"   {h(line, RED)}")
        elif "torch" in lower:
            print(f"   {h(line, YELLOW)}")
        else:
            print(f"   {line}")
    print()

    # 6. Actionable recommendations
    print(h("✅ Recommended fixes for pyproject.toml:", GREEN))
    print()

    print(h("  1. Add a [tool.uv.sources] override for CPU torch:", CYAN))
    print("""
  [tool.uv.sources]
  torch = { url = "https://download.pytorch.org/whl/cpu/torch-2.6.0+cpu-cp311-cp311-linux_x86_64.whl" }
  # Replace cp311 with your Python version (cp310, cp312 …)
  # Find exact wheel: https://download.pytorch.org/whl/cpu/
""")

    print(h("  2. Or use a find-links index in pyproject.toml:", CYAN))
    print("""
  [tool.uv]
  extra-index-url = ["https://download.pytorch.org/whl/cpu"]
""")

    print(h("  3. Then re-lock and re-sync:", CYAN))
    print("""
  uv lock --upgrade-package torch
  uv sync
""")

    print(h("  4. Verify no GPU packages remain:", CYAN))
    print("""
  uv pip list | grep -iE 'nvidia|cuda|triton'
  # Should return nothing
""")

    print(h("  5. Confirm torch is CPU-only:", CYAN))
    print("""
  uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
  # Expected: 2.x.x+cpu   False
""")

    # 7. What you actually need
    print(h("📋 Minimal dependencies for your Hybrid RAG stack:", CYAN))
    rag_deps = [
        ("sentence-transformers", "embeddings"),
        ("pinecone-client / pinecone", "vector DB"),
        ("rank-bm25",               "BM25 sparse index"),
        ("torch (CPU wheel)",        "required by sentence-transformers"),
        ("transformers",             "tokenisers / models"),
        ("numpy",                    "array ops"),
        ("tqdm",                     "progress bars (optional)"),
    ]
    for pkg, purpose in rag_deps:
        print(f"   {h('✓', GREEN)} {pkg:<35} # {purpose}")

    print()
    print(h("Everything else in that screenshot is CUDA runtime pulled in by the GPU torch wheel.", YELLOW))
    print(h("Switching to the CPU wheel eliminates ~400 MiB of NVIDIA packages.\n", YELLOW))


if __name__ == "__main__":
    main()