"""Turn a list of SVG frames into a GIF: Edge headless screenshots + PIL with a shared palette.

Used by anims.py. Frames are rendered at 1x (GIF size), in parallel.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def _shot(svg_path: Path, w: int, h: int) -> Path:
    png = svg_path.with_suffix(".png")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={svg_path.parent / ('prof_' + svg_path.stem)}",
                    "--force-device-scale-factor=1", f"--window-size={w},{h}",
                    f"--screenshot={png}", svg_path.as_uri()],
                   check=True, capture_output=True, timeout=120)
    return png


def make_gif(frames: list[str], durations: list[int], dst: Path, colors: int = 96) -> None:
    """frames: SVG strings (same size); durations: ms per frame."""
    assert len(frames) == len(durations)
    w = int(re.search(r'width="(\d+)"', frames[0]).group(1))
    h = int(re.search(r'height="(\d+)"', frames[0]).group(1))
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i, f in enumerate(frames):
            p = Path(tmp) / f"f{i:04d}.svg"
            p.write_text(f, encoding="utf-8")
            paths.append(p)
        with ThreadPoolExecutor(max_workers=8) as ex:
            pngs = list(ex.map(lambda p: _shot(p, w, h), paths))
        imgs = [Image.open(p).convert("RGB") for p in pngs]
    # shared palette from first / middle / last frames, no dithering (flat colors stay flat)
    probe = Image.new("RGB", (w, h * 3))
    for k, im in enumerate([imgs[0], imgs[len(imgs) // 2], imgs[-1]]):
        probe.paste(im, (0, k * h))
    pal = probe.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    dst.parent.mkdir(parents=True, exist_ok=True)
    q[0].save(dst, save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=True)
    print("gif", dst.name, len(frames), "frames", dst.stat().st_size // 1024, "KB")


def contact_sheet(gif: Path, out: Path, n: int = 6) -> None:
    im = Image.open(gif)
    w, h = im.size
    sheet = Image.new("RGB", (w * 2, h * ((n + 1) // 2)), "white")
    for k in range(n):
        im.seek(int(k * (im.n_frames - 1) / (n - 1)))
        sheet.paste(im.convert("RGB"), ((k % 2) * w, (k // 2) * h))
    sheet.save(out)
