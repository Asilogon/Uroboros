"""Functional tests for Uroboros web_fetch tool and version endpoint."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

print('=' * 60)
print('Uroboros functional test')
print('=' * 60)

# --- Test 1: version endpoint ---
print('\n[TEST 1] /api/version endpoint')
try:
    from deepseek_gui.app import app
    client = app.test_client()
    r = client.get('/api/version')
    print(f'  status: {r.status_code}')
    data = r.get_json()
    print(f'  body: {data}')
    assert r.status_code == 200, f'expected 200, got {r.status_code}'
    assert 'version' in data, 'no version key'
    print(f'  [OK] version = {data["version"]}')
except Exception as e:
    print(f'  [FAIL] {e}')
    raise

# --- Test 2: web_fetch to example.com ---
print('\n[TEST 2] web_fetch("https://example.com")')
try:
    from deepseek_gui.web_tool import web_fetch
    res = web_fetch('https://example.com')
    print(f'  success: {res.get("success")}')
    print(f'  status_code: {res.get("status_code")}')
    print(f'  content_type: {res.get("content_type")}')
    print(f'  size: {res.get("size")} bytes')
    preview = res.get('preview', '')
    print(f'  preview (first 120 chars): {preview[:120]!r}')
    assert res.get('success'), f'fetch failed: {res.get("error")}'
    assert 'Example Domain' in preview, 'expected "Example Domain" in preview'
    print('  [OK] example.com content fetched')
except Exception as e:
    print(f'  [FAIL] {e}')
    raise

# --- Test 3: web_fetch with save_to ---
print('\n[TEST 3] web_fetch(save_to=test_downloads/example.html)')
try:
    test_proj = ROOT / 'test_project_tmp'
    test_proj.mkdir(exist_ok=True)
    res2 = web_fetch(
        'https://example.com',
        save_path='test_downloads/example.html',
        project_root=str(test_proj),
    )
    print(f'  success: {res2.get("success")}')
    print(f'  saved_path: {res2.get("saved_path")}')
    saved_file = test_proj / 'test_downloads' / 'example.html'
    assert saved_file.exists(), f'saved file missing: {saved_file}'
    size = saved_file.stat().st_size
    print(f'  saved file size: {size} bytes')
    assert size > 100, 'saved file too small'
    print('  [OK] file saved and verified')
except Exception as e:
    print(f'  [FAIL] {e}')
    raise

# --- Test 4: bad URL handling ---
print('\n[TEST 4] web_fetch with invalid URL')
try:
    r_bad = web_fetch('ftp://bad-url')
    print(f'  success: {r_bad.get("success")}')
    print(f'  error: {r_bad.get("error")}')
    assert r_bad.get('success') is False
    print('  [OK] invalid URL rejected')
except Exception as e:
    print(f'  [FAIL] {e}')
    raise

# --- Test 5: path traversal guard ---
print('\n[TEST 5] web_fetch with path traversal attempt (should fail to save outside root)')
try:
    from deepseek_gui.web_tool import _safe_project_path
    raised = False
    try:
        _safe_project_path(str(ROOT), '../../etc/passwd')
    except ValueError:
        raised = True
    assert raised, 'path traversal should have raised'
    print('  [OK] path traversal blocked')
except Exception as e:
    print(f'  [FAIL] {e}')
    raise

print('\n' + '=' * 60)
print('ALL TESTS PASSED')
print('=' * 60)
