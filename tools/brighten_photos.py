"""Brighten a slab photo: white point from the centre of the frame, one gain for all channels, gentle midtone lift."""
# Usage (repo root): python3 -I tools/brighten_photos.py photos/<Series>/<book>/*.jpg
# Rewrites each file in place under the same name (listing URLs depend on the path). Originals stay in git history.
# Used 2026-11-01 on all 110 photos: median gain 1.38, mean brightness 63 -> 101.
import sys
from PIL import Image, ImageOps

def brighten(src, dst, target=248, pct=0.995, max_gain=2.6, gamma=0.85):
    im = Image.open(src)
    exif = im.info.get("exif")
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    c = im.crop((int(w*.2), int(h*.15), int(w*.8), int(h*.85))).convert("L")
    c.thumbnail((600, 600))
    hist = c.histogram(); n = sum(hist); acc = 0
    for wp in range(256):
        acc += hist[wp]
        if acc >= pct*n: break
    gain = min(max_gain, max(1.0, target / max(wp, 1)))
    lut = [min(255, round(255 * ((min(255, i*gain))/255) ** gamma)) for i in range(256)]
    out = im.point(lut * 3)
    out.save(dst, "JPEG", quality=92, optimize=True, subsampling=0)
    return wp, gain

if __name__ == "__main__":
    import os
    for s in sys.argv[1:]:
        tmp = s + ".tmp.jpg"
        wp, g = brighten(s, tmp); os.replace(tmp, s); print(f"white point {wp:3d} gain {g:.2f}  {s}")
