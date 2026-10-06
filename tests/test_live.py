"""End-to-end checks: a real stdio session, and the real embedding model.

The model test downloads ~470 MB on first run. Skip it with
`pytest -m "not model"`.
"""

from __future__ import annotations

import json
import os
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from yuji import config
from yuji.embed import FastEmbedder, concept_text


async def test_stdio_session_lists_tools_and_saves_a_concept(home):
    # The subprocess gets an isolated YUJI_HOME and must not try to load the
    # model: use a fake via env so this stays fast and offline.
    env = {**os.environ, "YUJI_HOME": str(home), "YUJI_FAKE_EMBEDDER": "1"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "yuji.cli"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            assert {"find_similar", "create_concept", "clear_index"} <= tools

            result = await session.call_tool(
                "create_concept", {"label": "麻烦 máfan", "gloss": "troublesome"}
            )
            body = result.structured_content or json.loads(result.content[0].text)
            assert body["status"] == "created"

            got = await session.call_tool("get_concept", {"concept_id": body["concept_id"]})
            body = got.structured_content or json.loads(got.content[0].text)
            assert body["label"] == "麻烦 máfan"


@pytest.mark.model
def test_real_model_keeps_huijia_and_qujia_apart_but_close():
    emb = FastEmbedder()
    home = emb.embed(concept_text("回家 huíjiā", "to return home", "word"))
    go = emb.embed(concept_text("去家 qùjiā", "to go to (someone's) home", "word"))
    apple = emb.embed(concept_text("苹果 píngguǒ", "apple", "word"))
    near = float(home @ go)
    far = float(home @ apple)
    assert near > far
    assert near > config.SIMILAR_THRESHOLD, near  # close enough that create_concept should stop and ask
    assert far < config.SIMILAR_THRESHOLD, far  # far enough that it saves straight away
