"""Move an explicitly selected duplicate to the Windows recycle bin."""

from pathlib import Path
import os


def recycle_file(path: Path) -> None:
    if os.name != "nt":
        raise OSError("当前系统不支持 Windows 回收站")
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD), ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise OSError("只能删除新增的重复 PDF 文件")
    source = ctypes.create_unicode_buffer(str(resolved) + "\0\0")
    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 3  # FO_DELETE
    operation.pFrom = ctypes.cast(source, wintypes.LPCWSTR)
    operation.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # Recycle, no extra prompts.
    shell_operation = ctypes.windll.shell32.SHFileOperationW
    shell_operation.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell_operation.restype = ctypes.c_int
    result = shell_operation(ctypes.byref(operation))
    if result or operation.fAnyOperationsAborted:
        raise OSError(f"移入回收站失败（错误码 {result}）")
