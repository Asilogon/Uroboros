"""Find red-highlighted regions in a screenshot and analyze them."""
import sys
from pathlib import Path
from collections import Counter

from PIL import Image


def find_red_regions(img_path: Path):
    img = Image.open(img_path).convert('RGB')
    w, h = img.size
    print(f'[IMAGE] {img_path.name}: {w}x{h}')

    pixels = img.load()
    # Sample every 2 pixels for speed
    red_pixels = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = pixels[x, y]
            # "Pure red" / highlight red: strong R, low G, low B
            if r > 180 and g < 100 and b < 100:
                red_pixels.append((x, y))

    if not red_pixels:
        print('[NO-RED] No bright red pixels found')
        return None

    xs = [p[0] for p in red_pixels]
    ys = [p[1] for p in red_pixels]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    print(f'[RED-BBOX] x={minx}..{maxx} y={miny}..{maxy} (width={maxx-minx+1}, height={maxy-miny+1})')
    print(f'[RED-PIXELS] sampled={len(red_pixels)}')

    # Save cropped region (with small padding)
    pad = 5
    crop = img.crop((max(0, minx - pad), max(0, miny - pad), min(w, maxx + pad), min(h, maxy + pad)))
    crop_path = img_path.parent / f'red_region_{img_path.stem}.png'
    crop.save(crop_path)
    print(f'[CROP-SAVED] {crop_path} ({crop.size[0]}x{crop.size[1]})')

    # Analyze dominant colors in crop
    small = crop.resize((min(200, crop.size[0]), min(200, crop.size[1])))
    colors = Counter(small.getdata())
    print('[TOP-COLORS-IN-CROP]')
    for color, count in colors.most_common(8):
        print(f'  {color}: {count}')

    # Very rough cluster detection: split the crop into horizontal bands and report
    # number of red pixels per band (helps understand if it's text-like or block-like).
    print('[RED-DENSITY-BY-BAND]')
    nbands = 10
    band_h = max(1, (maxy - miny + 1) // nbands)
    for i in range(nbands):
        y0 = miny + i * band_h
        y1 = min(maxy + 1, y0 + band_h)
        cnt = sum(1 for (x, y) in red_pixels if y0 <= y < y1)
        bar = '#' * min(60, cnt // 5)
        print(f'  y={y0:4}..{y1:4} ({cnt:5} px) {bar}')

    return (minx, miny, maxx, maxy, len(red_pixels))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        # Latest pasted image
        files = sorted(
            Path('logs/files').glob('pasted_*.png'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            print('No pasted_*.png in logs/files/')
            sys.exit(1)
        target = files[0]

    find_red_regions(target)
