import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('ZnJvbSBoYW5kbGVycy5tZXNzYWdlLnVzZXJfbWVzc2FnZSBpbXBvcnQgZHAKZnJvbSBoYW5kbGVycy5tZXNzYWdlLmJhbGFuY2VfbWVzc2FnZSBpbXBvcnQgZHAKZnJvbSBoYW5kbGVycy5tZXNzYWdlLmFkbWluX21lc3NhZ2UgaW1wb3J0IGRwCmZyb20gaGFuZGxlcnMubWVzc2FnZS5vdGhlcl9tZXNzYWdlIGltcG9ydCBkcAoKX19hbGxfXyA9IFsiZHAiXQo=').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
