#!/usr/bin/env python
"""
Validation Test Script for RAG Calling Agent Fixes
Tests all 5 critical fixes applied to the system.
"""

import requests
import json
import time
from typing import Dict, List

BASE_URL = "http://localhost:8000"

class Colors:
    GREEN = ''
    RED = ''
    YELLOW = ''
    BLUE = ''
    END = ''

def print_test(name: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def print_pass(msg: str):
    print(f"{Colors.GREEN}✓ PASS: {msg}{Colors.END}")

def print_fail(msg: str):
    print(f"{Colors.RED}✗ FAIL: {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.YELLOW}ℹ INFO: {msg}{Colors.END}")

# TEST 1: Session ID Middleware
def test_session_id_middleware():
    print_test("Fix 1: Session ID Middleware")
    
    try:
        response = requests.post(
            f"{BASE_URL}/qa/query",
            json={"message": "test session id"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "session_id" in data:
                print_pass(f"Session ID present in response: {data['session_id']}")
                return True
            else:
                print_fail("No session_id in response")
                return False
        else:
            print_fail(f"Request failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"Exception: {e}")
        return False

# TEST 2: TTS Health Check
def test_tts_fallback():
    print_test("Fix 2: TTS Fallback Mechanism")
    
    try:
        response = requests.get(f"{BASE_URL}/health/tts", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print_info(f"TTS Health: {json.dumps(data, indent=2)}")
            
            if data.get("pyttsx3_available"):
                print_pass("pyttsx3 is available (fallback working)")
            else:
                print_fail("pyttsx3 not available")
                
            if data.get("status") == "healthy":
                print_pass("TTS service is healthy")
                return True
            else:
                print_fail("TTS service degraded")
                return False
        else:
            print_fail(f"Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"Exception: {e}")
        return False

# TEST 3: Cache Deduplication
def test_cache_deduplication():
    print_test("Fix 3: Cache Deduplication")
    
    test_query = f"Test cache query {int(time.time())}"
    
    try:
        # First request (cache miss)
        print_info("Making first request (cache miss)...")
        start1 = time.time()
        response1 = requests.post(
            f"{BASE_URL}/qa/query",
            json={"message": test_query},
            timeout=30
        )
        time1 = time.time() - start1
        
        if response1.status_code != 200:
            print_fail(f"First request failed: {response1.status_code}")
            return False
            
        # Second request (should hit cache)
        print_info("Making second request (should hit cache)...")
        time.sleep(0.5)  # Small delay
        start2 = time.time()
        response2 = requests.post(
            f"{BASE_URL}/qa/query",
            json={"message": test_query},
            timeout=30
        )
        time2 = time.time() - start2
        
        if response2.status_code != 200:
            print_fail(f"Second request failed: {response2.status_code}")
            return False
            
        print_info(f"First request: {time1:.2f}s")
        print_info(f"Second request: {time2:.2f}s")
        
        if time2 < time1 * 0.5:  # Cache hit should be much faster
            print_pass("Cache hit is significantly faster")
            return True
        else:
            print_fail("Cache doesn't seem to be working (similar times)")
            return False
            
    except Exception as e:
        print_fail(f"Exception: {e}")
        return False

# TEST 4: Document Diversity (requires log inspection)
def test_document_diversity():
    print_test("Fix 4: Document Diversity")
    
    try:
        response = requests.post(
            f"{BASE_URL}/qa/query",
            json={"message": "Tell me about admissions and fees"},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])
            
            print_info(f"Retrieved {len(sources)} sources")
            
            # Check for unique sources
            unique_sources = set()
            for source in sources:
                source_name = source.get("source") or source.get("metadata", {}).get("filename", "unknown")
                unique_sources.add(source_name)
                print_info(f"  - {source_name}")
            
            if len(unique_sources) >= 2:
                print_pass(f"Diversity achieved: {len(unique_sources)} unique sources")
                return True
            else:
                print_fail(f"Low diversity: only {len(unique_sources)} unique source(s)")
                return False
        else:
            print_fail(f"Request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"Exception: {e}")
        return False

# TEST 5: Basic endpoint availability
def test_endpoints_available():
    print_test("Fix 5: Endpoint Availability")
    
    endpoints = [
        ("/", "Root"),
        ("/health", "Health"),
        ("/health/tts", "TTS Health"),
    ]
    
    all_ok = True
    for path, name in endpoints:
        try:
            time.sleep(1) # Be nice to server
            response = requests.get(f"{BASE_URL}{path}", timeout=30)
            if response.status_code == 200:
                print_pass(f"{name} endpoint: OK")
            else:
                print_fail(f"{name} endpoint: {response.status_code}")
                all_ok = False
        except Exception as e:
            print_fail(f"{name} endpoint: {e}")
            all_ok = False
    
    return all_ok

def main():
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}RAG Calling Agent - Fix Validation Suite{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    results = {}
    
    # Run all tests
    results["Endpoints"] = test_endpoints_available()
    results["Session ID"] = test_session_id_middleware()
    results["TTS Fallback"] = test_tts_fallback()
    results["Cache Dedup"] = test_cache_deduplication()
    results["Diversity"] = test_document_diversity()
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{test_name}: {status}")
    
    print(f"\n{Colors.BLUE}Total: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}✓ All fixes validated successfully!{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}✗ Some tests failed. Check logs for details.{Colors.END}")
        return 1

if __name__ == "__main__":
    exit(main())
