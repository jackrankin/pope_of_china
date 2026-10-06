# 语迹 (yuji)

A local MCP server that remembers the Chinese words and language points you've
been taught, by stable concept ID. The chat you already use (Cursor, or any
other MCP client) is the interface. There is no website and no separate bot.

Each concept gets its own ID. The characters are a label, not a key: 回家 and
去家 are two rows. Embeddings exist only to surface neighbors. The server never
merges on a similarity score; closeness only forces the agent to look at the
neighbors and pick an existing ID or mint a new one.

## Setup

```sh
cd /Users/jjrankin/chinese/pope_of_china
uv sync
```

Add to Cursor's MCP config (`~/.cursor/mcp.json`, or this repo's
`.cursor/mcp.json`, which is already set up):

```json
{
  "mcpServers": {
    "yuji": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/jjrankin/chinese/pope_of_china", "yuji"]
    }
  }
}
```

Cursor launches the server when a chat first calls a tool. You never need to
start it yourself; `uv run yuji` in a terminal only speaks MCP on stdin.

The index lives at `~/.yuji/yuji.db`. The first similarity call downloads the
multilingual embedding model (~240 MB) into `~/.yuji/models`.

## Commands

```sh
uv run yuji status   # where the index is and what it holds
uv run yuji clear    # delete every concept and deck; the model cache stays
```

In chat, "clear the index" calls `clear_index` with `confirm=true`. Without
that flag the tool deletes nothing.

## What it stores

SQLite holds each concept: `id`, `kind`, `label` (characters + pinyin),
`gloss`, `notes`, links to the slides that taught it, and relations to other
concepts. One embedding per concept ID sits alongside, used only to find
neighbors.

`kind` keeps vocabulary and grammar apart:

- `word` — a vocabulary item (default when added from chat)
- `language_point` — a grammar topic such as 把字句
- `other` — anything else

`search` can be limited to one kind. `find_similar` looks across all kinds and
reports each neighbor's kind.

## Tools

| Tool | Writes? | What it does |
| --- | --- | --- |
| `read_slides(path, title)` | deck text only | Stores a PPTX / PDF / txt / md deck's slide text. Never creates concepts. |
| `find_similar(description)` | no | Embeds the description, returns closest concept IDs with labels, glosses, kinds, scores. |
| `create_concept(label, gloss, kind, notes, deck_id, slide_numbers, confirm_new)` | yes | Mints an ID and embeds it. If a neighbor scores at or above the threshold, returns `needs_confirmation` and writes nothing unless `confirm_new=true`. |
| `attach(concept_id, deck_id, slide_numbers)` | yes | Links an existing concept to slides. |
| `relate(id_a, id_b, note)` | yes | Records that two concepts are related and still distinct. |
| `search(query, kind, limit)` | no | Text search over labels, glosses, notes. |
| `get_concept(concept_id)` | no | Full record with slides and relations. |
| `list_decks()` | no | Decks that have been read. |
| `clear_index(confirm)` | yes | Wipes everything. Requires `confirm=true`. |

A new deck goes: `read_slides`, propose concepts, `find_similar` for each,
then `attach` or `create_concept`. A word typed in chat takes the same path,
starting at `find_similar`.

With the bundled model, 回家 against 去家 scores about 0.78 and a reworded 回家
scores about 0.90; both stop and ask. 回家 against 苹果 scores about 0.26 and is
saved straight away. The threshold is 0.75; override with
`YUJI_SIMILAR_THRESHOLD`.

## Quizzing

Ask in chat. The agent reads from `search` and `get_concept`, so questions come
from what is actually stored:

- "Quiz me on five vocabulary words. Show the English, I'll answer in Chinese."
- "Ask me about my language points one at a time. Don't show the answer until I try."
- "Give me a sentence to finish using a grammar point I already know."

## Development

```sh
uv sync --all-groups
uv run pytest -m "not model"   # fast, offline
uv run pytest                  # also runs the real-model similarity check
```

Environment: `YUJI_HOME` moves the index directory; `YUJI_EMBED_MODEL` picks
another fastembed model; `YUJI_FAKE_EMBEDDER=1` swaps in a hash embedder for
offline tests.
