"""LLM-based semantic compression using kiro-cli as the inference engine."""

import re
import subprocess
from pathlib import Path

from .compressor import CompressionResult


COMPRESS_PROMPT = """Compress this AI agent instruction file for token efficiency.

Rules:
- Preserve ALL semantic meaning, paths, names, triggers, procedures, behavioral rules
- Remove markdown formatting (bold **, backticks `, horizontal rules ---)
- Remove blank lines between items
- Use shorthand notation (→, =, |, w/o, incl.)
- Collapse short bullet lists into inline text separated by |
- Remove filler words and articles where meaning is preserved
- Keep code blocks and code examples unchanged
- Keep safety/behavioral rules as clear sentences (don't weaken them)
- For tables: convert to compact key=value or inline format
- Do NOT add any explanation, commentary, or preamble

Output ONLY the compressed version, nothing else."""


def llm_compress_file(filepath: str | Path, quiet: bool = False) -> CompressionResult:
    """Compress a file using kiro-cli as the LLM backend."""
    filepath = Path(filepath)
    content = filepath.read_text()

    prompt = f"{COMPRESS_PROMPT}\n\n---\n{content}\n---"

    result = subprocess.run(
        ["kiro-cli", "chat", "--no-interactive", "--trust-tools="],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        if not quiet:
            print(f"  ⚠️  LLM compression failed for {filepath.name}, keeping original")
        return CompressionResult(
            original=content,
            compressed=content,
            original_bytes=len(content.encode()),
            compressed_bytes=len(content.encode()),
        )

    # Clean output: remove ANSI codes, thinking lines, tool use lines
    compressed = result.stdout
    compressed = re.sub(r"\x1B\[[0-9;]*m", "", compressed)  # ANSI
    compressed = re.sub(r"^.*\(using tool:.*$\n?", "", compressed, flags=re.MULTILINE)
    compressed = re.sub(r"^.*Completed in.*$\n?", "", compressed, flags=re.MULTILINE)
    compressed = re.sub(r"^.*reasoning process.*$\n?", "", compressed, flags=re.MULTILINE)
    compressed = re.sub(r"^> ", "", compressed, flags=re.MULTILINE)  # quote markers
    compressed = re.sub(r"^\s*[✓⋮]\s*.*$\n?", "", compressed, flags=re.MULTILINE)
    compressed = re.sub(r"\n{3,}", "\n\n", compressed)
    compressed = compressed.strip()

    # Sanity check: if compressed is larger or empty, keep original
    if not compressed or len(compressed.encode()) >= len(content.encode()):
        if not quiet:
            print(f"  ⚠️  No improvement for {filepath.name}, keeping original")
        return CompressionResult(
            original=content,
            compressed=content,
            original_bytes=len(content.encode()),
            compressed_bytes=len(content.encode()),
        )

    return CompressionResult(
        original=content,
        compressed=compressed,
        original_bytes=len(content.encode()),
        compressed_bytes=len(compressed.encode()),
    )


def llm_compress_dir(input_dir: str | Path, output_dir: str | Path, quiet: bool = False) -> dict:
    """Compress all .md files in a directory using LLM."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = {}
    total_original = 0
    total_compressed = 0

    for md_file in sorted(input_path.glob("*.md")):
        if not quiet:
            print(f"  Compressing {md_file.name}...", end=" ", flush=True)

        result = llm_compress_file(md_file, quiet=True)
        results[md_file.name] = result

        out_file = output_path / md_file.name
        out_file.write_text(result.compressed)

        total_original += result.original_bytes
        total_compressed += result.compressed_bytes

        if not quiet:
            print(f"{result.original_bytes:,} → {result.compressed_bytes:,} ({result.reduction_pct:.0f}%)")

    if not quiet and total_original > 0:
        pct = (1 - total_compressed / total_original) * 100
        print(f"\n  Total: {total_original:,} → {total_compressed:,} bytes ({pct:.1f}% reduction)")

    return results
