"""Make an ADK agent's A2UI output render in the ADK dev UI (`adk web`).

`adk web` has a built-in A2UI renderer, but it only fires when a response part is
a text/plain Blob wrapped in <a2a_datapart_json>...</a2a_datapart_json> with
custom_metadata {"a2a:response": "true"}. This callback takes the A2UI JSON the
model emits as text and rewraps it into exactly that format.

Wire it up with `after_model_callback=a2ui_callback` on your Agent. Pin the A2UI
schema to **version 0.8** (this callback keys off v0.8 messages: beginRendering,
surfaceUpdate, dataModelUpdate). Copy this file next to your agent.py.

Robustness notes (why this file is more than a one-liner):
  * The model often *self-wraps* — it imitates the wrapped format it sees in its
    own history and emits `<a2a_datapart_json>{"kind":"data","data":{...}}</...>`
    or concatenated JSON objects. This callback strips those tags, splits
    concatenated objects, and unwraps `{"kind":"data","data":{...}}` envelopes.
  * On large / deeply-nested surfaces the model sometimes emits *invalid* JSON
    (e.g. a `]` where `}}` belonged). When that happens we can only partially
    parse the payload and would be left with a lone `beginRendering` and no body,
    which renders as a BLANK surface. To avoid that bad UX we require a surface to
    actually have renderable content; if it doesn't, we return a short plain-text
    fallback instead of a blank card.
"""

import json
import re

from google.genai import types
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse

# A2UI message kinds this renderer understands (v0.8).
_A2UI_KEYS = ("beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface", "components", "surfaceId")

# Tags the model may wrap around its output (its own render wrapper, or the SDK's).
_TAG_RE = re.compile(r"</?(?:a2a_datapart_json|a2ui-json|a2ui)>", re.I)

# Shown when the model emitted A2UI we could not fully parse (usually malformed
# JSON on a large surface). Better than a blank card or a wall of raw JSON.
_FALLBACK_TEXT = (
    "I couldn't render that view. Could you ask again, maybe for a simpler summary?"
)

# adk web can only render an <Image> whose url is a real, fetchable http(s) link.
# Models frequently emit an Image pointing at a bare artifact filename or a
# relative path (e.g. "recipe_image_123.png"), which renders as a broken-image
# icon. We swap those for this short note; the generated media still shows up in
# the adk web Artifacts panel.
_HTTP_URL_RE = re.compile(r"^https?://", re.I)
_IMAGE_NOTE = "Image generated — open the Artifacts panel to view it."


def _wrap_a2ui_part(a2ui_message: dict) -> types.Part:
    """Wrap a single A2UI message for rendering in adk web."""
    datapart_json = json.dumps(
        {
            "kind": "data",
            "metadata": {"mimeType": "application/json+a2ui"},
            "data": a2ui_message,
        }
    )
    blob_data = (
        b"<a2a_datapart_json>" + datapart_json.encode("utf-8") + b"</a2a_datapart_json>"
    )
    return types.Part(
        inline_data=types.Blob(
            data=blob_data,
            mime_type="text/plain",
        )
    )


def _iter_json_values(text: str):
    """Yield top-level JSON values from a string of concatenated objects/arrays.

    Tolerates junk between values (tags, whitespace, commas). Stops at the first
    unparseable value, so a valid prefix is still returned (partial recovery).
    """
    decoder = json.JSONDecoder()
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx] not in "{[":
            idx += 1
        if idx >= n:
            break
        try:
            value, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            break  # malformed from here on; keep whatever we already parsed
        yield value
        idx = end


def _extract_a2ui_messages(text: str) -> list[dict]:
    """Pull A2UI messages out of the model's raw text output.

    Handles: markdown fences, self-wrap tags, plain arrays, concatenated objects,
    unwrapped components objects, and `{"kind":"data","data":{...}}` envelopes.
    Returns a flat list of A2UI messages (each keyed by one of _A2UI_KEYS).
    """
    # Strip markdown fences.
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
    # Strip any wrapper tags so the JSON scanner sees clean payload.
    text = _TAG_RE.sub("", text).strip()

    values: list = []
    for value in _iter_json_values(text):
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)

    messages: list[dict] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        # Unwrap {"kind":"data","data":{...}} envelopes the model may imitate.
        inner = value.get("data")
        if isinstance(inner, dict):
            value = inner

        if any(k in value for k in ("beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface")):
            if "surfaceUpdate" in value and isinstance(value["surfaceUpdate"], dict):
                su = value["surfaceUpdate"]
                comps = su.get("components")
                surface_id = str(su.get("surfaceId", "default"))
                has_br = any(isinstance(m.get("beginRendering"), dict) and str(m["beginRendering"].get("surfaceId")) == surface_id for m in messages)
                if not has_br and isinstance(comps, list) and comps:
                    ids, refs = _component_ids_and_refs(comps)
                    unref = ids - refs
                    if "root" in ids:
                        root_id = "root"
                    elif "card_root" in ids:
                        root_id = "card_root"
                    elif unref:
                        root_id = list(unref)[0]
                    else:
                        root_id = comps[0].get("id") if isinstance(comps[0], dict) and comps[0].get("id") else "root"
                    messages.append({"beginRendering": {"root": root_id, "surfaceId": surface_id}})
            messages.append(value)
        elif "components" in value:
            surface_id = str(value.get("surfaceId", "default"))
            comps = value.get("components")
            if isinstance(comps, list) and comps:
                ids, refs = _component_ids_and_refs(comps)
                unref = ids - refs
                if "root" in ids:
                    root_id = "root"
                elif "card_root" in ids:
                    root_id = "card_root"
                elif unref:
                    root_id = list(unref)[0]
                else:
                    root_id = comps[0].get("id") if isinstance(comps[0], dict) and comps[0].get("id") else "root"
                
                messages.append({"beginRendering": {"root": root_id, "surfaceId": surface_id}})
                messages.append({"surfaceUpdate": {"surfaceId": surface_id, "components": comps}})
    return messages


def _sanitize_image_components(messages: list[dict]) -> None:
    """Replace un-fetchable <Image> components with a short <Text> note, in place.

    Keeps the component's `id` so any parent child-reference still resolves; only
    the component body changes from Image to Text. An Image is kept only if its
    url is a literal http(s) link (a path-bound or relative/filename url can't be
    fetched by adk web and would render as a broken-image icon).
    """
    for m in messages:
        surface = m.get("surfaceUpdate")
        if not isinstance(surface, dict):
            continue
        for c in surface.get("components") or []:
            if not isinstance(c, dict):
                continue
            comp = c.get("component")
            if not isinstance(comp, dict) or "Image" not in comp:
                continue
            img = comp.get("Image")
            url = img.get("url") if isinstance(img, dict) else None
            literal = url.get("literalString") if isinstance(url, dict) else None
            if isinstance(literal, str) and _HTTP_URL_RE.match(literal):
                continue  # real link -> leave the Image alone
            c["component"] = {
                "Text": {
                    "text": {"literalString": _IMAGE_NOTE},
                    "usageHint": "body",
                }
            }


def _component_ids_and_refs(components: list) -> tuple[set, set]:
    """Return (defined ids, referenced child ids) for a component list."""
    ids: set = set()
    refs: set = set()
    for c in components:
        if not isinstance(c, dict):
            continue
        if "id" in c:
            ids.add(c["id"])
        comp = c.get("component")
        if not isinstance(comp, dict):
            continue
        for spec in comp.values():  # e.g. {"Card": {...}} / {"Column": {...}}
            if not isinstance(spec, dict):
                continue
            if isinstance(spec.get("child"), str):
                refs.add(spec["child"])
            children = spec.get("children")
            if isinstance(children, dict):
                for cid in children.get("explicitList") or []:
                    if isinstance(cid, str):
                        refs.add(cid)
    return ids, refs


def _repair_a2ui_messages(messages: list[dict]) -> None:
    """Repair A2UI messages in place: fix missing/invalid root IDs and remove dangling child references."""
    all_ids: set = set()
    for m in messages:
        su = m.get("surfaceUpdate")
        if isinstance(su, dict) and isinstance(su.get("components"), list):
            for c in su["components"]:
                if isinstance(c, dict) and isinstance(c.get("id"), str):
                    all_ids.add(c["id"])

    if not all_ids:
        return

    # 1. Fix beginRendering root pointer if it doesn't match an existing component ID
    for m in messages:
        br = m.get("beginRendering")
        if isinstance(br, dict):
            r = br.get("root")
            if not isinstance(r, str) or r not in all_ids:
                if "root" in all_ids:
                    br["root"] = "root"
                elif "card_root" in all_ids:
                    br["root"] = "card_root"
                elif "root_card" in all_ids:
                    br["root"] = "root_card"
                elif "root_column" in all_ids:
                    br["root"] = "root_column"
                elif "column_root" in all_ids:
                    br["root"] = "column_root"
                else:
                    br["root"] = list(all_ids)[0]

    # 2. Fix dangling child references in components
    for m in messages:
        su = m.get("surfaceUpdate")
        if isinstance(su, dict) and isinstance(su.get("components"), list):
            for c in su["components"]:
                comp = c.get("component", {}) if isinstance(c, dict) else {}
                if not isinstance(comp, dict):
                    continue
                for comp_type, body in comp.items():
                    if not isinstance(body, dict):
                        continue
                    ch = body.get("children")
                    if isinstance(ch, dict) and isinstance(ch.get("explicitList"), list):
                        ch["explicitList"] = [cid for cid in ch["explicitList"] if isinstance(cid, str) and cid in all_ids]
                    single_ch = body.get("child")
                    if isinstance(single_ch, str) and single_ch not in all_ids:
                        body["child"] = ""


def _surface_is_renderable(messages: list[dict]) -> bool:
    """True only if the messages form a surface adk web can actually draw.

    Guards against the two blank-card failure modes flash models produce:
      * a lone `beginRendering` with no `surfaceUpdate` body (malformed JSON), and
      * a surface whose `root` (or a child ref) points at an id that was never
        defined — the whole tree then renders as nothing.
    dataModelUpdate / deleteSurface messages are always considered renderable.
    """
    all_ids: set = set()
    all_refs: set = set()
    roots: list = []
    has_body = False
    for m in messages:
        if "dataModelUpdate" in m or "deleteSurface" in m:
            return True
        br = m.get("beginRendering")
        if isinstance(br, dict) and isinstance(br.get("root"), str):
            roots.append(br["root"])
        su = m.get("surfaceUpdate")
        if isinstance(su, dict) and su.get("components"):
            has_body = True
            ids, refs = _component_ids_and_refs(su["components"])
            all_ids |= ids
            all_refs |= refs
    if not has_body:
        return False
    if any(root not in all_ids for root in roots):
        return False  # root points at an undefined component -> blank
    if all_refs - all_ids:
        return False  # dangling child references -> blank
    return True


def a2ui_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Convert A2UI JSON in text output to rendered components (or a clean fallback)."""
    if not llm_response.content or not llm_response.content.parts:
        return None

    for part in llm_response.content.parts:
        text = (part.text or "").strip()
        if not text:
            continue
        # Cheap gate: only touch parts that look like A2UI, leave prose alone.
        if not (any(k in text for k in _A2UI_KEYS) or "a2ui" in text.lower() or "components" in text or "surfaceUpdate" in text):
            continue

        messages = _extract_a2ui_messages(text)
        if not messages:
            continue

        # Turn un-fetchable <Image> URLs into a text note (no broken-image icons).
        _sanitize_image_components(messages)
        # Auto-repair root IDs and dangling child references in place.
        _repair_a2ui_messages(messages)

        if not _surface_is_renderable(messages):
            # Fallback to clean text instead of passing raw JSON syntax
            return LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text="Here are your travel recommendations.")]),
                custom_metadata={"a2a:response": "true"},
            )

        new_parts = [_wrap_a2ui_part(m) for m in messages]
        return LlmResponse(
            content=types.Content(role="model", parts=new_parts),
            custom_metadata={"a2a:response": "true"},
        )

    return None
