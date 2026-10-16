"""Export every SVG under assets/<topic>/ to a 2x PNG with headless Edge.

Usage: python export_png.py [topic ...]   (no args = all topics)
cairosvg lacks the cairo DLL on this machine, so we screenshot with Edge.
"""
import re
import subprocess
import sys
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ASSETS = Path(__file__).resolve().parent.parent


def size_of(svg: Path) -> tuple[int, int]:
    head = svg.read_text(encoding="utf-8")[:400]
    w = int(re.search(r'width="(\d+)"', head).group(1))
    h = int(re.search(r'height="(\d+)"', head).group(1))
    return w, h


def export(svg: Path) -> None:
    w, h = size_of(svg)
    png = svg.with_suffix(".png")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", f"--window-size={w},{h}",
                    f"--screenshot={png}", svg.as_uri()],
                   check=True, capture_output=True, timeout=60)
    print("png", png.name)


def main() -> None:
    """Args are topic names under assets/, or paths to any directory of SVGs."""
    topics = sys.argv[1:] or [p.name for p in ASSETS.iterdir() if p.is_dir() and p.name != "src"]
    for t in topics:
        folder = Path(t) if Path(t).is_dir() else ASSETS / t
        for svg in sorted(folder.glob("*.svg")):
            export(svg)


if __name__ == "__main__":
    main()
