# 语迹 (yuji)

A local MCP server that remembers the Chinese words and language points you learn,
each under a stable concept ID. The chat you already use (Cursor, or any MCP client)
is the interface; this server is the memory.

- SQLite stores each concept: ID, kind, label, gloss, notes, and links to the
  slides that taught it. 回家 and 去家 are two rows because they are two concepts.
  The characters are a label, not the key.
- One embedding per concept ID, used only to find neighbors. The server never merges
  on a score. Closeness makes the agent look at the neighbors and choose an existing
  ID or mint a new one.
- The embedding model (`paraphrase-multilingual-MiniLM-L12-v2`, ONNX, ~240 MB)
  runs inside the server and is downloaded on first use.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/).

```sh
cd /Users/jjrankin/chinese/pope_of_china
uv sync
```

Cursor config (already in `.cursor/mcp.json` for this checkout; copy to
`~/.cursor/mcp.json` to use it from any project):

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

Cursor launches the server when a chat first uses a tool. Running `uv run yuji`
in a terminal only speaks MCP on stdin, so there is nothing to type there.

## Commands

```sh
uv run yuji          # serve over stdio (what Cursor runs)
uv run yuji status   # where the index is and what it holds
uv run yuji clear    # delete every concept and deck; keep the model cache
```

The index lives at `~/.yuji/yuji.db`; models at `~/.yuji/models`. Override the
directory with `YUJI_HOME`, the threshold with `YUJI_SIMILAR_THRESHOLD` (default 0.75).

## Tools

| Tool | Writes? | What it does |
|---|---|---|
| `read_slides(path, title)` | deck only | Stores the per-slide text of a `.pptx`, `.pdf`, `.txt`, or `.md` and returns it. Never creates concepts. |
| `find_similar(description, limit)` | no | Embeds a description, returns the closest concept IDs with label, gloss, kind, score. |
| `create_concept(label, gloss, kind, notes, deck_id, slide_numbers, confirm_new)` | yes | Mints an ID. Refuses with `needs_confirmation` if a neighbor scores at or above the threshold or has the same characters, unless `confirm_new=true`. |
| `attach(concept_id, deck_id, slide_numbers)` | yes | Links an existing concept to slides. |
| `relate(id_a, id_b, note)` | yes | Records two concepts as related and still distinct. |
| `search(query, kind, limit)` | no | Text search over labels/glosses/notes; `kind` restricts to `word`, `language_point`, or `other`. |
| `get_concept(concept_id)` | no | Full record with linked slides and relations. |
| `list_decks()` | no | Decks that have been read. |
| `clear_index(confirm)` | yes | Wipes everything. Does nothing without `confirm=true`. |

A new deck goes: `read_slides`, propose concepts, `find_similar` for each, then
`attach` or `create_concept`. A word typed in chat takes the same path from `find_similar`.

## Things to say in chat

- "Ingest ~/Desktop/lesson3.pptx."
- "Add 麻烦 máfan, troublesome."
- "Show my language points."
- "Quiz me on five words. Show the English, I'll answer in Chinese."
- "Clear the index."

## Tests

```sh
uv run pytest                 # all 24, including a live stdio session and the real model
uv run pytest -m "not model"  # offline only
```
