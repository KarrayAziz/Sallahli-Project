import json
import re


_VALID_JSON_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')
_LATEX_COMMAND_ESCAPE_RE = re.compile(r'(?<!\\)\\(?=[A-Za-z])')
_HEX_DIGITS = set("0123456789abcdefABCDEF")


def _strip_json_fences(raw_text):
    # """
    # input : ```json {"a": 1} ```
    # output: {"a": 1}
    # """
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _escape_invalid_backslashes(raw_text):
    # """
    # input : \x  
    # ouput : \\x
    # """
    return _VALID_JSON_ESCAPE_RE.sub(r"\\\\", raw_text)


def _escape_latex_command_backslashes(raw_text):
    # """
    # input : \textbf{hello}  
    # ouput : \\textbf{hello}
    # """
    return _LATEX_COMMAND_ESCAPE_RE.sub(r"\\\\", raw_text)


def _repair_backslashes_inside_json_strings(raw_text):
#     """
#     ✔ Valid JSON escapes stay intact : v\n \" \u1234
#     ✔ Invalid escapes are fixed : \q → \\q
#     ✔ LaTeX is preserved safely : \alpha → \\alpha
#     """
    result = []
    in_string = False
    i = 0

    while i < len(raw_text):
        char = raw_text[i]

        if char == '"':
            slash_count = 0
            j = len(result) - 1
            while j >= 0 and result[j] == "\\":
                slash_count += 1
                j -= 1
            if slash_count % 2 == 0:
                in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string and char == "\\":
            next_char = raw_text[i + 1] if i + 1 < len(raw_text) else ""
            following_char = raw_text[i + 2] if i + 2 < len(raw_text) else ""

            if next_char == "u":
                unicode_digits = raw_text[i + 2:i + 6]
                if len(unicode_digits) == 4 and all(digit in _HEX_DIGITS for digit in unicode_digits):
                    result.append(char)
                else:
                    result.append("\\\\")
                i += 1
                continue

            if next_char in {'"', "\\", "/", "b", "f", "n", "r", "t"} and not following_char.isalpha():
                result.append(char)
            else:
                result.append("\\\\")
            i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def safe_json_loads(raw_text, context="model output"):
    """
    Parse model JSON while tolerating common LLM mistakes:
    - markdown JSON fences
    - raw LaTeX/backslash sequences inside JSON strings

    It first tries strict JSON, then a repaired version. If both fail, the
    original JSONDecodeError is raised with a small output preview in logs.
    """
    text = _strip_json_fences(raw_text or "")
    latex_safe_text = _repair_backslashes_inside_json_strings(_escape_latex_command_backslashes(text))

    try:
        return json.loads(latex_safe_text)
    except json.JSONDecodeError as original_error:
        repaired = _escape_invalid_backslashes(latex_safe_text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as repaired_error:
            preview = text[:1000]
            print(f"[JSON] Failed to parse {context}: {repaired_error}", flush=True)
            print(f"[JSON] Original parse error: {original_error}", flush=True)
            print(f"[JSON] Raw preview: {preview}", flush=True)
            raise repaired_error
        

test_input = r'''
{
  "question": "Solve this equation: \alpha + \beta = 5",
  "hint": "Use formula \frac{a}{b} and remember \n is newline",
  "bad_escape": "This is invalid: \q \x \y",
  "unicode_test": "Smile: \u263A and broken: \u12GZ",
  "mixed": "Math: \alpha \beta \gamma and quote: \"hello\""
}
'''

if main := __name__ == "__main__":
    print(safe_json_loads(test_input))

#output : 
# {
#   "question": "Solve this equation: \\alpha + \\beta = 5",
#   "hint": "Use formula \\frac{a}{b} and remember \n is newline",
#   "bad_escape": "This is invalid: \\q \\x \\y",
#   "unicode_test": "Smile: \u263A and broken: \\u12GZ",
#   "mixed": "Math: \\alpha \\beta \\gamma and quote: \\"hello\""
# }