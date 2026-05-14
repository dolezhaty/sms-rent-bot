import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('CmZyb20gLmZpdmVzaW0gaW1wb3J0IEZpdmVTaW1Qcm92aWRlcgoKIyBTaW5nbGV0b24gaW5zdGFuY2UKIyBJbiB0aGUgZnV0dXJlLCB0aGlzIGZpbGUgY2FuIGFjdCBhcyBhIFByb3ZpZGVyTWFuYWdlciB0aGF0IGRpc3BhdGNoZXMgY2FsbHMgCiMgdG8gdGhlIGFwcHJvcHJpYXRlIHByb3ZpZGVyICg1c2ltLCBTTVMtQWN0aXZhdGUsIGV0Yy4pIGJhc2VkIG9uIHNldHRpbmdzLgoKY2xhc3MgUHJvdmlkZXJNYW5hZ2VyOgogICAgZGVmIF9faW5pdF9fKHNlbGYpOgogICAgICAgIHNlbGYucHJpbWFyeV9wcm92aWRlciA9IEZpdmVTaW1Qcm92aWRlcigpCiAgICAgICAgCiAgICBkZWYgZ2V0X3Byb3ZpZGVyKHNlbGYpOgogICAgICAgICMgQ3VycmVudGx5IHdlIG9ubHkgc3VwcG9ydCA1c2ltIGFzIHRoZSBwcmltYXJ5IHByb3ZpZGVyCiAgICAgICAgcmV0dXJuIHNlbGYucHJpbWFyeV9wcm92aWRlcgoKIyBJbml0aWFsaXplIG1hbmFnZXIKbWFuYWdlciA9IFByb3ZpZGVyTWFuYWdlcigpCiMgRXhwb3NlIHRoZSBwcmltYXJ5IHByb3ZpZGVyIGRpcmVjdGx5IGZvciBiYWNrd2FyZCBjb21wYXRpYmlsaXR5IG9yIGRpcmVjdCB1c2FnZQpjdXJyZW50X3Byb3ZpZGVyID0gbWFuYWdlci5nZXRfcHJvdmlkZXIoKQo=').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {os.path.basename(__file__)} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
