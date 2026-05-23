"""Tests for the compression engine."""

import pytest
from context_compress.compressor import (
    classify_section,
    compress_file,
    compress_section,
    find_duplicates,
    ContentType,
    CompressionConfig,
)


class TestClassification:
    def test_safety_rules_detected(self):
        text = "NEVER execute commands without explicit user approval"
        assert classify_section(text) == ContentType.SAFETY

    def test_safety_ask_before(self):
        text = "Before proceeding with destructive actions, always ask for confirmation"
        assert classify_section(text) == ContentType.SAFETY

    def test_preference_detected(self):
        text = "For python always use venv"
        assert classify_section(text) == ContentType.PREFERENCE

    def test_code_block_detected(self):
        text = "```python\nprint('hello')\n```"
        assert classify_section(text) == ContentType.CODE

    def test_reference_path(self):
        text = "Path: /Users/someone/Documents/vault\nConsult reference.md for details"
        assert classify_section(text) == ContentType.REFERENCE

    def test_prose_default(self):
        text = "This is a general description of how things work in the system."
        assert classify_section(text) == ContentType.PROSE


class TestCompression:
    def test_code_never_compressed(self):
        code = "```bash\npython3 -m venv .venv\nsource .venv/bin/activate\n```"
        result = compress_section(code, ContentType.CODE, CompressionConfig())
        assert result == code

    def test_safety_preserves_meaning(self):
        text = "**NEVER** execute commands without `explicit` user approval"
        result = compress_section(text, ContentType.SAFETY, CompressionConfig())
        assert "NEVER" in result
        assert "execute" in result
        assert "approval" in result
        # Formatting stripped
        assert "**" not in result
        assert "`" not in result

    def test_prose_compressed(self):
        text = "- Item one\n- Item two\n- Item three"
        result = compress_section(text, ContentType.PROSE, CompressionConfig())
        # Should be collapsed into inline
        assert "\n- " not in result

    def test_strip_markdown_bold(self):
        text = "This is **important** text"
        result = compress_section(text, ContentType.PROSE, CompressionConfig())
        assert "**" not in result
        assert "important" in result


class TestFullFile:
    def test_compress_file_reduces_size(self):
        content = """# My Agent

## Safety
- **NEVER** delete files without asking
- **NEVER** push to git without permission

## Personality
- Professional but approachable
- Curious and thorough
- Security-conscious

## References
- Path: `/Users/me/vault`
- Consult `reference.md` for details
- Check `rules.md` before acting
"""
        result = compress_file(content)
        assert result.compressed_bytes < result.original_bytes
        assert result.reduction_pct > 0
        # Safety content preserved
        assert "NEVER" in result.compressed
        assert "delete" in result.compressed

    def test_empty_file(self):
        result = compress_file("")
        assert result.compressed == ""
        assert result.reduction_pct == 0


class TestDeduplication:
    def test_finds_duplicates(self):
        files = {
            "soul.md": "Always use python venv for all Python projects in this workspace",
            "python.md": "Always use python venv for all Python projects in this workspace",
        }
        dupes = find_duplicates(files)
        assert len(dupes) > 0

    def test_no_false_positives_on_short(self):
        files = {
            "a.md": "short",
            "b.md": "short",
        }
        dupes = find_duplicates(files)
        assert len(dupes) == 0  # too short to count
