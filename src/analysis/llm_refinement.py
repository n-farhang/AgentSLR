# src/analysis/llm_refinement.py
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI


@dataclass(frozen=True)
class ReportRefinementSpec:
    report_type: str
    report_label: str
    raw_md_filename: str
    critique_dimensions: list[str]
    prompt_dir: Path
    stats_text_builder: Callable[[dict[str, Any]], str]
    draft_label: str


class AnalysisLLMClient:
    def __init__(
        self,
        model_name: str,
        base_url: str | None,
        api_key: str | None,
        responses_api: bool,
        reasoning_effort: str,
        max_completion_tokens: int | None,
    ):
        self.model_name = model_name
        self.responses_api = bool(responses_api)
        self.reasoning_effort = reasoning_effort
        self.max_completion_tokens = max_completion_tokens
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        json_mode: bool = False,
    ) -> str:
        if self.responses_api:
            params: dict[str, Any] = {
                "model": self.model_name,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "reasoning": {"effort": self.reasoning_effort},
            }
            if temperature is not None:
                params["temperature"] = temperature
            if self.max_completion_tokens is not None:
                params["max_output_tokens"] = self.max_completion_tokens
            response = self._call_with_fallback(
                self.client.responses.create,
                params,
                [
                    (),
                    ("temperature",),
                    ("max_output_tokens",),
                    ("temperature", "max_output_tokens"),
                ],
            )
            return self._extract_responses_text(response)

        params = {
            "model": self.model_name,
            "messages": [
                {"role": self._system_role(), "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "reasoning_effort": self.reasoning_effort,
        }
        if temperature is not None:
            params["temperature"] = temperature
        if self.max_completion_tokens is not None:
            params["max_completion_tokens"] = self.max_completion_tokens
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        response = self._call_with_fallback(
            self.client.chat.completions.create,
            params,
            [
                (),
                ("response_format",),
                ("temperature",),
                ("response_format", "temperature"),
                ("max_completion_tokens",),
                ("response_format", "max_completion_tokens"),
                ("temperature", "max_completion_tokens"),
                ("response_format", "temperature", "max_completion_tokens"),
            ],
        )
        return self._extract_chat_text(response)

    def _system_role(self) -> str:
        if self.model_name.startswith("o") or self.model_name.startswith("gpt-5"):
            return "developer"
        return "system"

    @staticmethod
    def _extract_chat_text(response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            return ""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif getattr(item, "type", None) == "text":
                    parts.append(getattr(item, "text", ""))
            return "".join(parts).strip()
        return ""

    @staticmethod
    def _extract_responses_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        parts: list[str] = []
        for item in getattr(response, "output", None) or []:
            item_type = getattr(item, "type", None)
            if item_type == "message":
                for content in getattr(item, "content", None) or []:
                    content_type = getattr(content, "type", None)
                    if content_type in {"output_text", "text"}:
                        text_value = getattr(content, "text", "")
                        if text_value:
                            parts.append(text_value)
                    elif isinstance(content, dict) and content.get("type") in {
                        "output_text",
                        "text",
                    }:
                        parts.append(content.get("text", ""))
            elif item_type in {"output_text", "text"}:
                text_value = getattr(item, "text", "")
                if text_value:
                    parts.append(text_value)
        return "".join(parts).strip()

    @staticmethod
    def _call_with_fallback(
        create_fn: Callable[..., Any],
        params: dict[str, Any],
        drop_sequences: list[tuple[str, ...]],
    ) -> Any:
        last_error = None
        for drop_keys in drop_sequences:
            try:
                attempt = {
                    key: value
                    for key, value in params.items()
                    if key not in set(drop_keys)
                }
                return create_fn(**attempt)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("No API call attempts were made")


class NarrativeRefiner:
    def __init__(
        self,
        llm_client: AnalysisLLMClient,
        spec: ReportRefinementSpec,
        max_iterations: int,
        common_prompt_dir: Path,
    ):
        self.llm_client = llm_client
        self.spec = spec
        self.max_iterations = max_iterations
        self.common_prompt_dir = common_prompt_dir

    def read_inputs_from_paths(
        self,
        pathogen: str,
        md_path: Path,
        manifest_path: Path,
        writeup_dir: Path,
    ) -> dict[str, Any]:
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {md_path}")
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        markdown = md_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        figures_info = "\n".join(
            [
                f"Figure {fig.get('number')}: {fig.get('title')}\n"
                f"  Path: {fig.get('path')}\n"
                f"  Caption: {fig.get('caption')}\n"
                f"  Observations: {fig.get('n_observations')}\n"
                for fig in manifest.get("figures", [])
            ]
        )
        tables_info = "\n".join(
            [
                f"Table {tbl.get('number')}: {tbl.get('title')}\n"
                f"  Columns: {', '.join(tbl.get('columns', []))}\n"
                f"  Rows: {tbl.get('n_rows')}\n"
                f"  Caption: {tbl.get('caption')}\n"
                for tbl in manifest.get("tables", [])
            ]
        )

        return {
            "pathogen": pathogen,
            "markdown": markdown,
            "manifest": manifest,
            "figures_info": figures_info,
            "tables_info": tables_info,
            "stats_text": self.spec.stats_text_builder(
                manifest.get("summary_statistics", {})
            ),
            "writeup_dir": writeup_dir,
            "required_assets": self._extract_required_assets(markdown),
        }

    def generate_initial_synthesis(self, inputs: dict[str, Any]) -> tuple[str, str]:
        narrative = self.llm_client.complete(
            system_prompt=self._render_prompt("initial_system.md", {}),
            user_prompt=self._render_prompt(
                "initial_user.md",
                {"EVIDENCE_PACKET": self._evidence_packet(inputs)},
            ),
            temperature=0.4,
        )
        narrative = self._normalize_final_markdown(narrative)
        narrative = self._ensure_assets_present(narrative, inputs.get("required_assets", {}))
        reasoning = (
            "INITIAL SYNTHESIS TRACE\n"
            f"Model: {self.llm_client.model_name}\n"
            "Temperature: 0.4\n"
            f"Evidence excerpt length: {len(inputs.get('markdown', ''))} chars\n"
            "Method basis: Self-Refine (iterative), G-Eval (rubric mindset), attribution-first revision, living review principles.\n"
            f"Scope: {self.spec.report_label.lower()}.\n"
        )
        return narrative, reasoning

    def critique_narrative(
        self,
        narrative: str,
        iteration: int,
        inputs: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        critique_text = self.llm_client.complete(
            system_prompt=self._render_prompt("critique_system.md", {}),
            user_prompt=self._render_prompt(
                "critique_user.md",
                {
                    "STATS_TEXT": inputs["stats_text"],
                    "REQUIRED_FIGURE_PATHS": "\n".join(
                        [
                            f"- {path}"
                            for path in inputs.get("required_assets", {}).get(
                                "image_paths", []
                            )
                        ]
                    ),
                    "NARRATIVE": narrative,
                },
            ),
            temperature=0.1,
            json_mode=not self.llm_client.responses_api,
        )

        critique = None
        if critique_text:
            try:
                critique = json.loads(critique_text)
            except Exception:
                raw_json = self._extract_first_balanced_json_object(critique_text)
                if raw_json:
                    try:
                        critique = json.loads(raw_json)
                    except Exception:
                        critique = None

        if critique is None:
            critique = self._json_repair_with_model(critique_text or "") or {}

        critique = self._normalize_critique_schema(critique, iteration)
        scores = {k: v.get("score", 3) for k, v in critique["dimensions"].items()}
        reasoning = (
            f"CRITIQUE TRACE (Iteration {iteration})\n"
            f"Model: {self.llm_client.model_name}\n"
            "Temperature: 0.1\n"
            f"Scores: {json.dumps(scores, indent=2)}\n"
            f"Priority fixes: {len(critique.get('priority_fixes', []))}\n"
        )
        return critique, reasoning

    def refine_narrative(
        self,
        narrative: str,
        critique: dict[str, Any],
        inputs: dict[str, Any],
    ) -> tuple[str, str]:
        dims_summary = "\n".join(
            [f"- {key}: {value.get('score', 3)}/5" for key, value in critique.get("dimensions", {}).items()]
        )
        priority = "\n".join([f"- {item}" for item in critique.get("priority_fixes", [])])
        refined = self.llm_client.complete(
            system_prompt=self._render_prompt("refine_system.md", {}),
            user_prompt=self._render_prompt(
                "refine_user.md",
                {
                    "QUALITY_SCORES": dims_summary,
                    "PRIORITY_FIXES": priority if priority.strip() else "- (none listed)",
                    "EVIDENCE_PACKET": self._evidence_packet(inputs),
                    "CURRENT_REPORT": narrative,
                },
            ),
            temperature=0.4,
        )
        refined = self._normalize_final_markdown(refined)
        refined = self._ensure_assets_present(refined, inputs.get("required_assets", {}))
        reasoning = (
            "REFINEMENT TRACE\n"
            f"Model: {self.llm_client.model_name}\n"
            "Temperature: 0.4\n"
            f"Issues addressed: {len(critique.get('priority_fixes', []))}\n"
            f"Scores pre-revision: {dims_summary}\n"
        )
        return refined, reasoning

    def run_refinement_loop(
        self,
        inputs: dict[str, Any],
        output_dir: Path,
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'=' * 80}")
        print(f"LLM Refinement for {inputs['pathogen']} {self.spec.report_label}")
        print(f"Using model: {self.llm_client.model_name}")
        print(f"{'=' * 80}\n")

        print("Step 1: Initial synthesis...")
        current_narrative, init_reasoning = self.generate_initial_synthesis(inputs)
        initial_path = output_dir / "iteration_0_initial.md"
        initial_path.write_text(current_narrative, encoding="utf-8")
        reasoning_path = output_dir / "iteration_0_reasoning.txt"
        reasoning_path.write_text(init_reasoning, encoding="utf-8")
        print(f"  ✓ Saved: {initial_path}")
        print(f"  ✓ Reasoning: {reasoning_path}")

        critiques: list[dict[str, Any]] = []
        all_reasoning: list[str] = [init_reasoning]

        for iteration in range(1, self.max_iterations + 1):
            print(f"\nIteration {iteration}/{self.max_iterations}")
            print("-" * 40)

            print("  Generating critique...")
            critique, critique_reasoning = self.critique_narrative(
                current_narrative,
                iteration,
                inputs,
            )
            critiques.append(critique)

            critique_path = output_dir / f"iteration_{iteration}_critique.json"
            critique_path.write_text(
                json.dumps(critique, indent=2),
                encoding="utf-8",
            )
            critique_reasoning_path = (
                output_dir / f"iteration_{iteration}_critique_reasoning.txt"
            )
            critique_reasoning_path.write_text(critique_reasoning, encoding="utf-8")

            dimensions = critique.get("dimensions", {})
            avg_score = sum(
                value.get("score", 3) for value in dimensions.values()
            ) / max(1, len(dimensions))

            print(f"  ✓ Critique: {critique_path}")
            print(f"  ✓ Reasoning: {critique_reasoning_path}")
            print(f"  Average score: {avg_score:.2f}/5.0")
            for name, value in dimensions.items():
                print(f"    - {name}: {value.get('score', 3)}/5")

            print("\n  Refining...")
            refined_narrative, refinement_reasoning = self.refine_narrative(
                current_narrative,
                critique,
                inputs,
            )

            refined_path = output_dir / f"iteration_{iteration}_refined.md"
            refined_path.write_text(refined_narrative, encoding="utf-8")
            refinement_reasoning_path = (
                output_dir / f"iteration_{iteration}_refinement_reasoning.txt"
            )
            refinement_reasoning_path.write_text(
                refinement_reasoning,
                encoding="utf-8",
            )

            all_reasoning.append(critique_reasoning)
            all_reasoning.append(refinement_reasoning)

            print(f"  ✓ Refined: {refined_path}")
            print(f"  ✓ Reasoning: {refinement_reasoning_path}")

            current_narrative = refined_narrative

        final_path = output_dir / "final_refined_narrative.md"
        final_path.write_text(current_narrative, encoding="utf-8")
        all_reasoning_path = output_dir / "complete_reasoning_trace.txt"
        all_reasoning_path.write_text(
            "\n\n" + "=" * 80 + "\n\n".join(all_reasoning),
            encoding="utf-8",
        )

        print(f"\n{'=' * 80}")
        print(f"✓ Final: {final_path}")
        print(f"✓ Complete reasoning trace: {all_reasoning_path}")
        print(f"{'=' * 80}\n")

        return current_narrative, critiques, all_reasoning

    def generate_summary(self, critiques: list[dict[str, Any]], output_path: Path):
        summary: dict[str, Any] = {
            "total_iterations": len(critiques),
            "timestamp": datetime.now().isoformat(),
            "quality_progression": [],
        }
        for idx, critique in enumerate(critiques, start=1):
            dimensions = critique.get("dimensions", {})
            avg_score = sum(
                value.get("score", 3) for value in dimensions.values()
            ) / max(1, len(dimensions))
            summary["quality_progression"].append(
                {
                    "iteration": idx,
                    "average_score": round(avg_score, 2),
                    "scores": {
                        dimension: value.get("score", 3)
                        for dimension, value in dimensions.items()
                    },
                }
            )
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def _json_repair_with_model(self, raw_text: str) -> dict[str, Any] | None:
        repaired = self.llm_client.complete(
            system_prompt=self._load_common_prompt("json_repair_system.md"),
            user_prompt=self._render_common_prompt(
                "json_repair_user.md",
                {"RAW_TEXT": raw_text},
            ),
            temperature=0.0,
            json_mode=not self.llm_client.responses_api,
        )
        if not repaired:
            return None
        try:
            return json.loads(repaired)
        except Exception:
            raw_json = self._extract_first_balanced_json_object(repaired)
            if raw_json is None:
                return None
            try:
                return json.loads(raw_json)
            except Exception:
                return None

    def _normalize_critique_schema(
        self,
        critique: dict[str, Any],
        iteration: int,
    ) -> dict[str, Any]:
        dimensions = critique.get("dimensions", {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        for name in self.spec.critique_dimensions:
            if not isinstance(dimensions.get(name), dict):
                dimensions[name] = {"score": 3, "issues": [], "suggestions": []}
            if "score" not in dimensions[name]:
                dimensions[name]["score"] = 3
            try:
                score = int(dimensions[name].get("score", 3))
            except Exception:
                score = 3
            dimensions[name]["score"] = max(1, min(5, score))
            if not isinstance(dimensions[name].get("issues"), list):
                dimensions[name]["issues"] = []
            if not isinstance(dimensions[name].get("suggestions"), list):
                dimensions[name]["suggestions"] = []
        critique["dimensions"] = dimensions
        if not isinstance(critique.get("priority_fixes"), list):
            critique["priority_fixes"] = []
        critique["iteration"] = iteration
        critique["timestamp"] = datetime.now().isoformat()
        return critique

    def _evidence_packet(
        self,
        inputs: dict[str, Any],
        truncate_md_chars: int = 9000,
    ) -> str:
        markdown_excerpt = inputs["markdown"][:truncate_md_chars]
        required_paths = inputs.get("required_assets", {}).get("image_paths", [])
        return (
            f"PATHOGEN: {inputs['pathogen']}\n\n"
            f"DATASET SUMMARY:\n{inputs['stats_text']}\n\n"
            "FIGURES AVAILABLE (must all appear at least once as markdown images; placement may change):\n"
            f"{inputs['figures_info']}\n\n"
            "TABLES AVAILABLE (may be reformatted but values must not change; all must be present):\n"
            f"{inputs['tables_info']}\n\n"
            "REQUIRED FIGURE PATHS:\n"
            + "\n".join([f"- {path}" for path in required_paths])
            + "\n\n"
            f"RA DRAFT (EXCERPT; treat as {self.spec.draft_label}):\n"
            f"{markdown_excerpt}\n"
        )

    @staticmethod
    def _extract_required_assets(markdown: str) -> dict[str, Any]:
        image_lines = []
        image_paths = []
        image_entries = []
        lines = markdown.splitlines()
        for idx, line in enumerate(lines):
            match = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
            if match:
                image_lines.append(line.rstrip("\n"))
                image_path = match.group(2).strip()
                image_paths.append(image_path)
                caption = ""
                cursor = idx + 1
                while cursor < len(lines):
                    candidate = lines[cursor].strip()
                    if not candidate:
                        cursor += 1
                        continue
                    if candidate.startswith("**Figure"):
                        caption = candidate
                    break
                image_entries.append(
                    {
                        "path": image_path,
                        "image_line": line.rstrip("\n"),
                        "caption": caption,
                    }
                )

        table_blocks = []
        table_entries = []
        idx = 0
        while idx < len(lines):
            if lines[idx].strip().startswith("|"):
                block = []
                heading = ""
                back = idx - 1
                while back >= 0:
                    candidate = lines[back].strip()
                    if not candidate:
                        back -= 1
                        continue
                    if candidate.startswith("#"):
                        heading = candidate
                    break
                cursor = idx
                while cursor < len(lines) and lines[cursor].strip().startswith("|"):
                    block.append(lines[cursor].rstrip("\n"))
                    cursor += 1
                if len(block) >= 2:
                    table_block = "\n".join(block)
                    table_blocks.append(table_block)
                    caption = ""
                    forward = cursor
                    while forward < len(lines):
                        candidate = lines[forward].strip()
                        if not candidate:
                            forward += 1
                            continue
                        if candidate.startswith("*"):
                            caption = candidate
                        break
                    table_entries.append(
                        {
                            "heading": heading,
                            "block": table_block,
                            "caption": caption,
                        }
                    )
                idx = cursor
            else:
                idx += 1

        return {
            "image_lines": image_lines,
            "image_paths": sorted(set(image_paths)),
            "image_entries": image_entries,
            "table_blocks": table_blocks,
            "table_entries": table_entries,
        }

    @staticmethod
    def _ensure_assets_present(md_text: str, required_assets: dict[str, Any]) -> str:
        output = md_text if isinstance(md_text, str) else ""
        image_paths = required_assets.get("image_paths", [])
        table_blocks = required_assets.get("table_blocks", [])
        image_entries = required_assets.get("image_entries", [])
        table_entries = required_assets.get("table_entries", [])

        missing_images = [path for path in image_paths if path not in output]
        missing_tables = []
        normalized_output = re.sub(r"\s+", " ", output)
        for table_block in table_blocks:
            normalized_table = re.sub(r"\s+", " ", table_block.strip())
            if normalized_table and normalized_table not in normalized_output:
                missing_tables.append(table_block)

        appendix_started = False
        if missing_images or missing_tables:
            output += "\n\n---\n\n## Appendix\n"
            appendix_started = True

        if missing_images:
            for path in missing_images:
                entry = next(
                    (item for item in image_entries if item.get("path") == path),
                    None,
                )
                image_line = (
                    entry.get("image_line")
                    if entry and entry.get("image_line")
                    else f"![Figure]({path})"
                )
                output += f"\n{image_line}\n"
                if entry and entry.get("caption"):
                    output += f"{entry['caption']}\n"

        if missing_tables:
            for table_block in missing_tables:
                entry = next(
                    (item for item in table_entries if item.get("block") == table_block),
                    None,
                )
                heading = entry.get("heading", "") if entry else ""
                caption = entry.get("caption", "") if entry else ""
                if heading:
                    output += f"\n{heading}\n"
                output += f"\n{table_block}\n"
                if caption:
                    output += f"{caption}\n"

        return output

    @staticmethod
    def _normalize_final_markdown(markdown: str) -> str:
        if not isinstance(markdown, str):
            return ""
        lines = markdown.splitlines()
        normalized_lines: list[str] = []

        for idx, line in enumerate(lines):
            if idx == 0 and line.startswith("#"):
                line = re.sub(
                    r"\s*\((?:Version|version)[^)]+\)",
                    "",
                    line,
                ).rstrip()
            if re.match(r"^##\s+Appendix:", line.strip()):
                line = "## Appendix"
            if re.match(r"^###\s+Auto-appended", line.strip(), flags=re.IGNORECASE):
                continue
            line = re.sub(
                r"\s*Report Figure\s+\d+;?\s*file\s+`[^`]+`\.*",
                "",
                line,
                flags=re.IGNORECASE,
            )
            line = re.sub(r"auto-appended", "", line, flags=re.IGNORECASE)
            line = re.sub(
                r"\s*file\s+`figures/[^`]+`\.*",
                "",
                line,
                flags=re.IGNORECASE,
            )
            line = re.sub(r"\s{2,}", " ", line).rstrip()
            normalized_lines.append(line)

        return "\n".join(normalized_lines).strip() + "\n"

    @staticmethod
    def _extract_first_balanced_json_object(text: str) -> str | None:
        if not isinstance(text, str):
            return None
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : idx + 1]
        return None

    def _render_prompt(self, filename: str, replacements: dict[str, str]) -> str:
        prompt = (self.spec.prompt_dir / filename).read_text(encoding="utf-8")
        for key, value in replacements.items():
            prompt = prompt.replace(f"{{{{{key}}}}}", value)
        return prompt

    def _load_common_prompt(self, filename: str) -> str:
        return (self.common_prompt_dir / filename).read_text(encoding="utf-8")

    def _render_common_prompt(
        self,
        filename: str,
        replacements: dict[str, str],
    ) -> str:
        prompt = self._load_common_prompt(filename)
        for key, value in replacements.items():
            prompt = prompt.replace(f"{{{{{key}}}}}", value)
        return prompt


def generate_pdf(md_path: Path, pdf_path: Path, base_dir: Path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_JUSTIFY
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    markdown = md_path.read_text(encoding="utf-8")
    styles = getSampleStyleSheet()

    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        spaceAfter=12,
        spaceBefore=12,
        textColor=colors.HexColor("#1B4F72"),
        fontName="Helvetica-Bold",
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=17,
        spaceAfter=8,
        spaceBefore=10,
        textColor=colors.HexColor("#2E86AB"),
        fontName="Helvetica-Bold",
    )
    h3 = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontSize=11,
        leading=15,
        spaceAfter=6,
        spaceBefore=8,
        fontName="Helvetica-Bold",
    )
    code = ParagraphStyle(
        "Code",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Courier",
        leftIndent=20,
        rightIndent=20,
        spaceAfter=6,
        spaceBefore=6,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=60,
        leftMargin=60,
        topMargin=60,
        bottomMargin=60,
    )
    available_width = letter[0] - doc.leftMargin - doc.rightMargin

    def clean_text(text: str) -> str:
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace("–", "-")
        text = text.replace("—", "-")
        text = text.replace("“", '"')
        text = text.replace("”", '"')
        text = text.replace("‘", "'")
        text = text.replace("’", "'")
        return text

    def parse_inline(text: str) -> str:
        text = clean_text(text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
        return text

    def parse_fig_layout(layout_line: str) -> dict[str, float]:
        values: dict[str, float] = {}
        match = re.search(r"<!--\s*fig-layout:\s*([^>]*)-->", layout_line.strip())
        if not match:
            return values
        for part in re.split(r"\s+", match.group(1).strip()):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            try:
                values[key.strip()] = float(value.strip())
            except Exception:
                continue
        return values

    story: list[Any] = []
    lines = markdown.splitlines()
    idx = 0
    in_code_block = False
    code_lines: list[str] = []

    while idx < len(lines):
        line = lines[idx].rstrip()

        if line.startswith("```"):
            if in_code_block:
                story.append(Paragraph(clean_text("\n".join(code_lines)), code))
                story.append(Spacer(1, 6))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            idx += 1
            continue

        if in_code_block:
            code_lines.append(line)
            idx += 1
            continue

        if line.startswith("# "):
            story.append(Paragraph(parse_inline(line[2:]), h1))
        elif line.startswith("## "):
            story.append(Paragraph(parse_inline(line[3:]), h2))
        elif line.startswith("### "):
            story.append(Paragraph(parse_inline(line[4:]), h3))
        elif line.strip().startswith("![") and "](" in line:
            try:
                match = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", line)
                if match:
                    img_path = Path(match.group(2))
                    if not img_path.is_absolute():
                        img_path = (base_dir / img_path).resolve()
                    if img_path.exists():
                        layout = {}
                        if idx + 1 < len(lines):
                            layout = parse_fig_layout(lines[idx + 1])
                        image = Image(str(img_path))
                        image_width = float(image.imageWidth)
                        image_height = float(image.imageHeight)
                        draw_width = min(available_width, 5.5 * inch)
                        if "width_in" in layout:
                            draw_width = min(
                                available_width,
                                max(1.0 * inch, layout["width_in"] * inch),
                            )
                        aspect = image_height / image_width if image_width > 0 else 1.0
                        draw_height = draw_width * aspect
                        if "max_height_in" in layout:
                            max_height = max(1.0 * inch, layout["max_height_in"] * inch)
                            if draw_height > max_height:
                                draw_height = max_height
                                draw_width = draw_height / aspect if aspect > 0 else draw_width
                        image.drawWidth = draw_width
                        image.drawHeight = draw_height
                        story.append(image)
                        story.append(Spacer(1, 10))
                        if idx + 1 < len(lines) and re.search(
                            r"<!--\s*fig-layout:",
                            lines[idx + 1].strip(),
                        ):
                            idx += 1
            except Exception as exc:
                print(f"Warning: Could not add image: {exc}")
        elif line.strip().startswith("|"):
            table_lines = []
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                table_lines.append(lines[idx])
                idx += 1
            idx -= 1
            if len(table_lines) >= 2:
                rows = []
                for table_line in table_lines:
                    if not re.match(r"\|[\s:-]+\|", table_line):
                        rows.append(
                            [
                                clean_text(cell.strip())
                                for cell in table_line.strip().strip("|").split("|")
                            ]
                        )
                if rows:
                    table = Table(rows)
                    table.setStyle(
                        TableStyle(
                            [
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                                ("FONTSIZE", (0, 0), (-1, -1), 9),
                                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ]
                        )
                    )
                    story.append(table)
                    story.append(Spacer(1, 10))
        elif line.strip() == "---":
            story.append(Spacer(1, 15))
        elif line.strip():
            story.append(Paragraph(parse_inline(line), body))

        idx += 1

    try:
        doc.build(story)
        print(f"✓ PDF: {pdf_path}")
    except Exception as exc:
        print(f"✗ PDF generation failed: {exc}")


def promote_refined_outputs(
    writeup_dir: Path,
    raw_md_filename: str,
    refined_dirname: str,
) -> dict[str, str]:
    refined_dir = writeup_dir / refined_dirname
    source = refined_dir / "final_refined_narrative.md"
    source_pdf = refined_dir / "final_refined_narrative.pdf"
    if not source.exists():
        raise FileNotFoundError(str(source))

    promoted_md = writeup_dir / raw_md_filename
    promoted_pdf = writeup_dir / raw_md_filename.replace(".md", ".pdf")
    final_copy = writeup_dir / "final_refined_narrative.md"
    markdown = source.read_text(encoding="utf-8")
    promoted_md.write_text(markdown, encoding="utf-8")
    final_copy.write_text(markdown, encoding="utf-8")
    promoted = {"promoted_md": str(promoted_md), "top_level_md": str(final_copy)}
    if source_pdf.exists():
        top_level_pdf = writeup_dir / "final_refined_narrative.pdf"
        top_level_pdf.write_bytes(source_pdf.read_bytes())
        promoted_pdf.write_bytes(source_pdf.read_bytes())
        promoted["top_level_pdf"] = str(top_level_pdf)
        promoted["promoted_pdf"] = str(promoted_pdf)
    return promoted


def run_report_refinement(
    config,
    spec: ReportRefinementSpec,
    writeup_dir: Path,
) -> dict[str, str]:
    llm_client = AnalysisLLMClient(
        model_name=config.report_model_name,
        base_url=config.report_base_url,
        api_key=config.report_api_key,
        responses_api=config.report_responses_api,
        reasoning_effort=config.report_reasoning_effort,
        max_completion_tokens=config.report_max_completion_tokens,
    )
    refiner = NarrativeRefiner(
        llm_client=llm_client,
        spec=spec,
        max_iterations=config.writeup_refinement_iterations,
        common_prompt_dir=Path(__file__).parent / "prompts" / "common",
    )

    md_path = writeup_dir / spec.raw_md_filename
    manifest_path = writeup_dir / "content_manifest.json"
    inputs = refiner.read_inputs_from_paths(
        config.pathogen,
        md_path,
        manifest_path,
        writeup_dir,
    )
    output_dir = writeup_dir / config.writeup_refinement_dirname
    final_narrative, critiques, _ = refiner.run_refinement_loop(inputs, output_dir)

    summary_path = output_dir / "refinement_summary.json"
    refiner.generate_summary(critiques, summary_path)

    final_md_path = output_dir / "final_refined_narrative.md"
    final_md_path.write_text(final_narrative, encoding="utf-8")
    final_pdf_path = output_dir / "final_refined_narrative.pdf"
    generate_pdf(final_md_path, final_pdf_path, writeup_dir)

    promoted_paths = promote_refined_outputs(
        writeup_dir=writeup_dir,
        raw_md_filename=spec.raw_md_filename,
        refined_dirname=config.writeup_refinement_dirname,
    )

    return {
        "md": str(final_md_path),
        "pdf": str(final_pdf_path),
        "summary": str(summary_path),
        "reasoning": str(output_dir / "complete_reasoning_trace.txt"),
        **promoted_paths,
    }


def main():
    print(
        "This module is intended to be used through src.analysis.*.writeup_llm wrappers.",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
