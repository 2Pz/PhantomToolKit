import configparser
import contextlib
import os
import sys


def get_base_dir():
    return getattr(sys, "fspy_base_dir", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def get_settings_path():
    return os.path.join(get_base_dir(), "phantomtoolkit.ini")


def read_language():
    path = get_settings_path()
    if os.path.exists(path):
        with contextlib.suppress(Exception):
            config = configparser.ConfigParser()
            config.read(path, encoding="utf-8")
            if "Settings" in config and "language" in config["Settings"]:
                return config["Settings"]["language"]
    return "en"


def set_language(lang):
    path = get_settings_path()
    config = configparser.ConfigParser()
    if os.path.exists(path):
        with contextlib.suppress(Exception):
            config.read(path, encoding="utf-8")
    if "Settings" not in config:
        config["Settings"] = {}
    config["Settings"]["language"] = lang
    with open(path, "w", encoding="utf-8") as f:
        config.write(f)
