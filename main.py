import builtins
import configparser
import os
import sys
import threading
import time
import tomllib

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyproject.toml"), "rb") as f:
    mod_name = tomllib.load(f)["project"]["name"]


dll_path = globals().get("__dll_path__") or getattr(sys, "fspy_dll_path", None)
base_dir = os.path.dirname(os.path.abspath(dll_path)) if dll_path else os.path.dirname(os.path.abspath(__file__))
sys.fspy_base_dir = base_dir

LOG_FILE = os.path.join(base_dir, "logs", f"{mod_name}.log")


os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


INI_FILE = os.path.join(base_dir, f"{mod_name}.ini")


def load_ini():
    if not os.path.exists(INI_FILE):
        config = configparser.ConfigParser()
        config["Settings"] = {"example_setting": "true"}
        with open(INI_FILE, "w", encoding="utf-8") as f:
            config.write(f)

    config = configparser.ConfigParser()
    config.read(INI_FILE, encoding="utf-8")
    return config


config = load_ini()

try:
    with open(LOG_FILE, "w", encoding="utf-8"):
        pass
except Exception:
    pass


def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"[{mod_name}] {msg}\n")
    except Exception:
        pass


class LoggerWriter:
    def __init__(self, prefix=""):
        self.prefix = prefix

    def write(self, message):
        msg = message.rstrip()
        if not msg:
            return
        if self._is_http(msg):
            return
        if self.prefix:
            log(f"{self.prefix}{msg}")
        else:
            log(msg)

    @staticmethod
    def _is_http(msg):
        return any(m in msg for m in ('"GET ', '"POST ', '"PUT ', '"DELETE ', '"PATCH '))

    def flush(self):
        pass


sys.stdout = LoggerWriter()
sys.stderr = LoggerWriter("ERROR: ")


def start_web_server():
    log("Starting web server on http://127.0.0.1:5000")
    stop_event = getattr(builtins, "__fspy_reload_stop__", None)

    old_server = getattr(builtins, "__fspy_web_server", None)
    if old_server is not None:
        try:
            old_server.shutdown()
            log("Previous server shut down.")
        except Exception:
            pass
        builtins.__fspy_web_server = None

    try:
        import logging

        import werkzeug.serving

        log_werkzeug = logging.getLogger("werkzeug")
        log_werkzeug.setLevel(logging.ERROR)

        from backend.app import app

        server = werkzeug.serving.make_server("127.0.0.1", 5000, app)
        builtins.__fspy_web_server = server
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        log("Web server started.")

        while t.is_alive():
            if stop_event and stop_event.is_set():
                server.shutdown()
                builtins.__fspy_web_server = None
                log("Web server stopped (reload).")
                break
            time.sleep(0.5)
    except Exception as e:
        log(f"Web server failed: {e}")


def on_attach():
    stop_event = getattr(builtins, "__fspy_reload_stop__", None)
    if stop_event and not stop_event.is_set():
        log("Mod reloaded — starting fresh threads.")
    else:
        log("Mod attached successfully.")
    threading.Thread(target=start_web_server, daemon=True).start()
