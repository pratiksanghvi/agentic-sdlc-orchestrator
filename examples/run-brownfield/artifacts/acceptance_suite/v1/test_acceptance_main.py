"""Acceptance tests, phase 'main'. Generated from the approved test plan; do not edit."""

import json
from pathlib import Path

from acceptance_support import run_case

CASES = {c["id"]: c for c in json.loads((Path(__file__).parent / "cases.json").read_text())}


def test_tc_1(base_url):
    """TC-1 (AC-1.1): Create link with expiresInDays=7 returns 201 and Location /api/links/{code}"""
    run_case(CASES["TC-1"], base_url)


def test_tc_2(base_url):
    """TC-2 (AC-1.2): Link created with expiresInDays=1 is accepted and redirects before expiry (pre-advance portion; the contract exposes no test-clock control)"""
    run_case(CASES["TC-2"], base_url)


def test_tc_3(base_url):
    """TC-3 (AC-2.1): Create with minimum expiresInDays=1 returns 201 with exactly shortCode, longUrl, createdAt"""
    run_case(CASES["TC-3"], base_url)


def test_tc_4(base_url):
    """TC-4 (AC-2.1): Create with maximum expiresInDays=3650 returns 201 with exactly shortCode, longUrl, createdAt"""
    run_case(CASES["TC-4"], base_url)


def test_tc_5(base_url):
    """TC-5 (AC-2.2): Link with expiresInDays=3650 redirects immediately with 302 to submitted URL"""
    run_case(CASES["TC-5"], base_url)


def test_tc_6(base_url):
    """TC-6 (AC-3.1): expiresInDays=0 rejected with 400 problem+json mentioning expiry"""
    run_case(CASES["TC-6"], base_url)


def test_tc_7(base_url):
    """TC-7 (AC-3.1): expiresInDays=-1 rejected with 400 problem+json mentioning expiry"""
    run_case(CASES["TC-7"], base_url)


def test_tc_8(base_url):
    """TC-8 (AC-3.1): expiresInDays=1.5 rejected with 400 problem+json mentioning expiry"""
    run_case(CASES["TC-8"], base_url)


def test_tc_9(base_url):
    """TC-9 (AC-3.1): expiresInDays="7" (string) rejected with 400 problem+json mentioning expiry"""
    run_case(CASES["TC-9"], base_url)


def test_tc_10(base_url):
    """TC-10 (AC-3.1): expiresInDays=3651 rejected with 400 problem+json mentioning expiry"""
    run_case(CASES["TC-10"], base_url)


def test_tc_11(base_url):
    """TC-11 (AC-3.2): Huge expiresInDays rejected with 400 (not 500) and no stack trace"""
    run_case(CASES["TC-11"], base_url)


def test_tc_12(base_url):
    """TC-12 (AC-4.1): Rejected expiresInDays=0 produces no Location header and no short code"""
    run_case(CASES["TC-12"], base_url)


def test_tc_13(base_url):
    """TC-13 (AC-4.2): Valid create after rejected invalid-expiry create succeeds and the valid link exists"""
    run_case(CASES["TC-13"], base_url)


def test_tc_14(base_url):
    """TC-14 (AC-5.1): Link with expiresInDays=1 is live before expiry and is not answered with 410 (pre-advance portion; the contract exposes no test-clock control)"""
    run_case(CASES["TC-14"], base_url)


def test_tc_15(base_url):
    """TC-15 (AC-6.1): Link with expiresInDays=2 redirects with 302 before the 48h boundary"""
    run_case(CASES["TC-15"], base_url)


def test_tc_16(base_url):
    """TC-16 (AC-6.2): Link with expiresInDays=2 is not yet gone before creation + 48h (pre-boundary portion; the contract exposes no test-clock control)"""
    run_case(CASES["TC-16"], base_url)


def test_tc_17(base_url):
    """TC-17 (AC-7.1): Link created without expiresInDays redirects with 302 to long URL"""
    run_case(CASES["TC-17"], base_url)


def test_tc_18(base_url):
    """TC-18 (AC-7.2): Upgraded service is running and a non-expiring link redirects with 302 to its long URL (API-observable portion; data-store upgrade and restarts are performed outside the contract)"""
    run_case(CASES["TC-18"], base_url)


def test_tc_19(base_url):
    """TC-19 (AC-8.1): expiresInDays explicitly null is accepted with 201"""
    run_case(CASES["TC-19"], base_url)


def test_tc_20(base_url):
    """TC-20 (AC-8.2): Link created with expiresInDays=null redirects with 302"""
    run_case(CASES["TC-20"], base_url)


def test_tc_21(base_url):
    """TC-21 (AC-9.1): expiresInDays=7.0 rejected with 400 problem+json and no Location"""
    run_case(CASES["TC-21"], base_url)


def test_tc_22(base_url):
    """TC-22 (AC-9.1): expiresInDays=7e0 rejected with 400 problem+json and no Location"""
    run_case(CASES["TC-22"], base_url)


def test_tc_23(base_url):
    """TC-23 (AC-10.1): Single successful redirect on a 1-day link records clickCount=1 and a stable lastClickedAt (pre-advance portion; the contract exposes no test-clock control)"""
    run_case(CASES["TC-23"], base_url)


def test_tc_24(base_url):
    """TC-24 (AC-10.2): Never-redirected 1-day link shows clickCount=0 and lastClickedAt=null (pre-advance portion; the contract exposes no test-clock control)"""
    run_case(CASES["TC-24"], base_url)


def test_tc_25(base_url):
    """TC-25 (AC-11.1): Unexpired 5-day link redirects 302 with Location and Cache-Control no-store"""
    run_case(CASES["TC-25"], base_url)


def test_tc_26(base_url):
    """TC-26 (AC-11.2): Two redirects on an unexpired 5-day link yield clickCount=2 and non-null lastClickedAt"""
    run_case(CASES["TC-26"], base_url)


def test_tc_27(base_url):
    """TC-27 (AC-12.1): Unknown code zzzzzzz returns 404 problem+json"""
    run_case(CASES["TC-27"], base_url)


def test_tc_28(base_url):
    """TC-28 (AC-13.1): Details of a 1-day link return 200 with exactly shortCode, longUrl, createdAt"""
    run_case(CASES["TC-28"], base_url)


def test_tc_29(base_url):
    """TC-29 (AC-13.2): Analytics of a 1-day link return 200 with exactly shortCode, clickCount, lastClickedAt"""
    run_case(CASES["TC-29"], base_url)


def test_tc_30(base_url):
    """TC-30 (AC-14.1): Create with expiresInDays=7 returns exactly shortCode, longUrl, createdAt and no expiresAt"""
    run_case(CASES["TC-30"], base_url)


def test_tc_31(base_url):
    """TC-31 (AC-14.2): Create without expiresInDays returns 201 with Location and exactly the three fields"""
    run_case(CASES["TC-31"], base_url)


def test_tc_32(base_url):
    """TC-32 (AC-14.2): Unknown alias property is ignored: 201 with Location and exactly the three fields"""
    run_case(CASES["TC-32"], base_url)


def test_tc_33(base_url):
    """TC-33 (AC-15.1): Redirect responses for a 1-day link carry Cache-Control: no-store (pre-advance portion; the contract exposes no test-clock control)"""
    run_case(CASES["TC-33"], base_url)
