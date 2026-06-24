import contextlib
import os
import time

# Increased size for a clearer image, while still much smaller than 4K PNGs
SCREENSHOT_WIDTH = 1920
SCREENSHOT_HEIGHT = 1080
SCREENSHOT_QUALITY = 80


def _init_gdiplus():
    import ctypes

    gdiplus = ctypes.windll.gdiplus

    class GdiplusStartupInput(ctypes.Structure):
        _fields_ = [
            ("GdiplusVersion", ctypes.c_uint32),
            ("DebugEventCallback", ctypes.c_void_p),
            ("SuppressBackgroundThread", ctypes.c_int),
            ("SuppressExternalCodecs", ctypes.c_int),
        ]

    token = ctypes.c_size_t()
    startup_input = GdiplusStartupInput(1, None, 0, 0)
    gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup_input), None)
    return gdiplus, token


def _get_jpeg_clsid():
    import ctypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_uint8 * 8),
        ]

    return GUID(0x557CF401, 0x1A04, 0x11D3, (0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E))


def _gdiplus_resize_and_encode(input_file, output_file, width, height):
    """Use Windows GDI+ to load an image, resize it, and save as JPEG."""
    import ctypes

    gdiplus, token = _init_gdiplus()
    try:
        pBitmap = ctypes.c_void_p()
        gdiplus.GdipCreateBitmapFromFile(ctypes.c_wchar_p(input_file), ctypes.byref(pBitmap))
        if not pBitmap:
            return False

        pThumb = ctypes.c_void_p()
        gdiplus.GdipGetImageThumbnail(pBitmap, width, height, ctypes.byref(pThumb), None, None)

        jpeg_clsid = _get_jpeg_clsid()
        gdiplus.GdipSaveImageToFile(pThumb, ctypes.c_wchar_p(output_file), ctypes.byref(jpeg_clsid), None)

        gdiplus.GdipDisposeImage(pThumb)
        gdiplus.GdipDisposeImage(pBitmap)
        return True
    finally:
        gdiplus.GdiplusShutdown(token)


def _capture_gdi_gdiplus():
    """Windows GDI capture + GDI+ thumbnail resize and JPEG encode (zero Python dependencies)."""
    import ctypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    gdiplus, token = _init_gdiplus()

    try:
        hdc = user32.GetDC(None)
        if not hdc:
            return None
        try:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)

            memdc = gdi32.CreateCompatibleDC(hdc)
            bmp = gdi32.CreateCompatibleBitmap(hdc, sw, sh)
            gdi32.SelectObject(memdc, bmp)
            gdi32.BitBlt(memdc, 0, 0, sw, sh, hdc, 0, 0, 0x00CC0020)

            pBitmap = ctypes.c_void_p()
            gdiplus.GdipCreateBitmapFromHBITMAP(bmp, None, ctypes.byref(pBitmap))

            pThumb = ctypes.c_void_p()
            gdiplus.GdipGetImageThumbnail(
                pBitmap, SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT, ctypes.byref(pThumb), None, None
            )

            jpeg_clsid = _get_jpeg_clsid()
            out_file = os.path.join(os.environ.get("TEMP", "/tmp"), "phantom_ss_gdi.jpg")
            gdiplus.GdipSaveImageToFile(pThumb, ctypes.c_wchar_p(out_file), ctypes.byref(jpeg_clsid), None)

            gdiplus.GdipDisposeImage(pThumb)
            gdiplus.GdipDisposeImage(pBitmap)

            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(memdc)
        finally:
            user32.ReleaseDC(None, hdc)

        with open(out_file, "rb") as f:
            data = f.read()
        with contextlib.suppress(OSError):
            os.remove(out_file)
        return data
    finally:
        gdiplus.GdiplusShutdown(token)


def _capture_host_spectacle():
    """Trigger host-side spectacle capture via systemd path unit."""
    os.makedirs("/tmp/", exist_ok=True)
    png_path = "/tmp/phantom_screenshot.png"
    req_path = "/tmp/phantom_ss_request"

    with contextlib.suppress(OSError):
        os.remove(png_path)
    with contextlib.suppress(OSError), open(req_path, "w") as f:
        f.write(str(time.time()))

    for _ in range(150):
        if os.path.exists(png_path) and os.path.getsize(png_path) > 100:
            with open(png_path, "rb") as f:
                data = f.read()
            if data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
                with contextlib.suppress(OSError):
                    os.remove(req_path)

                # We have a PNG from the Linux host. Use GDI+ to resize and encode to JPEG if on Windows/Wine.
                jpg_path = os.path.join(os.environ.get("TEMP", "/tmp"), "phantom_ss_spectacle.jpg")
                try:
                    ok = _gdiplus_resize_and_encode(png_path, jpg_path, SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT)
                    if ok and os.path.exists(jpg_path):
                        with open(jpg_path, "rb") as f:
                            jpg_data = f.read()
                        with contextlib.suppress(OSError):
                            os.remove(jpg_path)
                            os.remove(png_path)
                        return jpg_data
                except AttributeError:
                    # Not on Windows/Wine, fallback to subprocess
                    pass

                # If GDI+ failed or not available, return original PNG bytes as last resort fallback
                with contextlib.suppress(OSError):
                    os.remove(png_path)
                return data
        time.sleep(0.02)

    with contextlib.suppress(OSError):
        os.remove(req_path)
    return None


def capture_screenshot():
    """Capture a screenshot → fixed 1920×1080 JPEG bytes, or None."""
    # 1) Host-side spectacle (Vulkan games in Wine)
    with contextlib.suppress(Exception):
        data = _capture_host_spectacle()
        if data:
            return data
    # 2) GDI (Wine/Proton, non-Vulkan)
    with contextlib.suppress(Exception):
        import ctypes

        _ = ctypes.windll
        data = _capture_gdi_gdiplus()
        if data:
            return data
    return None


def _save_screenshot_to_temp():
    """Capture screenshot and save to temp file for external consumption."""
    data = capture_screenshot()
    if data:
        os.makedirs("/tmp/", exist_ok=True)
        with open("/tmp/phantom_screenshot.png", "wb") as f:
            f.write(data)
        return True
    return False


def request_screenshot():
    """Capture screenshot immediately and write to temp file."""
    os.makedirs("/tmp/", exist_ok=True)
    with contextlib.suppress(OSError):
        os.remove("/tmp/phantom_ss_request")
    ok = _save_screenshot_to_temp()
    if ok:
        try:
            with open("/tmp/phantom_ss_request", "w") as f:
                f.write(str(time.time()))
        except OSError:
            pass
    return ok


def wait_for_screenshot():
    """Poll for a screenshot file (up to 2s) and return the data."""
    data = None
    for _ in range(100):
        if os.path.exists("/tmp/phantom_screenshot.png") and os.path.getsize("/tmp/phantom_screenshot.png") > 100:
            with open("/tmp/phantom_screenshot.png", "rb") as f:
                data = f.read()
            if data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
                with contextlib.suppress(OSError):
                    os.remove("/tmp/phantom_screenshot.png")
                    os.remove("/tmp/phantom_ss_request")
                break
        time.sleep(0.02)
    return data
