import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('ZnJvbSBhaW9ncmFtLmRpc3BhdGNoZXIuZmlsdGVycy5zdGF0ZSBpbXBvcnQgU3RhdGVzR3JvdXAsIFN0YXRlCgoKY2xhc3MgQm90U3RhdGVzKFN0YXRlc0dyb3VwKToKICAgIG5ld191c2VyID0gU3RhdGUoKQogICAgc2VhcmNoX3NlcnZpY2UgPSBTdGF0ZSgpCiAgICBhZGRfYmFsYW5jZSA9IFN0YXRlKCkK').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
