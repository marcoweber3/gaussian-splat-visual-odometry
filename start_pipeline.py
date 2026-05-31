from pathlib import Path
import os
import sys

repo_root = Path(__file__).resolve().parent
src_dir = repo_root / "src"

os.chdir(repo_root)
sys.path.insert(0, str(src_dir))

gui = __import__("gui")


if __name__ == "__main__":
    gui.main()
