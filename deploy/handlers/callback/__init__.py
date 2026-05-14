import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('ZnJvbSBoYW5kbGVycy5jYWxsYmFjay5hZG1pbl9jYWxsYmFjayBpbXBvcnQgZHAKZnJvbSBoYW5kbGVycy5jYWxsYmFjay5vdGhlcl9jYWxsYmFjayBpbXBvcnQgZHAKZnJvbSBoYW5kbGVycy5jYWxsYmFjay51c2VyX2NhbGxiYWNrIGltcG9ydCBkcApmcm9tIGhhbmRsZXJzLmNhbGxiYWNrLm9yZGVyX2NhbGxiYWNrIGltcG9ydCBkcAoKX19hbGxfXyA9IFsiZHAiXQo=').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
