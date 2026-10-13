"""Build a clean GIF from a PNG frame sequence (shared palette, no dithering)."""
import sys
from pathlib import Path

from PIL import Image

import av

video, dst, fps = sys.argv[1], sys.argv[2], int(sys.argv[3])
with av.open(video) as container:
    frames = [fr.to_image().convert("RGB") for fr in container.decode(video=0)]
print("frames", len(frames), "size", frames[0].size)

# 用首、中、尾三帧拼图生成一个共享调色板，保证所有颜色都被覆盖
w, h = frames[0].size
probe = Image.new("RGB", (w, h * 3))
for i, f in enumerate([frames[0], frames[len(frames) // 2], frames[-1]]):
    probe.paste(f, (0, i * h))
palette = probe.quantize(colors=64, method=Image.Quantize.MEDIANCUT)

q = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
q[0].save(dst, save_all=True, append_images=q[1:], duration=int(1000 / fps), loop=0, optimize=True)

sheet = Image.new("RGB", (w * 2, h * 3), "white")
check = Image.open(dst)
idx = [int(i * (check.n_frames - 1) / 5) for i in range(6)]
for k, i in enumerate(idx):
    check.seek(i)
    sheet.paste(check.convert("RGB"), ((k % 2) * w, (k // 2) * h))
sheet.save(Path(dst).with_name("contact_sheet.png"))
print("written", dst, Path(dst).stat().st_size // 1024, "KB")
