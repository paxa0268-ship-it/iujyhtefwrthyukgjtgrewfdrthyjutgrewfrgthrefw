"""Anthropic (Claude) bilan ishlash."""
import logging

from anthropic import AsyncAnthropic

import prompts

log = logging.getLogger("llm")

DECIDE_TOOL = {
    "name": "decide_reply",
    "description": "Report your analysis of the situation and the decision about replying on the owner's behalf.",
    "input_schema": {
        "type": "object",
        "properties": {
            "analysis": {"type": "string", "description": "1-2 sentences in Uzbek for the owner: who writes, what they want, mood, context."},
            "intent": {"type": "string", "enum": ["salomlashish", "savol", "iltimos", "reja", "shoshilinch", "hissiy", "spam", "boshqa"]},
            "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
            "should_reply": {"type": "boolean"},
            "reply": {"type": "string", "description": "The exact message to send as the owner. Empty if should_reply is false."},
            "notify_owner": {"type": "boolean", "description": "True if the owner personally should look at this."},
            "notify_reason": {"type": "string", "description": "Short Uzbek reason when notify_owner is true or you hold the reply."},
            "relation_guess": {"type": "string", "description": "Best guess of relationship (do_st, qarindosh, hamkasb, mijoz, notanish...). Optional."},
            "note_update": {"type": "string", "description": "Durable observation about this person. Optional."},
        },
        "required": ["analysis", "intent", "urgency", "should_reply", "reply", "notify_owner"],
    },
}

SAVE_FACTS_TOOL = {
    "name": "save_facts",
    "description": "Save extracted facts about the owner.",
    "input_schema": {
        "type": "object",
        "properties": {"facts": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "content": {"type": "string"},
                "visibility": {"type": "string", "enum": ["public", "private"]},
                "replaces_id": {"type": "integer", "description": "id of an existing fact this one replaces"},
            },
            "required": ["category", "content", "visibility"],
        }}},
        "required": ["facts"],
    },
}

OWNER_TOOLS = [
    {
        "name": "remember_facts",
        "description": "Save one or more new facts about the owner (or update existing ones via replaces_id).",
        "input_schema": SAVE_FACTS_TOOL["input_schema"],
    },
    {
        "name": "forget_fact",
        "description": "Delete a stored fact by id.",
        "input_schema": {"type": "object", "properties": {"fact_id": {"type": "integer"}}, "required": ["fact_id"]},
    },
    {
        "name": "set_fact_visibility",
        "description": "Change whether a fact may be used when answering other people.",
        "input_schema": {"type": "object", "properties": {
            "fact_id": {"type": "integer"}, "visibility": {"type": "string", "enum": ["public", "private"]}},
            "required": ["fact_id", "visibility"]},
    },
    {
        "name": "update_contact",
        "description": "Set what a contact is to the owner, add notes, or mute/unmute auto-replies for that contact. Use chat_id from the CONTACTS list.",
        "input_schema": {"type": "object", "properties": {
            "chat_id": {"type": "integer"}, "relation": {"type": "string"},
            "notes": {"type": "string"}, "muted": {"type": "boolean"}}, "required": ["chat_id"]},
    },
    {
        "name": "send_to_contact",
        "description": "Send a message to a contact as the owner. ONLY when the owner explicitly asks to send something. Write the final text in the owner's style.",
        "input_schema": {"type": "object", "properties": {
            "chat_id": {"type": "integer"}, "text": {"type": "string"}}, "required": ["chat_id", "text"]},
    },
]


def _sys(blocks):
    out = []
    for text, cache in blocks:
        b = {"type": "text", "text": text}
        if cache:
            b["cache_control"] = {"type": "ephemeral"}
        out.append(b)
    return out


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()


class LLM:
    def __init__(self, api_key, model, fast_model):
        self.client = AsyncAnthropic(api_key=api_key, max_retries=4, timeout=90)
        self.model = model
        self.fast_model = fast_model

    async def decide_reply(self, blocks, user_content) -> dict:
        resp = await self.client.messages.create(
            model=self.model, max_tokens=1000, system=_sys(blocks),
            messages=[{"role": "user", "content": user_content}],
            tools=[DECIDE_TOOL], tool_choice={"type": "tool", "name": "decide_reply"},
        )
        for b in resp.content:
            if b.type == "tool_use":
                d = dict(b.input)
                d.setdefault("analysis", "")
                d.setdefault("reply", "")
                d.setdefault("should_reply", False)
                d.setdefault("notify_owner", False)
                d.setdefault("urgency", "low")
                return d
        raise RuntimeError("Model decide_reply chaqirmadi")

    async def compose(self, blocks, user_content) -> str:
        resp = await self.client.messages.create(
            model=self.model, max_tokens=600, system=_sys(blocks),
            messages=[{"role": "user", "content": user_content}],
        )
        return _text(resp)

    async def owner_agent(self, blocks, messages, executor, max_turns=6) -> str:
        msgs = list(messages)
        for _ in range(max_turns):
            resp = await self.client.messages.create(
                model=self.model, max_tokens=1500, system=_sys(blocks),
                messages=msgs, tools=OWNER_TOOLS,
            )
            if resp.stop_reason != "tool_use":
                return _text(resp) or "Tayyor ✅"
            msgs.append({"role": "assistant", "content": resp.content})
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    try:
                        out = await executor(b.name, dict(b.input))
                    except Exception as e:  # noqa: BLE001
                        log.exception("tool xatosi")
                        out = f"Xato: {e}"
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": str(out)})
            msgs.append({"role": "user", "content": results})
        return "Juda ko'p qadam bo'ldi, iltimos qayta urinib ko'ring."

    async def extract_facts(self, existing: str, context: str, text: str, fast=False) -> list:
        resp = await self.client.messages.create(
            model=self.fast_model if fast else self.model, max_tokens=3000,
            system=_sys([(prompts.EXTRACT_RULES, False)]),
            messages=[{"role": "user", "content":
                       f"EXISTING FACTS:\n{existing or '(none)'}\n\nCONTEXT: {context}\n\nTEXT:\n{text}"}],
            tools=[SAVE_FACTS_TOOL], tool_choice={"type": "tool", "name": "save_facts"},
        )
        for b in resp.content:
            if b.type == "tool_use":
                return list(b.input.get("facts", []))
        return []

    async def style_profile(self, samples: list, old: str = "") -> str:
        body = "\n".join("- " + s.replace("\n", " ⏎ ") for s in samples)
        extra = f"\n\nPrevious guide (refine, do not just repeat):\n{old}" if old else ""
        resp = await self.client.messages.create(
            model=self.model, max_tokens=700, system=_sys([(prompts.STYLE_PROFILE_RULES, False)]),
            messages=[{"role": "user", "content": f"VERBATIM MESSAGES BY THE PERSON:\n{body}{extra}"}],
        )
        return _text(resp)
