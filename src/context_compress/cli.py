"""CLI interface for context-compress."""

import click
from pathlib import Path

from .compressor import compress_file, find_duplicates, CompressionConfig


@click.group()
@click.version_option()
def main():
    """Token-efficient compression for AI agent instruction files."""
    pass


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output file (default: stdout)")
@click.option("--level", type=click.Choice(["light", "medium", "heavy"]), default="medium")
@click.option("--quiet", is_flag=True, help="Suppress stats output")
def compress(input_file, output, level, quiet):
    """Compress a single instruction file."""
    content = Path(input_file).read_text()
    config = CompressionConfig(compression_level=level)
    result = compress_file(content, config)

    if output:
        Path(output).write_text(result.compressed)
    else:
        click.echo(result.compressed)

    if not quiet:
        click.echo(f"\n--- Stats ---", err=True)
        click.echo(f"Original:   {result.original_bytes:,} bytes", err=True)
        click.echo(f"Compressed: {result.compressed_bytes:,} bytes", err=True)
        click.echo(f"Reduction:  {result.reduction_pct:.1f}%", err=True)
        click.echo(f"\nSection classifications:", err=True)
        for section, ctype in result.sections_classified.items():
            click.echo(f"  {section[:40]:40s} → {ctype}", err=True)


@main.command("compress-dir")
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("-o", "--output-dir", type=click.Path(), required=True)
@click.option("--level", type=click.Choice(["light", "medium", "heavy"]), default="medium")
@click.option("--quiet", is_flag=True)
def compress_dir(input_dir, output_dir, level, quiet):
    """Compress all .md files in a directory (regex-based)."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    config = CompressionConfig(compression_level=level)
    total_original = 0
    total_compressed = 0

    for md_file in sorted(input_path.glob("*.md")):
        content = md_file.read_text()
        result = compress_file(content, config)

        out_file = output_path / md_file.name
        out_file.write_text(result.compressed)

        total_original += result.original_bytes
        total_compressed += result.compressed_bytes

        if not quiet:
            click.echo(
                f"  {md_file.name:30s} "
                f"{result.original_bytes:6,} → {result.compressed_bytes:6,} "
                f"({result.reduction_pct:.0f}%)"
            )

    if not quiet and total_original > 0:
        pct = (1 - total_compressed / total_original) * 100
        click.echo(f"\nTotal: {total_original:,} → {total_compressed:,} bytes ({pct:.1f}% reduction)")


@main.command("llm")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), required=True, help="Output file or directory")
@click.option("--quiet", is_flag=True)
def llm_compress(input_path, output, quiet):
    """Compress using LLM (kiro-cli) for semantic understanding. Much better results."""
    from .llm_compressor import llm_compress_file, llm_compress_dir

    path = Path(input_path)
    if path.is_dir():
        llm_compress_dir(path, output, quiet=quiet)
    else:
        result = llm_compress_file(path, quiet=quiet)
        Path(output).write_text(result.compressed)
        if not quiet:
            click.echo(f"  {path.name}: {result.original_bytes:,} → {result.compressed_bytes:,} ({result.reduction_pct:.1f}%)")


@main.command()
@click.argument("input_dir", type=click.Path(exists=True))
def stats(input_dir):
    """Show token usage statistics for a context directory."""
    input_path = Path(input_dir)
    files = {}
    total_bytes = 0

    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4")
        has_tiktoken = True
    except (ImportError, Exception):
        has_tiktoken = False

    click.echo(f"{'File':<35} {'Bytes':>8} {'Tokens':>8} {'%':>6}")
    click.echo("-" * 60)

    for md_file in sorted(input_path.rglob("*.md")):
        content = md_file.read_text()
        files[md_file.name] = content
        size = len(content.encode())
        total_bytes += size

        tokens = len(enc.encode(content)) if has_tiktoken else size // 4
        rel_path = str(md_file.relative_to(input_path))
        click.echo(f"{rel_path:<35} {size:>8,} {tokens:>8,}")

    click.echo("-" * 60)
    total_tokens = total_bytes // 4 if not has_tiktoken else None
    if has_tiktoken:
        all_content = "\n".join(files.values())
        total_tokens = len(enc.encode(all_content))
    click.echo(f"{'TOTAL':<35} {total_bytes:>8,} {total_tokens:>8,}")

    # Check for duplicates
    dupes = find_duplicates(files)
    if dupes:
        click.echo(f"\n⚠️  Found {len(dupes)} duplicate phrases across files:")
        for phrase, locations in list(dupes.items())[:5]:
            click.echo(f"  \"{phrase[:60]}...\"")
            click.echo(f"    in: {', '.join(locations)}")


@main.command()
@click.argument("input_dir", type=click.Path(exists=True))
def dedup(input_dir):
    """Find duplicate content across instruction files."""
    input_path = Path(input_dir)
    files = {}

    for md_file in sorted(input_path.rglob("*.md")):
        files[md_file.name] = md_file.read_text()

    dupes = find_duplicates(files)

    if not dupes:
        click.echo("No duplicates found.")
        return

    click.echo(f"Found {len(dupes)} duplicate phrases:\n")
    for phrase, locations in sorted(dupes.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        click.echo(f"  [{len(locations)}x] \"{phrase[:80]}\"")
        click.echo(f"       in: {', '.join(locations)}")
        click.echo()


if __name__ == "__main__":
    main()
