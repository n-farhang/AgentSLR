import asyncio
import datetime as dt
import json
from pathlib import Path

from openai import AsyncOpenAI, OpenAI


class OpenAIWrapper:
    def __init__(
        self,
        model_name,
        base_url,
        api_key="6767",
        save_traces=False,
        trace_dir=None,
        reasoning_effort="high",
        max_completion_tokens=None,
        async_flag=False,
    ):
        self.model_name = model_name
        self.save_traces = save_traces
        self.trace_dir = trace_dir
        self._trace_counter = 0
        self.reasoning_effort = reasoning_effort
        self.max_completion_tokens = max_completion_tokens
        self.async_flag = async_flag
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.async_client = AsyncOpenAI(base_url=base_url, api_key=api_key) if async_flag else None
        self.extra_body = {"thinking": {"type": "enabled"}} if "gpt" not in model_name.lower() else {}

        if self.save_traces and trace_dir:
            Path(self.trace_dir).mkdir(parents=True, exist_ok=True)
            self.trace_file = Path(self.trace_dir) / "reasoning_traces.jsonl"

    def _save_trace(self, trace_data):
        if not self.save_traces or not self.trace_dir:
            return
        with open(self.trace_file, "a") as handle:
            handle.write(json.dumps(trace_data) + "\n")

    def _extract_text(self, resp):
        text_response = ""
        if getattr(resp, "choices", None):
            msg = resp.choices[0].message
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                text_response = content.strip()
            elif isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif hasattr(part, "type") and getattr(part, "type", None) == "text" and hasattr(part, "text"):
                        parts.append(getattr(part, "text", ""))
                text_response = "".join(parts).strip()
        return text_response

    def _build_messages(self, prompt, system_prompt=None):
        system_role = "developer" if (self.model_name.startswith("o") or self.model_name.startswith("gpt-5")) else "system"
        if system_prompt:
            return [
                {"role": system_role, "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        return [{"role": "user", "content": prompt}]

    async def _one_chat(
        self,
        prompt,
        system_prompt=None,
        reasoning_effort=None,
        trace_id=None,
        max_completion_tokens=None,
    ):
        reasoning_effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort
        max_completion_tokens = (
            max_completion_tokens if max_completion_tokens is not None else self.max_completion_tokens
        )
        input_data = self._build_messages(prompt, system_prompt=system_prompt)

        trace_data = None
        if self.save_traces:
            self._trace_counter += 1
            trace_data = {
                "trace_id": trace_id or f"trace_{self._trace_counter}",
                "timestamp": dt.datetime.now().isoformat(),
                "model": self.model_name,
                "reasoning_effort": reasoning_effort,
                "max_completion_tokens": max_completion_tokens,
                "input": input_data,
                "response": None,
                "extracted_text": None,
                "error": None,
            }
            if self.extra_body:
                trace_data["extra_body"] = self.extra_body

        try:
            request_params = {"model": self.model_name, "messages": input_data}
            if "gpt" not in self.model_name.lower():
                request_params["reasoning_effort"] = reasoning_effort
            else:
                request_params["reasoning_effort"] = reasoning_effort
            if max_completion_tokens is not None:
                request_params["max_completion_tokens"] = max_completion_tokens
            if self.extra_body:
                request_params["extra_body"] = self.extra_body

            if self.async_flag:
                resp = await self.async_client.chat.completions.create(**request_params)
            else:
                resp = self.client.chat.completions.create(**request_params)

            if trace_data is not None:
                trace_data["response"] = resp.model_dump()

            text_response = self._extract_text(resp)

            if trace_data is not None:
                trace_data["extracted_text"] = text_response
                self._save_trace(trace_data)

            return text_response
        except Exception as exc:
            if trace_data is not None:
                trace_data["error"] = str(exc)
                trace_data["extracted_text"] = f"ERROR: {type(exc).__name__}: {exc}"
                self._save_trace(trace_data)
            raise

    async def _many_chat(
        self,
        prompts,
        system_prompt=None,
        concurrency=16,
        reasoning_effort=None,
        trace_ids=None,
        max_completion_tokens=None,
    ):
        sem = asyncio.Semaphore(concurrency)

        async def guarded(prompt, idx):
            async with sem:
                trace_id = trace_ids[idx] if trace_ids else None
                return await self._one_chat(
                    prompt,
                    system_prompt=system_prompt,
                    reasoning_effort=reasoning_effort,
                    trace_id=trace_id,
                    max_completion_tokens=max_completion_tokens,
                )

        return await asyncio.gather(*(guarded(prompt, idx) for idx, prompt in enumerate(prompts)))

    def _many_chat_sync(
        self,
        prompts,
        system_prompt=None,
        reasoning_effort=None,
        trace_ids=None,
        max_completion_tokens=None,
    ):
        out = []
        for idx, prompt in enumerate(prompts):
            out.append(
                self._one_chat_sync(
                    prompt,
                    system_prompt=system_prompt,
                    reasoning_effort=reasoning_effort,
                    trace_id=trace_ids[idx] if trace_ids else None,
                    max_completion_tokens=max_completion_tokens,
                )
            )
        return out

    def _one_chat_sync(
        self,
        prompt,
        system_prompt=None,
        reasoning_effort=None,
        trace_id=None,
        max_completion_tokens=None,
    ):
        reasoning_effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort
        max_completion_tokens = (
            max_completion_tokens if max_completion_tokens is not None else self.max_completion_tokens
        )
        input_data = self._build_messages(prompt, system_prompt=system_prompt)

        trace_data = None
        if self.save_traces:
            self._trace_counter += 1
            trace_data = {
                "trace_id": trace_id or f"trace_{self._trace_counter}",
                "timestamp": dt.datetime.now().isoformat(),
                "model": self.model_name,
                "reasoning_effort": reasoning_effort,
                "max_completion_tokens": max_completion_tokens,
                "input": input_data,
                "response": None,
                "extracted_text": None,
                "error": None,
            }
            if self.extra_body:
                trace_data["extra_body"] = self.extra_body

        try:
            request_params = {"model": self.model_name, "messages": input_data}
            request_params["reasoning_effort"] = reasoning_effort
            if max_completion_tokens is not None:
                request_params["max_completion_tokens"] = max_completion_tokens
            if self.extra_body:
                request_params["extra_body"] = self.extra_body

            resp = self.client.chat.completions.create(**request_params)

            if trace_data is not None:
                trace_data["response"] = resp.model_dump()

            text_response = self._extract_text(resp)

            if trace_data is not None:
                trace_data["extracted_text"] = text_response
                self._save_trace(trace_data)

            return text_response
        except Exception as exc:
            if trace_data is not None:
                trace_data["error"] = str(exc)
                trace_data["extracted_text"] = f"ERROR: {type(exc).__name__}: {exc}"
                self._save_trace(trace_data)
            raise

    def generate_many(
        self,
        prompts,
        system_prompt=None,
        concurrency=16,
        reasoning_effort=None,
        trace_ids=None,
        max_completion_tokens=None,
    ):
        if self.async_flag:
            return asyncio.run(
                self._many_chat(
                    prompts,
                    system_prompt=system_prompt,
                    concurrency=concurrency,
                    reasoning_effort=reasoning_effort,
                    trace_ids=trace_ids,
                    max_completion_tokens=max_completion_tokens,
                )
            )
        return self._many_chat_sync(
            prompts,
            system_prompt=system_prompt,
            reasoning_effort=reasoning_effort,
            trace_ids=trace_ids,
            max_completion_tokens=max_completion_tokens,
        )

    def generate_one(
        self,
        prompt,
        system_prompt=None,
        reasoning_effort=None,
        trace_id=None,
        max_completion_tokens=None,
    ):
        trace_ids = [trace_id] if trace_id is not None else None
        return self.generate_many(
            [prompt],
            system_prompt=system_prompt,
            concurrency=1,
            reasoning_effort=reasoning_effort,
            trace_ids=trace_ids,
            max_completion_tokens=max_completion_tokens,
        )[0]


class OpenAIResponsesWrapper:
    def __init__(
        self,
        model_name,
        base_url,
        api_key="6767",
        save_traces=False,
        trace_dir=None,
        reasoning_effort="high",
        max_output_tokens=None,
    ):
        self.model_name = model_name
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.async_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.save_traces = save_traces
        self.trace_dir = trace_dir
        self._trace_counter = 0
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens

        if self.save_traces and trace_dir:
            Path(self.trace_dir).mkdir(parents=True, exist_ok=True)
            self.trace_file = Path(self.trace_dir) / "reasoning_traces.jsonl"

    def _save_trace(self, trace_data):
        if not self.save_traces or not self.trace_dir:
            return
        with open(self.trace_file, "a") as handle:
            handle.write(json.dumps(trace_data) + "\n")

    async def _one_chat(
        self,
        prompt,
        system_prompt=None,
        reasoning_effort=None,
        trace_id=None,
        max_output_tokens=None,
    ):
        reasoning_effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort
        max_output_tokens = max_output_tokens if max_output_tokens is not None else self.max_output_tokens

        if system_prompt:
            input_data = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        else:
            input_data = [{"role": "user", "content": prompt}]

        trace_data = None
        if self.save_traces:
            self._trace_counter += 1
            trace_data = {
                "trace_id": trace_id or f"trace_{self._trace_counter}",
                "timestamp": dt.datetime.now().isoformat(),
                "model": self.model_name,
                "reasoning_effort": reasoning_effort,
                "max_output_tokens": max_output_tokens,
                "input": input_data,
                "response": None,
                "extracted_text": None,
                "error": None,
            }

        try:
            request_params = {
                "model": self.model_name,
                "input": input_data,
                "reasoning": {"effort": reasoning_effort},
            }
            if max_output_tokens is not None:
                request_params["max_output_tokens"] = max_output_tokens

            resp = await self.async_client.responses.create(**request_params)

            if trace_data is not None:
                trace_data["response"] = resp.model_dump()

            text_response = ""
            if resp.output and len(resp.output) > 0:
                last_item = resp.output[-1]
                if hasattr(last_item, "content") and last_item.content:
                    first_content = last_item.content[0]
                    if hasattr(first_content, "text"):
                        text_response = first_content.text.strip()

            if trace_data is not None:
                trace_data["extracted_text"] = text_response
                self._save_trace(trace_data)

            return text_response
        except Exception as exc:
            if trace_data is not None:
                trace_data["error"] = str(exc)
                trace_data["extracted_text"] = f"ERROR: {type(exc).__name__}: {exc}"
                self._save_trace(trace_data)
            raise

    async def _many_chat(
        self,
        prompts,
        system_prompt=None,
        concurrency=16,
        reasoning_effort=None,
        trace_ids=None,
        max_output_tokens=None,
    ):
        sem = asyncio.Semaphore(concurrency)

        async def guarded(prompt, idx):
            async with sem:
                trace_id = trace_ids[idx] if trace_ids else None
                return await self._one_chat(
                    prompt,
                    system_prompt=system_prompt,
                    reasoning_effort=reasoning_effort,
                    trace_id=trace_id,
                    max_output_tokens=max_output_tokens,
                )

        return await asyncio.gather(*(guarded(prompt, idx) for idx, prompt in enumerate(prompts)))

    def generate_many(
        self,
        prompts,
        system_prompt=None,
        concurrency=16,
        reasoning_effort=None,
        trace_ids=None,
        max_output_tokens=None,
    ):
        return asyncio.run(
            self._many_chat(
                prompts,
                system_prompt=system_prompt,
                concurrency=concurrency,
                reasoning_effort=reasoning_effort,
                trace_ids=trace_ids,
                max_output_tokens=max_output_tokens,
            )
        )

    def generate_one(
        self,
        prompt,
        system_prompt=None,
        reasoning_effort=None,
        trace_id=None,
        max_output_tokens=None,
    ):
        trace_ids = [trace_id] if trace_id is not None else None
        return self.generate_many(
            [prompt],
            system_prompt=system_prompt,
            concurrency=1,
            reasoning_effort=reasoning_effort,
            trace_ids=trace_ids,
            max_output_tokens=max_output_tokens,
        )[0]
