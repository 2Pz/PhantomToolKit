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

    print("Copying local folder to dist/static/local...")
    local_src = os.path.join("static", "local")
    local_dist = os.path.join("dist", "static", "local")
    if os.path.exists(local_dist):
        shutil.rmtree(local_dist)
    os.makedirs(os.path.dirname(local_dist), exist_ok=True)
    if os.path.exists(local_src):
        shutil.copytree(local_src, local_dist)
    print("Done! Local folder copied.")

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
