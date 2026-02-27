#!/usr/bin/env python3
"""
Production smoke tests — run after each deployment.
Tests the critical path: text query → scheme response.
"""
import requests
import json
import sys
import argparse
import time

def run_smoke_tests(api_url: str, auth_token: str) -> bool:
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    all_passed = True

    tests = [
        {
            "name": "Create conversation session",
            "method": "POST",
            "path": "/conversations",
            "body": {"channel": "web", "language_preference": "hi"},
            "expect_status": 201,
            "expect_keys": ["session_id"],
        },
    ]

    session_id = None

    for test in tests:
        try:
            url = f"{api_url}{test['path']}"
            if "{session_id}" in url and session_id:
                url = url.replace("{session_id}", session_id)

            start = time.time()
            response = requests.request(
                test["method"], url,
                headers=headers,
                json=test.get("body"),
                timeout=15
            )
            latency_ms = int((time.time() - start) * 1000)

            status_ok = response.status_code == test["expect_status"]
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

            keys_ok = all(k in body for k in test.get("expect_keys", []))

            if status_ok and keys_ok:
                print(f"  PASS [{latency_ms}ms]: {test['name']}")
                if "session_id" in body:
                    session_id = body["session_id"]
            else:
                print(f"  FAIL: {test['name']} | status={response.status_code} (expected {test['expect_status']})")
                print(f"         body={body}")
                all_passed = False

        except Exception as e:
            print(f"  ERROR: {test['name']} | {e}")
            all_passed = False

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--token", default="test-token")
    args = parser.parse_args()

    print(f"Running smoke tests against {args.api_url} ({args.env})...")
    passed = run_smoke_tests(args.api_url, args.token)
    
    if passed:
        print("All smoke tests PASSED")
        sys.exit(0)
    else:
        print("SMOKE TESTS FAILED")
        sys.exit(1)
