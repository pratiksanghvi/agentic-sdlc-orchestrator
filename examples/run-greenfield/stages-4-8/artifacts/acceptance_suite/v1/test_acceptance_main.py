"""Acceptance tests, phase 'main'. Generated from the approved test plan; do not edit."""

import json
from pathlib import Path

from acceptance_support import run_case

CASES = {c["id"]: c for c in json.loads((Path(__file__).parent / "cases.json").read_text())}


def test_tc_1(base_url):
    """TC-1 (AC-1.1): Create short link for a valid https URL returns 201 with a non-empty short code"""
    run_case(CASES["TC-1"], base_url)


def test_tc_2(base_url):
    """TC-2 (AC-1.2): Details of a just-created link return the original URL"""
    run_case(CASES["TC-2"], base_url)


def test_tc_3(base_url):
    """TC-3 (AC-2.1): Redirect Location header equals the original long URL"""
    run_case(CASES["TC-3"], base_url)


def test_tc_4(base_url):
    """TC-4 (AC-3.1): Redirect status code is exactly 302"""
    run_case(CASES["TC-4"], base_url)


def test_tc_5(base_url):
    """TC-5 (AC-4.1): Details return the same short code that was requested"""
    run_case(CASES["TC-5"], base_url)


def test_tc_6(base_url):
    """TC-6 (AC-5.1): Three redirects produce a click count of 3"""
    run_case(CASES["TC-6"], base_url)


def test_tc_7(base_url):
    """TC-7 (AC-5.2): Clicks are counted per link independently (A=2, B=1)"""
    run_case(CASES["TC-7"], base_url)


def test_tc_8(base_url):
    """TC-8 (AC-6.1): Last-click timestamp is present as a date-time after one redirect"""
    run_case(CASES["TC-8"], base_url)


def test_tc_9(base_url):
    """TC-9 (AC-6.2): A second redirect updates the last-click timestamp"""
    run_case(CASES["TC-9"], base_url)


def test_tc_10(base_url):
    """TC-10 (AC-7.1): Analytics after one click report count 1 and non-null last-click timestamp"""
    run_case(CASES["TC-10"], base_url)


def test_tc_11(base_url):
    """TC-11 (AC-8.1): Two links for different URLs get different service-generated codes"""
    run_case(CASES["TC-11"], base_url)


def test_tc_12(base_url):
    """TC-12 (AC-9.1): Same long URL submitted twice yields different short codes"""
    run_case(CASES["TC-12"], base_url)


def test_tc_13(base_url):
    """TC-13 (AC-9.2): Links for the same URL count clicks independently"""
    run_case(CASES["TC-13"], base_url)


def test_tc_14(base_url):
    """TC-14 (AC-10.1): ftp URL is rejected with 400 and no short code"""
    run_case(CASES["TC-14"], base_url)


def test_tc_15(base_url):
    """TC-15 (AC-10.2): Relative path is rejected with 400 and no short code"""
    run_case(CASES["TC-15"], base_url)


def test_tc_16(base_url):
    """TC-16 (AC-10.3): Plain http URL without path is accepted"""
    run_case(CASES["TC-16"], base_url)


def test_tc_17(base_url):
    """TC-17 (AC-11.1): Details include short code, original URL and creation timestamp"""
    run_case(CASES["TC-17"], base_url)


def test_tc_18(base_url):
    """TC-18 (AC-12.1): Redirect for unknown code returns 404"""
    run_case(CASES["TC-18"], base_url)


def test_tc_19(base_url):
    """TC-19 (AC-12.2): Details for unknown code return 404"""
    run_case(CASES["TC-19"], base_url)


def test_tc_20(base_url):
    """TC-20 (AC-12.3): Analytics for unknown code return 404"""
    run_case(CASES["TC-20"], base_url)


def test_tc_21(base_url):
    """TC-21 (AC-13.1): Never-clicked link reports 0 clicks and no last-click timestamp"""
    run_case(CASES["TC-21"], base_url)


def test_tc_22(base_url):
    """TC-22 (AC-14.1): Five identical redirects from the same client count 5 clicks"""
    run_case(CASES["TC-22"], base_url)


def test_tc_23(base_url):
    """TC-23 (AC-14.2): Redirect for unknown code does not increment an existing link's count"""
    run_case(CASES["TC-23"], base_url)


def test_tc_24(base_url):
    """TC-24 (AC-15.1): All operations succeed without credentials"""
    run_case(CASES["TC-24"], base_url)
