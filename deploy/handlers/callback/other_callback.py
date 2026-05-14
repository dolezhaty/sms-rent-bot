import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('ZnJvbSBhaW9ncmFtIGltcG9ydCB0eXBlcwpmcm9tIGFpb2dyYW0uZGlzcGF0Y2hlci5maWx0ZXJzIGltcG9ydCBSZWdleHAKCmZyb20gbG9hZGVyIGltcG9ydCBkcAoKQGRwLmNhbGxiYWNrX3F1ZXJ5X2hhbmRsZXIoUmVnZXhwKCJjbG9zZSIpKQphc3luYyBkZWYgY2xvc2VfY2FsbGJhY2soY2FsbDogdHlwZXMuQ2FsbGJhY2tRdWVyeSk6CiAgICAiIiIKICAgINCj0LTQsNC70LXQvdC40LUg0YLQtdC60YPRidC10LPQviDRgdC+0L7QsdGJ0LXQvdC40Y8KCiAgICA6cGFyYW0gY2FsbDoKICAgIDpyZXR1cm46CiAgICAiIiIKICAgIGF3YWl0IGNhbGwubWVzc2FnZS5kZWxldGUoKQo=').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
