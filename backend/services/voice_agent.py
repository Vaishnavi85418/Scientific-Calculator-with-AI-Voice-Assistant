"""
voice_agent.py
==============
Natural-language → mathematical-expression converter.

Strategy (3 layers, tried in order):
  1. Keyword-based parser  – catches structured spoken math in any phrasing
  2. Smart fallback        – extracts numbers + operator keyword from anything
  3. Direct-expression     – if the text already looks like a math expression, pass it through
  4. AI fallback           – if API key present, ask OpenAI
  5. Last-resort           – return success=False with a helpful message

Goal: ALWAYS give an answer if there is any mathematical intent whatsoever.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class VoiceResult:
    success: bool
    expression: Optional[str]
    spoken_response: str
    used_ai: bool = False


# ---------------------------------------------------------------------------
# Number helpers
# ---------------------------------------------------------------------------
_WORD_NUMBERS: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000",
    "million": "1000000",
}

# Number pattern used in all regexes – matches integers and decimals
_N = r"(-?\d+(?:\.\d+)?)"


def _words_to_digits(text: str) -> str:
    """Replace every number-word with its digit form."""
    # Handle compound like "twenty five" → "25"
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        w = words[i]
        # Try two-word compound (e.g. "twenty five")
        if i + 1 < len(words):
            compound = w + " " + words[i + 1]
            tens = _WORD_NUMBERS.get(w)
            ones = _WORD_NUMBERS.get(words[i + 1])
            if tens and ones and int(tens) >= 20 and 1 <= int(ones) <= 9:
                result.append(str(int(tens) + int(ones)))
                i += 2
                continue
        result.append(_WORD_NUMBERS.get(w, w))
        i += 1
    return " ".join(result)


def _prep(command: str) -> str:
    """Lowercase, strip filler phrases, replace word-numbers with digits."""
    raw = command.strip().lower()
    # Strip only sentence-level noise — keep "of", "the", "is", "by", "from"
    raw = re.sub(
        r"\b(please|could you|can you|what'?s|tell me|just|calculate|"
        r"compute|give me|show me|how much is|how many)\b",
        " ", raw
    )
    raw = re.sub(r"\s{2,}", " ", raw).strip()
    raw = _words_to_digits(raw)
    return raw


def _nums(text: str) -> list[str]:
    return re.findall(r"-?\d+(?:\.\d+)?", text)


# ---------------------------------------------------------------------------
# Layer 1 — keyword parser (flexible patterns, "of"/"the"/"is" optional)
# ---------------------------------------------------------------------------
def local_parse(command: str, mode: str = "DEG") -> Optional[VoiceResult]:
    raw = _prep(command)
    n   = _nums(raw)

    # ── helpers ──────────────────────────────────────────────────────────
    OF  = r"(?:\s+of)?"          # "of" is always optional
    THE = r"(?:\s+the)?"         # "the" is always optional
    ANY = r"[\s\w]*?"            # loose filler between tokens

    def hit(expr): return VoiceResult(True, expr, f"Calculating {expr}")

    # ── Percentage  "20 percent of 500" / "20% of 500" / "percentage 20 500" ─
    m = re.search(rf"{_N}\s*(?:percent(?:age)?|%)\s*(?:of\s*)?{_N}", raw)
    if m:
        return hit(f"{m.group(1)} * {m.group(2)} / 100")

    # ── Power / exponent ─────────────────────────────────────────────────
    # "2 raised to (the power of) 5" / "2 to the power 5" / "2 power 5"
    m = re.search(
        rf"{_N}\s+(?:raised\s+to(?:\s+the)?(?:\s+power(?:\s+of)?)?|"
        rf"to\s+the\s+power(?:\s+of)?|power(?:\s+of)?)\s+{_N}", raw)
    if m:
        return hit(f"{m.group(1)} ** {m.group(2)}")
    # "2 ^ 5"
    m = re.search(rf"{_N}\s*\^\s*{_N}", raw)
    if m:
        return hit(f"{m.group(1)} ** {m.group(2)}")
    # "5 squared" / "5 cubed"
    m = re.search(rf"{_N}\s+squared", raw)
    if m: return hit(f"{m.group(1)} ** 2")
    m = re.search(rf"{_N}\s+cubed", raw)
    if m: return hit(f"{m.group(1)} ** 3")

    # ── Cube root (before square root so "cube root" isn't eaten by "root") ─
    m = re.search(rf"cube\s*{THE}\s*root{OF}\s*{_N}", raw)
    if m: return hit(f"cbrt({m.group(1)})")
    m = re.search(rf"cbrt{OF}\s*{_N}", raw)
    if m: return hit(f"cbrt({m.group(1)})")

    # ── Square root ───────────────────────────────────────────────────────
    m = re.search(rf"(?:square\s*{THE}\s*root|sqrt|root){OF}\s*{_N}", raw)
    if m: return hit(f"sqrt({m.group(1)})")

    # ── Factorial ─────────────────────────────────────────────────────────
    m = re.search(rf"(?:factorial{OF}|{_N}\s+factorial)\s*{_N}?", raw)
    # Try "factorial of N" first
    m2 = re.search(rf"factorial{OF}\s*{_N}", raw)
    if m2: return hit(f"factorial({m2.group(1)})")
    m2 = re.search(rf"{_N}\s+factorial", raw)
    if m2: return hit(f"factorial({m2.group(1)})")

    # ── Trig / hyperbolic (order: longest name first to avoid sub-matches) ─
    TRIG = [
        (r"inverse\s+sine|arc\s*sine|arcsine",        "asin"),
        (r"inverse\s+cosine|arc\s*cosine|arccosine",  "acos"),
        (r"inverse\s+tangent|arc\s*tangent|arctangent","atan"),
        (r"hyperbolic\s+sine|sinh",                    "sinh"),
        (r"hyperbolic\s+cosine|cosh",                  "cosh"),
        (r"hyperbolic\s+tangent|tanh",                 "tanh"),
        (r"cosine|cos",                                "cos"),
        (r"tangent|tan",                               "tan"),
        (r"sine|sin",                                  "sin"),
        (r"asin",                                      "asin"),
        (r"acos",                                      "acos"),
        (r"atan",                                      "atan"),
    ]
    for pattern, fn in TRIG:
        m = re.search(rf"(?:{pattern}){OF}\s*{_N}", raw)
        if m: return hit(f"{fn}({m.group(1)})")

    # ── Logarithm ─────────────────────────────────────────────────────────
    m = re.search(rf"(?:natural\s+log(?:arithm)?|ln){OF}\s*{_N}", raw)
    if m: return hit(f"ln({m.group(1)})")
    m = re.search(rf"(?:log(?:arithm)?(?:\s+base\s+10)?){OF}\s*{_N}", raw)
    if m: return hit(f"log({m.group(1)})")

    # ── Exp ───────────────────────────────────────────────────────────────
    m = re.search(rf"(?:e\s+(?:to|raised)\s+(?:the\s+)?(?:power(?:\s+of)?)?|exp(?:onential)?){OF}\s*{_N}", raw)
    if m: return hit(f"exp({m.group(1)})")

    # ── Absolute value ────────────────────────────────────────────────────
    m = re.search(rf"(?:absolute\s*value|abs){OF}\s*{_N}", raw)
    if m: return hit(f"abs({m.group(1)})")

    # ── Floor / ceil / round ──────────────────────────────────────────────
    m = re.search(rf"floor{OF}\s*{_N}", raw)
    if m: return hit(f"floor({m.group(1)})")
    m = re.search(rf"(?:ceiling|ceil){OF}\s*{_N}", raw)
    if m: return hit(f"ceil({m.group(1)})")
    m = re.search(rf"round{OF}\s*{_N}", raw)
    if m: return hit(f"round({m.group(1)})")

    # ── Addition ──────────────────────────────────────────────────────────
    # Any of: add/plus/sum/and/with/total — optionally "to" or "with"
    m = re.search(rf"(?:add|plus|sum|total){ANY}{_N}{ANY}(?:and|to|with|plus)?{ANY}{_N}", raw)
    if not m:
        m = re.search(rf"{_N}\s+(?:plus|and)\s+{_N}", raw)
    if m:
        return hit(f"{m.group(1)} + {m.group(2)}")

    # ── Subtraction ───────────────────────────────────────────────────────
    m = re.search(rf"subtract\s+{_N}\s+from\s+{_N}", raw)
    if m: return hit(f"{m.group(2)} - {m.group(1)}")
    m = re.search(rf"(?:minus|subtract|less|take\s+away){ANY}{_N}{ANY}from\s+{_N}", raw)
    if m: return hit(f"{m.group(2)} - {m.group(1)}")
    m = re.search(rf"{_N}\s+(?:minus|less)\s+{_N}", raw)
    if m: return hit(f"{m.group(1)} - {m.group(2)}")

    # ── Multiplication ────────────────────────────────────────────────────
    m = re.search(rf"(?:multiply|times?|product){ANY}{_N}{ANY}(?:by|times|and|x)?\s*{_N}", raw)
    if not m:
        m = re.search(rf"{_N}\s+(?:times|multiplied\s+by|x)\s+{_N}", raw)
    if m: return hit(f"{m.group(1)} * {m.group(2)}")

    # ── Division ──────────────────────────────────────────────────────────
    m = re.search(rf"(?:divide|divided){ANY}{_N}{ANY}(?:by|over|into)\s+{_N}", raw)
    if not m:
        m = re.search(rf"{_N}\s+(?:divided\s+by|over)\s+{_N}", raw)
    if m: return hit(f"{m.group(1)} / {m.group(2)}")

    # ── Pi / e constants ─────────────────────────────────────────────────
    if re.search(r"\bpi\b", raw) and not n:
        return VoiceResult(True, "pi", "Pi ≈ 3.14159")
    if re.search(r"\beuler\b", raw) and not n:
        return VoiceResult(True, "e", "e ≈ 2.71828")

    return None


# ---------------------------------------------------------------------------
# Layer 2 — smart number-extraction fallback
# ---------------------------------------------------------------------------
# If someone says anything containing two numbers and a recognisable operator
# keyword, produce an expression. This catches creative phrasings like
# "kya hoga 12 aur 8 ka sum" or "bata 50 mein se 20".
# ---------------------------------------------------------------------------
_OP_KEYWORDS = {
    # Addition
    r"\badd\b|\bplus\b|\bsum\b|\band\b|\bmore\b|\btotal\b|\baur\b|\bjod\b": "+",
    # Subtraction
    r"\bsubtract\b|\bminus\b|\bless\b|\btake\s+away\b|\bghata\b|\bse\b": "-",
    # Multiplication
    r"\bmultiply\b|\btimes\b|\bproduct\b|\bguna\b|\bka\s+guna\b": "*",
    # Division
    r"\bdivide\b|\bover\b|\bby\b|\bbhag\b|\bka\s+bhag\b": "/",
}

def _smart_fallback(command: str, mode: str) -> Optional[VoiceResult]:
    raw = _prep(command)
    nums = _nums(raw)
    if len(nums) < 2:
        return None

    a, b = nums[0], nums[1]

    for pattern, op in _OP_KEYWORDS.items():
        if re.search(pattern, raw):
            # Special case: subtraction — check which way around
            if op == "-" and re.search(r"\bsubtract\b", raw):
                # "subtract A from B" → B - A
                m = re.search(
                    rf"subtract\s+{_N}\s+from\s+{_N}", raw
                )
                if m:
                    return VoiceResult(True, f"{m.group(2)} - {m.group(1)}", f"Calculating {m.group(2)} - {m.group(1)}")
            expr = f"{a} {op} {b}"
            return VoiceResult(True, expr, f"Calculating {expr}")

    # Two numbers with no operator keyword — assume addition as safest default
    # but only if they're clearly in an "X and Y" or "X Y" pattern
    if re.search(rf"{_N}\s+(?:and|aur|plus)\s+{_N}", raw):
        return VoiceResult(True, f"{a} + {b}", f"Calculating {a} + {b}")

    return None


# ---------------------------------------------------------------------------
# Layer 3 — direct expression passthrough
# ---------------------------------------------------------------------------
# If the transcript already looks like a valid math expression (digits +
# operators), pass it straight to the calculator engine.
# ---------------------------------------------------------------------------
_EXPR_PATTERN = re.compile(
    r"^[0-9\s\+\-\*\/\%\(\)\.\^a-z_]+$"
)
_HAS_OP = re.compile(r"[\+\-\*\/\%\^]|\b(sqrt|sin|cos|tan|log|ln|abs|exp|factorial|cbrt)\b")

def _direct_expr(command: str) -> Optional[VoiceResult]:
    raw = command.strip().lower()
    # Replace spoken symbols
    raw = raw.replace("×", "*").replace("÷", "/").replace("π", "pi").replace("^", "**")
    if _EXPR_PATTERN.match(raw) and _HAS_OP.search(raw):
        return VoiceResult(True, raw, f"Calculating {raw}")
    return None


# ---------------------------------------------------------------------------
# Layer 4 — AI-powered fallback (OpenAI-compatible)
# ---------------------------------------------------------------------------
_AI_SYSTEM_PROMPT = """\
You are a mathematical expression converter for a scientific calculator.
Your ONLY job is to convert natural language math questions into safe calculator expressions.

Rules:
- Respond with ONLY a JSON object, nothing else.
- The JSON must have exactly these keys:
    "expression": a math expression using only: numbers, +, -, *, /, **, %, (, ),
                  and these function names: sin cos tan asin acos atan sinh cosh tanh
                  log ln log10 sqrt cbrt abs exp floor ceil round factorial pi e
    "spoken_response": a short natural sentence with the answer.
- If you cannot understand the request, return:
    {"expression": null, "spoken_response": "I couldn't understand that calculation."}
- NEVER return Python code, JavaScript code, or any executable code.
- NEVER return anything outside the JSON object.
"""

def _call_openai(command: str, mode: str, api_key: str, model: str) -> Optional[VoiceResult]:
    import json
    import urllib.error
    import urllib.request

    base_url = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1")
    url = f"{base_url}/chat/completions"

    user_msg = (
        f"Convert this to a calculator expression. "
        f"The calculator is in {mode} mode (angles in {'degrees' if mode=='DEG' else 'radians'}).\n"
        f"Command: {command}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _AI_SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "temperature": 0,
        "max_tokens": 150,
    }

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
    except Exception as e:
        logger.warning("AI API call failed: %s", e)
        return None

    try:
        content = body["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        parsed  = json.loads(content)
    except Exception as e:
        logger.warning("AI response parse error: %s", e)
        return None

    expression = parsed.get("expression")
    spoken     = parsed.get("spoken_response", "Done.")

    if not expression:
        return VoiceResult(False, None, spoken, used_ai=True)

    safe_pattern = re.compile(r"^[0-9a-zA-Z_\s\+\-\*\/\%\(\)\.\,\^]+$")
    if not safe_pattern.match(expression):
        logger.warning("AI returned unsafe expression: %.200s", expression)
        return VoiceResult(False, None, "AI returned an unsafe expression — blocked.", used_ai=True)

    return VoiceResult(True, expression, spoken, used_ai=True)


# ---------------------------------------------------------------------------
# Conversation context (in-memory, per session)
# ---------------------------------------------------------------------------
_context: dict[str, float] = {}

def set_context(session_id: str, result: float) -> None:
    _context[session_id] = result

def get_context(session_id: str) -> Optional[float]:
    return _context.get(session_id)

def _resolve_that(command: str, session_id: str) -> str:
    last = get_context(session_id)
    if last is None:
        return command
    return re.sub(
        r"\b(that|it|the result|the answer|this|iska|uska)\b",
        str(last), command, flags=re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def process_voice_command(
    command: str,
    mode: str = "DEG",
    session_id: str = "default",
) -> VoiceResult:
    if not command or not command.strip():
        return VoiceResult(False, None, "I didn't catch that. Please try again.")

    resolved = _resolve_that(command.strip(), session_id)

    # Layer 1 — keyword parser
    result = local_parse(resolved, mode)
    if result and result.success:
        logger.info("Layer1 (keyword): %r -> %r", command, result.expression)
        return result

    # Layer 2 — smart number-extraction fallback
    result = _smart_fallback(resolved, mode)
    if result and result.success:
        logger.info("Layer2 (smart): %r -> %r", command, result.expression)
        return result

    # Layer 3 — direct expression passthrough
    result = _direct_expr(resolved)
    if result and result.success:
        logger.info("Layer3 (direct): %r -> %r", command, result.expression)
        return result

    # Layer 4 — AI
    api_key = os.getenv("AI_API_KEY", "").strip()
    model   = os.getenv("AI_MODEL", "gpt-4o-mini")
    if api_key:
        logger.info("Layer4 (AI, model=%s): %r", model, command)
        ai_result = _call_openai(resolved, mode, api_key, model)
        if ai_result is not None:
            return ai_result

    # Last resort — still try to do something with any two numbers found
    nums = _nums(_prep(resolved))
    if len(nums) == 1:
        # Single number — just evaluate it (user may be asking "what is 42?")
        return VoiceResult(True, nums[0], f"The answer is {nums[0]}.")
    if len(nums) >= 2:
        # Two numbers, no clear operator → default to addition
        expr = f"{nums[0]} + {nums[1]}"
        return VoiceResult(
            True, expr,
            f"I wasn't sure what to do, so I added them: {expr}",
        )

    return VoiceResult(
        False, None,
        "I couldn't find any numbers in that. Try: 'Add 25 and 35' or 'sqrt of 144'.",
    )
