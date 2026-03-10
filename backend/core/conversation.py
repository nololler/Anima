import json
from typing import Optional, Dict, List
from backend.llm import create_adapter, Message
from backend.config import get_config
from backend.core.message_bus import get_bus
from backend.memory.context import ContextMessage
from backend.tools.registry import get_main_llm_tools, execute_tool
import uuid


class ConversationHandler:
    """Manages the Main LLM conversation loop."""

    def __init__(self, context_manager, persona_assembler, persona_state: dict):
        self.context = context_manager
        self.assembler = persona_assembler
        self.state = persona_state
        self._adapter = None

    def _get_adapter(self):
        if self._adapter is None:
            cfg = get_config()
            self._adapter = create_adapter(cfg.main_llm)
        return self._adapter

    def invalidate_adapter(self):
        self._adapter = None

    def _messages_for_llm(self) -> List[Message]:
        """Convert context to Message objects, filtering out tool-role messages
        which are already embedded as assistant messages by the Ollama adapter."""
        return [
            Message(role=m["role"], content=m["content"])
            for m in self.context.get_messages_for_llm()
            if m["role"] in ("user", "assistant", "system")
        ]

    async def handle_user_message(
        self,
        content: str,
        user_id: str,
        username: str,
        prompter_result: dict,
        user_profile: Optional[str] = None,
    ) -> str:
        bus = get_bus()

        # Add user message to context and emit to frontend
        user_msg = ContextMessage.create(role="user", content=content)
        self.context.add_message(user_msg)
        await bus.emit_chat_message("user", content, user_msg.id)

        # Build system prompt
        system = await self.assembler.build_main_prompt(
            kernel_report=prompter_result.get("kernel_report"),
            inner_thought=prompter_result.get("inner_thought"),
            injected_memories=prompter_result.get("injected_memories", []),
            user_profile=user_profile,
        )

        adapter = self._get_adapter()
        tools = get_main_llm_tools()
        full_response = ""
        msg_id = str(uuid.uuid4())

        try:
            response = await adapter.complete(
                messages=self._messages_for_llm(),
                tools=tools,
                system=system,
                max_tokens=1024,
            )

            # Handle tool calls — execute them, then do a follow-up completion
            if response.tool_calls:
                tool_context = []  # accumulate tool results as assistant context
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                    result = await execute_tool(tool_name, args)
                    await bus.emit_tool_call(tool_name, args, result)
                    tool_context.append(f"[{tool_name}] → {json.dumps(result)[:300]}")

                # Inject tool results as an assistant message so the LLM knows what happened
                if response.content:
                    tool_summary = response.content + "\n\n" + "\n".join(tool_context)
                else:
                    tool_summary = "\n".join(tool_context)

                tool_msg = ContextMessage.create(role="assistant", content=tool_summary)
                self.context.add_message(tool_msg)

                # Final response after tools
                response = await adapter.complete(
                    messages=self._messages_for_llm(),
                    system=system,
                    max_tokens=1024,
                )

            full_response = response.content or ""

            # Emit streaming simulation then the full message
            await bus.emit_chat_stream("", msg_id)
            chunk_size = 4
            for i in range(0, len(full_response), chunk_size):
                await bus.emit_chat_stream(full_response[i:i + chunk_size], msg_id)

        except Exception as e:
            full_response = f"[Error: {e}]"
            await bus.emit_error(str(e), source="main_llm")

        # Emit stream end and the final committed message
        await bus.emit_chat_stream_end(msg_id, full_response)

        # Add assistant response to context and emit as a permanent chat_message
        assistant_msg = ContextMessage.create(role="assistant", content=full_response)
        self.context.add_message(assistant_msg)
        await bus.emit_chat_message("assistant", full_response, assistant_msg.id)

        return full_response

    async def handle_idle_tick(self, prompter_result: dict, suggest_cull: bool = False):
        """Main LLM receives idle tick with prompter report, may use tools autonomously."""
        bus = get_bus()
        system = await self.assembler.build_main_prompt(
            kernel_report=prompter_result.get("kernel_report"),
            inner_thought=prompter_result.get("inner_thought"),
        )

        idle_prompt = "It is quiet. No one is speaking with you right now. You have a moment to yourself."
        if suggest_cull:
            idle_prompt += " Your memory is getting full — consider what to keep and what to let go."
        if prompter_result.get("suggest_initiate") and prompter_result.get("suggested_message"):
            idle_prompt += f" Your inner voice is nudging you: \"{prompter_result['suggested_message']}\""

        adapter = self._get_adapter()
        tools = get_main_llm_tools()

        try:
            response = await adapter.complete(
                messages=[Message(role="user", content=idle_prompt)],
                tools=tools,
                system=system,
                max_tokens=512,
            )

            if response.tool_calls:
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                    result = await execute_tool(tool_name, args)
                    await bus.emit_tool_call(tool_name, args, result)

            # Context culling during idle
            if suggest_cull:
                candidates = self.context.get_summary_candidates(n=8)
                if candidates:
                    ids = [m.id for m in candidates]
                    self.context.cull_messages(ids)
                    await bus.emit_context_cull(ids)

        except Exception as e:
            await bus.emit_error(f"Idle tick error: {e}", source="main_llm")
