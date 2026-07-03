#!/usr/bin/env python3
"""Compare JSON vs TOON output size and token count for all dwdweather commands."""

import subprocess
from pathlib import Path

import tiktoken

LOCATION = "Berlin"
HIST_DATE = "2025-05-01"

COMMANDS: list[tuple[str, list[str]]] = [
    ("current", ["current", LOCATION]),
    ("forecast hourly", ["forecast", LOCATION]),
    ("forecast daily", ["forecast", "--daily", LOCATION]),
    ("history hourly", ["history", "--date", HIST_DATE, LOCATION]),
    ("history daily", ["history", "--daily", "--date", HIST_DATE, LOCATION]),
    ("alerts", ["alerts", LOCATION]),
    ("stations", ["stations", LOCATION]),
    ("summary", ["summary", LOCATION]),
]

DWDWEATHER = Path(__file__).parent / ".venv" / "bin" / "dwdweather"

RATINGS = [
    (0.50, "Excellent  (>50% smaller)"),
    (0.65, "Good       (>35% smaller)"),
    (0.80, "Moderate   (>20% smaller)"),
    (1.00, "Minimal    (<20% smaller)"),
]

_enc = tiktoken.get_encoding("o200k_base")

BAR_WIDTH = 30


def rating(ratio: float) -> str:
    for threshold, label in RATINGS:
        if ratio <= threshold:
            return label
    return RATINGS[-1][1]


def run(args: list[str], fmt: str) -> tuple[bytes, bool]:
    cmd = [str(DWDWEATHER), args[0], "--output", fmt] + args[1:]
    result = subprocess.run(cmd, capture_output=True)
    return result.stdout, result.returncode == 0


def count_tokens(data: bytes) -> int:
    return len(_enc.encode(data.decode("utf-8", errors="replace")))


def bar(savings_pct: float) -> str:
    filled = round(savings_pct / 100 * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def main() -> None:
    Row = tuple[str, int, int, int, int, float, float]
    rows: list[Row] = []

    for label, args in COMMANDS:
        json_data, ok_json = run(args, "json")
        toon_data, ok_toon = run(args, "toon")
        if not ok_json or not ok_toon or not json_data:
            print(f"  SKIP  {label}  (error or no data)")
            continue

        json_bytes = len(json_data)
        toon_bytes = len(toon_data)
        json_tokens = count_tokens(json_data)
        toon_tokens = count_tokens(toon_data)
        byte_ratio = toon_bytes / json_bytes
        tok_ratio = toon_tokens / json_tokens if json_tokens else 0.0
        rows.append((label, json_bytes, toon_bytes, json_tokens, toon_tokens, byte_ratio, tok_ratio))

    if not rows:
        print("No results.")
        return

    col_w = max(len(r[0]) for r in rows) + 2
    sep = "-" * (col_w + 8 + 8 + 9 + 8 + 8 + 9 + BAR_WIDTH + 2 + 26)
    header = (
        f"{'Command':<{col_w}} {'JSON B':>8} {'TOON B':>8} {'B-Save':>8}"
        f"  {'JSON T':>7} {'TOON T':>7} {'T-Save':>8}"
        f"  {'Byte savings':<{BAR_WIDTH}}  Rating"
    )
    print()
    print(header)
    print(sep)

    for label, jb, tb, jt, tt, byte_ratio, tok_ratio in rows:
        b_save = (1 - byte_ratio) * 100
        t_save = (1 - tok_ratio) * 100
        print(
            f"{label:<{col_w}} {jb:>8,} {tb:>8,} {b_save:>7.1f}%"
            f"  {jt:>7,} {tt:>7,} {t_save:>7.1f}%"
            f"  {bar(b_save)}  {rating(byte_ratio)}"
        )

    total_jb = sum(r[1] for r in rows)
    total_tb = sum(r[2] for r in rows)
    total_jt = sum(r[3] for r in rows)
    total_tt = sum(r[4] for r in rows)
    total_b_save = (1 - total_tb / total_jb) * 100
    total_t_save = (1 - total_tt / total_jt) * 100 if total_jt else 0.0
    total_byte_ratio = total_tb / total_jb
    print(sep)
    print(
        f"{'TOTAL':<{col_w}} {total_jb:>8,} {total_tb:>8,} {total_b_save:>7.1f}%"
        f"  {total_jt:>7,} {total_tt:>7,} {total_t_save:>7.1f}%"
        f"  {bar(total_b_save)}  {rating(total_byte_ratio)}"
    )
    print()


if __name__ == "__main__":
    main()
