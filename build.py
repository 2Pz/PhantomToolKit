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


if __name__ == "__main__":
    main()
