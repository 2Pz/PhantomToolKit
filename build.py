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

    print("Creating empty items folder in dist...")
    items_dir = os.path.join("dist", "items")
    os.makedirs(items_dir, exist_ok=True)
    print("Done! Empty items folder created.")


if __name__ == "__main__":
    main()
