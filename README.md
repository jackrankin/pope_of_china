# 语迹 (yuji)

A Chinese word list you fill in by pasting words into a chat, and a quiz page
that shows you a character and asks for the pinyin.

Each entry is three fields:

```
我   wo3   I, me
```

The characters are the key, so the same word can't be stored twice. Pinyin is
stored as tone numbers (`ni3 hao3`, `nv3` for nǚ).

## Setup

Requires [uv](https://docs.astral.sh/uv/). Register the MCP server once, with
Cursor (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "yuji": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/pope_of_china", "yuji"]
    }
  }
}
```

or with Claude Code:

```bash
claude mcp add --scope user yuji -- uv run --directory /path/to/pope_of_china yuji
```

## Use

Paste words into a chat: "add 我 你 他 好 谢谢". The agent fills in pinyin
and meaning and calls `add_words`. Re-adding a word updates it and the agent
is told what the old values were.

Then run the quiz:

```bash
uv run yuji web          # http://127.0.0.1:8765
```

Type the pinyin and press Enter. Tone numbers (`wo3`) or tone marks (`wǒ`)
both work; spacing doesn't matter. Wrong answers come back a few cards later.

Other commands:

```bash
uv run yuji list         # print every word
uv run yuji clear        # delete every word
```

Data lives in `~/.yuji/yuji.db` (override with `YUJI_HOME`).

## MCP tools

| tool | what it does |
| --- | --- |
| `add_words(words)` | bulk add/update; each result is `added`, `updated` (with `was`), or `unchanged` |
| `list_words(query, limit)` | list or search by characters, pinyin, or meaning |
| `remove_word(hanzi)` | delete one word |
| `clear_words(confirm)` | delete everything |

## Development

```bash
uv run pytest
```
