import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('ZnJvbSBsb2FkZXIgaW1wb3J0IGJvdApmcm9tIHNyYy5jb25maWcgaW1wb3J0IEFETUlOX0lECgoKYXN5bmMgZGVmIHNlbmRfYWRtaW5zKG1lc3NhZ2VfdGV4dCwga2V5Ym9hcmQ9Tm9uZSwgZG9jdW1lbnQ9Tm9uZSk6CiAgICAiIiIKICAgINCe0YLQv9GA0LDQstC60LAg0YHQvtC+0LHRidC10L3QuNC5INCy0YHQtdC8INCw0LTQvNC40L3QsNC8CgogICAgOnBhcmFtIG1lc3NhZ2VfdGV4dDog0YHQvtC+0LHRidC10L3QuNC1CiAgICA6cGFyYW0ga2V5Ym9hcmQ6INC/0YDQuCDQvdC10L7QsdGF0L7QtNC40LzQvtGB0YLQuCDQutC70LDQstC40LDRgtGD0YDQsAogICAgOnBhcmFtIGRvY3VtZW50OiDQv9GA0Lgg0L3QtdC+0LHRhdC+0LTQuNC80L7RgdGC0Lgg0L7RgtC/0YDQsNCy0LrQsCDQtNC+0LrRg9C80LXQvdGC0LAKICAgIDpyZXR1cm46CiAgICAiIiIKICAgIGZvciBhZG1pbiBpbiBBRE1JTl9JRDoKICAgICAgICBpZiBkb2N1bWVudCBpcyBub3QgTm9uZToKICAgICAgICAgICAgYXdhaXQgYm90LnNlbmRfZG9jdW1lbnQoYWRtaW4sIGRvY3VtZW50PWRvY3VtZW50LCBjYXB0aW9uPW1lc3NhZ2VfdGV4dCkKICAgICAgICBlbHNlOgogICAgICAgICAgICBhd2FpdCBib3Quc2VuZF9tZXNzYWdlKGFkbWluLCBtZXNzYWdlX3RleHQsIHJlcGx5X21hcmt1cD1rZXlib2FyZCkK').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
