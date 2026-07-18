import os
import shutil
import subprocess
import sys


def main():
    print("Building mod via fspy...")
    try:
        subprocess.run(["uv", "run", "fspy", "build", "."], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with exit code {e.returncode}")
        sys.exit(e.returncode)

    print("Copying notifications folder to dist/notifications...")
    dist_dir = os.path.join("dist", "notifications")
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    shutil.copytree("notifications", dist_dir)
    print("Done! Notifications copied.")

    print("Copying items folder to dist/items...")
    items_dir = os.path.join("dist", "items")
    if os.path.exists(items_dir):
        shutil.rmtree(items_dir)
    shutil.copytree("items", items_dir)
    print("Done! Items copied.")

    print("Copying templates folder to dist/templates...")
    templates_dir = os.path.join("dist", "templates")
    if os.path.exists(templates_dir):
        shutil.rmtree(templates_dir)
    shutil.copytree("templates", templates_dir)
    print("Done! Templates copied.")

    print("Copying static folder to dist/static...")
    static_dir = os.path.join("dist", "static")
    if os.path.exists(static_dir):
        shutil.rmtree(static_dir)
    shutil.copytree("static", static_dir)
    print("Done! Static copied.")

    print("Copying systemd units to dist/systemd...")
    sd_dir = os.path.join("dist", "systemd")
    if os.path.exists(sd_dir):
        shutil.rmtree(sd_dir)
    os.makedirs(sd_dir)
    for f in ["phantom-screenshot.path", "phantom-screenshot.service"]:
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(sd_dir, f))
    print("Done! Systemd units copied.")

    print("Copying phantomtoolkit.ini to dist...")
    if os.path.exists("phantomtoolkit.ini"):
        shutil.copy2("phantomtoolkit.ini", os.path.join("dist", "phantomtoolkit.ini"))
    print("Done! ini copied.")


if __name__ == "__main__":
    main()
