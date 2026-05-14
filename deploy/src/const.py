import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('aW1wb3J0IGpzb24KCmZyb20gc3JjLmNvbmZpZyBpbXBvcnQgRElSCgpqc29uX2ZpbGUgPSBvcGVuKGYie0RJUn0vc3JjL2NvbnN0Lmpzb24iLCBlbmNvZGluZz0ndXRmLTgnKQpjb25zdF9maWxlID0ganNvbi5sb2Fkcyhqc29uX2ZpbGUucmVhZCgpKQoKY29uc3RfcnU6IGRpY3QgPSBjb25zdF9maWxlWyJydSJdCgpkZWYgaXNfY29uc3Qod29yZCk6CiAgICAiIiIKICAgINCf0YDQvtCy0LXRgNC60LAg0YHQu9C+0LLQsCDQvdCwINC60L7QvdGB0YLQsNC90YLRgwogICAgOnBhcmFtIHdvcmQ6INGB0LvQvtCy0L4KICAgIDpyZXR1cm46IHRydWUgLSDQutC+0L3RgdGC0LDQvdGC0LAsIGZhbHNlIC0g0L3QtdGCCiAgICAiIiIKICAgIGZvciB2YWx1ZSBpbiBjb25zdF9ydS52YWx1ZXMoKToKICAgICAgICBpZiB3b3JkID09IHZhbHVlOgogICAgICAgICAgICByZXR1cm4gVHJ1ZQoKICAgIHJldHVybiBGYWxzZQo=').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
