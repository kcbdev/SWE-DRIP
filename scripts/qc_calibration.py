"""QC calibration runner — A10/A12 evidence (PBI-022).

Offline (default): runs the pinned fixtures (``pipeline/tests/fixtures/qc/``)
through the real rubric path and prints structured evidence. Fully offline —
this is the mode gates may invoke.

Live (``--live``): performs the SAME assertion against real vision calls.
Requires ``OPENROUTER_API_KEY`` plus two render images (local paths or URLs).
If live disagrees with the pins, the pins are stale — refresh them and record
the drift; never loosen the assertion.

Usage:
    python scripts/qc_calibration.py
    python scripts/qc_calibration.py --live --negative-image renders/ninja.png --positive-image renders/rocket.png
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import rubric  # noqa: E402
from pipeline.llm import OpenRouterClient  # noqa: E402
from pipeline.prompts import prompt_version  # noqa: E402
from pipeline.routing import model_for  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "pipeline" / "tests" / "fixtures" / "qc"


def load_pin(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def score_offline(pin: dict[str, Any]) -> dict[str, Any]:
    evaluation = rubric.evaluate(rubric.parse_scores(pin["pinned_vision_response"]))
    current = prompt_version("aesthetic_qc")
    return {
        "case": pin["name"],
        "mode": "offline-pinned",
        "rubric_version": rubric.RUBRIC_VERSION,
        "prompt_version": current,
        "prompt_matches_pin": pin.get("prompt_version", current) == current,
        "pass_threshold": rubric.PASS_THRESHOLD,
        "scores": evaluation["scores"],
        "result": evaluation["result"],
        "expected": pin["expected"],
        "match": evaluation["result"] == pin["expected"],
    }


def _image_url(ref: str) -> str:
    if ref.startswith(("http://", "https://", "data:")):
        return ref
    raw = Path(ref).read_bytes()
    mime = "image/png" if ref.lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def score_live(client: OpenRouterClient, model: str, pin: dict[str, Any], image: str) -> dict[str, Any]:
    prompt = rubric.build_qc_prompt(
        design_subject=pin["name"], style="locked-brand-style", attempt=1
    )
    result = client.vision(model=model, prompt=prompt, image_url=_image_url(image))
    content = result.content if isinstance(result.content, str) else ""
    evaluation = rubric.evaluate(rubric.parse_scores(json.loads(content)))
    return {
        "case": pin["name"],
        "mode": "live",
        "model": model,
        "rubric_version": rubric.RUBRIC_VERSION,
        "prompt_version": prompt_version("aesthetic_qc"),
        "pass_threshold": rubric.PASS_THRESHOLD,
        "scores": evaluation["scores"],
        "result": evaluation["result"],
        "expected": pin["expected"],
        "match": evaluation["result"] == pin["expected"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QC calibration runner (A10/A12)")
    parser.add_argument("--live", action="store_true", help="real vision calls (needs key + images)")
    parser.add_argument("--negative-image", default=None, help="ninja render (path or URL)")
    parser.add_argument("--positive-image", default=None, help="rocket render (path or URL)")
    args = parser.parse_args(argv)

    ninja, rocket = load_pin("ninja"), load_pin("rocket")
    if not args.live:
        evidence = [score_offline(ninja), score_offline(rocket)]
    else:
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY is not set", file=sys.stderr)
            return 2
        if not args.negative_image or not args.positive_image:
            print("--live needs --negative-image and --positive-image", file=sys.stderr)
            return 2
        client = OpenRouterClient()
        model = model_for("aesthetic_qc")
        assert model is not None
        evidence = [
            score_live(client, model, ninja, args.negative_image),
            score_live(client, model, rocket, args.positive_image),
        ]

    print(json.dumps({"evidence": evidence}, indent=2))
    ok = (
        all(item["match"] for item in evidence)
        and evidence[0]["result"] == "fail"
        and evidence[1]["result"] == "pass"
    )
    if not ok:
        print("CALIBRATION MISMATCH: pins are stale — refresh them, never loosen the assertion.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
