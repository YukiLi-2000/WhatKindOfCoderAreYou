#!/usr/bin/env python3
"""
Selenium end-to-end test runner for the DevSpectrum questionnaire.

Run this script while the Flask app is serving the quiz (default http://127.0.0.1:5001/).
It drives a visible Chrome browser by default so you can watch multiple persona
combinations being answered and see the resulting profile pages.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Iterable

# Ensure project root is importable when executed via `python tests/...`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import (  # type: ignore # noqa: E402
    AXES,
    AXIS_SEQUENCE,
    LETTER_DESCRIPTIONS,
    LETTER_TO_AXIS,
    QUESTIONS,
    build_profile_code,
    compute_scores,
)

from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.chrome.service import Service  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402
from webdriver_manager.chrome import ChromeDriverManager  # noqa: E402

BASE_URL_DEFAULT = "http://127.0.0.1:5001/"
DEFAULT_PROFILE_CODES = ["RPFA", "QCEV", "RPEV", "QPFV"]


def build_driver(headless: bool) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--window-size=1280,900")
    if headless:
        options.add_argument("--headless=new")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def determine_axis_targets(profile_code: str) -> Dict[str, str]:
    if len(profile_code) != len(AXIS_SEQUENCE):
        raise ValueError(
            f"Profile code {profile_code!r} does not match expected length {len(AXIS_SEQUENCE)}."
        )

    targets: Dict[str, str] = {}
    for axis_key, letter in zip(AXIS_SEQUENCE, profile_code):
        axis_info = AXES[axis_key]
        targets[axis_key] = "positive" if letter == axis_info["positive"] else "negative"
    return targets


def raw_answer_for_question(question, axis_targets: Dict[str, str]) -> int:
    axis_key = LETTER_TO_AXIS[question.dimension]
    target = axis_targets[axis_key]
    axis_info = AXES[axis_key]

    orientation = 1 if axis_info["positive"] == question.dimension else -1
    reverse = question.reverse

    if target == "positive":
        if orientation == 1:
            return 3 if not reverse else -3
        return -3 if not reverse else 3

    # target == "negative"
    if orientation == 1:
        return -3 if not reverse else 3
    return 3 if not reverse else -3


def build_answer_plan(profile_code: str) -> Dict[int, int]:
    axis_targets = determine_axis_targets(profile_code)
    return {question.id: raw_answer_for_question(question, axis_targets) for question in QUESTIONS}


def expected_profile_code(answer_plan: Dict[int, int]) -> str:
    form_data = {f"q{question_id}": str(value) for question_id, value in answer_plan.items()}
    score_data = compute_scores(form_data)
    profile_code, _ = build_profile_code(score_data["axis_scores"], LETTER_DESCRIPTIONS["en"])
    return profile_code


def fill_questionnaire(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    answer_plan: Dict[int, int],
    answer_delay: float,
) -> None:
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "form.panel-form")))

    for question in QUESTIONS:
        value_str = str(answer_plan[question.id])
        locator = (By.CSS_SELECTOR, f"input[name='{question.field_name}'][value='{value_str}']")
        option = wait.until(EC.element_to_be_clickable(locator))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
        option.click()
        if answer_delay > 0:
            time.sleep(answer_delay)


def run_profiles(
    profile_codes: Iterable[str],
    base_url: str,
    pause_seconds: float,
    answer_delay: float,
    headless: bool,
) -> None:
    driver = build_driver(headless=headless)
    wait = WebDriverWait(driver, 20)
    normalized_url = base_url.rstrip("/") + "/"

    try:
        codes = list(profile_codes)
        total = len(codes)
        for index, profile_code in enumerate(codes, start=1):
            answer_plan = build_answer_plan(profile_code)
            expected_code = expected_profile_code(answer_plan)

            driver.get(normalized_url)
            fill_questionnaire(driver, wait, answer_plan, answer_delay)

            submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit)
            submit.click()

            result = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".result-code")))
            actual_code = result.text.strip().upper()
            print(f"[{index}/{total}] Target {profile_code} -> page shows {actual_code}")
            if actual_code != expected_code:
                print(f"    (!) Expected {expected_code} based on predefined answers.")

            if not headless and pause_seconds > 0:
                time.sleep(pause_seconds)
    finally:
        driver.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate the DevSpectrum quiz in a browser using Selenium."
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL_DEFAULT,
        help="Root URL where the questionnaire is served (default: %(default)s).",
    )
    parser.add_argument(
        "--profiles",
        default=",".join(DEFAULT_PROFILE_CODES),
        help=(
            "Comma-separated profile codes to exercise (default: %(default)s). "
            "Each code must have four letters matching R/Q, P/C, F/E, A/V axes."
        ),
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=5.0,
        help="Pause duration on the result page for each profile when running with a visible browser.",
    )
    parser.add_argument(
        "--answer-delay",
        type=float,
        default=0.25,
        help="Delay (seconds) between selecting answers so the interaction is easier to follow.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome in headless mode (no visible window).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile_codes = [code.strip().upper() for code in args.profiles.split(",") if code.strip()]
    if not profile_codes:
        print("No valid profile codes provided. Nothing to do.", file=sys.stderr)
        sys.exit(1)

    try:
        run_profiles(
            profile_codes=profile_codes,
            base_url=args.base_url,
            pause_seconds=args.pause_seconds,
            answer_delay=args.answer_delay,
            headless=args.headless,
        )
    except Exception as exc:  # pragma: no cover - best-effort logging
        print(f"Selenium run failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
