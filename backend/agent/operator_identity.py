"""OS identity for the privileged local operator; never accept a reviewer label."""

import os


def operator_identity() -> str:
    if os.name != "nt":
        return f"uid:{os.getuid()}"
    import ctypes
    from ctypes import wintypes

    function = ctypes.WinDLL("secur32", use_last_error=True).GetUserNameExW
    function.argtypes = [ctypes.c_int, wintypes.LPWSTR, ctypes.POINTER(wintypes.ULONG)]
    function.restype = wintypes.BOOLEAN
    size = wintypes.ULONG(0)
    function(2, None, ctypes.byref(size))  # NameSamCompatible: DOMAIN\account
    if not size.value:
        raise RuntimeError("The operating-system operator identity is unavailable")
    buffer = ctypes.create_unicode_buffer(size.value)
    if not function(2, buffer, ctypes.byref(size)):
        raise RuntimeError("The operating-system operator identity is unavailable")
    return "windows:" + buffer.value.casefold()
