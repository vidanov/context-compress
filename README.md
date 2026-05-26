# context-compress

Token-efficient compression for AI agent instruction files. Reduces context window usage by 40-50% while preserving behavioral compliance.

Works with: **Kiro CLI**, **Claude Code**, **Cursor**, **Windsurf**, **Gemini CLI**

📖 **[Interactive demo & article](https://vidanov.github.io/context-compress/)** | 📝 **[Full article on DEV](https://dev.to/vidanov/i-ab-tested-compressed-agent-instructions-and-found-the-breaking-point-3h7k)**

## The Problem

AI coding agents load instruction files (CLAUDE.md, steering, skills) into context on every session. A typical power-user setup consumes 15-20K tokens before the first prompt. Most of that is formatting, redundancy, and prose the model doesn't need.

## What Makes This Different

Other approaches (Token Trim, caveman prompting) apply uniform compression and claim "zero behavior change" without testing. We found that's not true — **aggressive compression breaks behavioral rules** like safety compliance and preference adherence.

This tool uses **semantic-aware compression**: different aggressiveness per content type, validated by automated A/B testing.

## Compression Strategy

| Content Type | Strategy | Safe Reduction |
|---|---|---|
| Paths, references, lists | Maximum compression | 60-70% |
| Personality, style rules | Heavy compression | 50-60% |
| Safety rules, preferences | Light compression (formatting only) | 20-30% |
| Code examples | No compression | 0% |

## Installation

```bash
pip install context-compress
```

Or clone and use directly:

```bash
git clone https://github.com/vidanov/context-compress.git
cd context-compress
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### LLM compression (recommended, best results)

```bash
# Single file
context-compress llm CLAUDE.md -o CLAUDE.compressed.md

# Entire directory
context-compress llm .kiro/steering/ -o .kiro/steering-compressed/
```

Requires `kiro-cli` installed and configured.

### Regex compression (fast, offline, no LLM needed)

```bash
# Single file
context-compress compress CLAUDE.md -o CLAUDE.compressed.md

# Directory
context-compress compress-dir .kiro/steering/ -o .kiro/steering-compressed/
```

### Find duplicates across files

```bash
context-compress dedup .kiro/steering/
```

### Analyze token usage

```bash
context-compress stats .kiro/steering/
```

## Integration

### Kiro CLI (agentSpawn hook)

```json
{
  "hooks": {
    "agentSpawn": [
      {
        "command": "context-compress compress-dir ~/.kiro/steering/ -o ~/.kiro/steering-compressed/ --quiet",
        "description": "Compress steering files on session start"
      }
    ]
  }
}
```

Then point your agent resources to the compressed directory.

### Claude Code (pre-session)

Add to your shell profile or run before sessions:

```bash
context-compress compress CLAUDE.md -o .claude/CLAUDE.compressed.md
```

### CI/Git Hook

```bash
# .git/hooks/pre-commit
context-compress compress-dir docs/agent-instructions/ -o .kiro/steering/
```

## Configuration

Create `compress.yaml` to customize rules per file:

```yaml
defaults:
  strip_markdown: true
  remove_blanks: true
  collapse_lists: true
  deduplicate: true

overrides:
  "RULES.md":
    preserve_safety_rules: true
    compression_level: light
  "cli-tools.md":
    preserve_code_blocks: true
    compress_prose_only: true
  "writing-lab.md":
    compression_level: medium
```

## How It Works

1. **Classify** each section by content type (safety, reference, personality, code, procedure)
2. **Apply** type-appropriate compression rules
3. **Deduplicate** across files (finds repeated instructions)
4. **Validate** output preserves key behavioral markers
5. **Report** token savings and any flagged risks

## Results

Tested on a real 61KB agent context stack (SOUL + 10 steering files + 3 skills):

### Regex-based compression (fast, offline)

Best for heavily-formatted, prose-heavy files. Limited on already-lean files.

| File type | Typical reduction |
|---|---|
| Prose-heavy (errors, guides) | 40-70% |
| Already-lean (steering) | 2-7% |

### LLM-based compression (semantic, uses kiro-cli)

Uses an LLM to rewrite instructions in compressed form while preserving meaning.

| File | Original | Compressed | Reduction |
|---|---|---|---|
| obsidian-integration.md | 5,634 | 4,287 | 24% |
| RULES.md | 4,265 | 3,440 | 19% |
| linkedin-drafter.md | 6,724 | 5,396 | 20% |
| writing-lab.md | 5,572 | 4,376 | 21% |
| cli-tools.md | 5,448 | 3,603 | 34% |
| **Total** | **27,643** | **21,102** | **24%** |

### Deduplication (structural)

Finds repeated content across files. In our test setup:
- `writing-lab.md` (steering) was 90% duplicate of `writing-editing-lab/SKILL.md` (skill) → 5.5KB wasted every session
- Safety rules duplicated across SOUL.md and RULES.md → 0.5KB
- Obsidian paths in SOUL.md and obsidian-integration.md → 0.8KB

### Combined approach

| Strategy | Savings |
|---|---|
| LLM compression | ~24% |
| Deduplication | ~18% |
| **Combined** | **~37%** |

On a 61KB context stack: **~22KB saved → ~6,000 fewer tokens per session**

## License

MIT
