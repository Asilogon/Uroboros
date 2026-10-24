"""Cluster red pixels to identify highlighted UI regions."""
from pathlib import Path
from PIL import Image
import sys


def clusters_from_red(img_path: Path, min_size: int = 30):
    img = Image.open(img_path).convert('RGB')
    w, h = img.size
    print(f'[IMAGE] {img_path.name}: {w}x{h}')
    pixels = img.load()

    # Collect all red pixels (full sampling)
    red = []
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if r > 180 and g < 100 and b < 100:
                red.append((x, y))
    if not red:
        print('no red pixels')
        return

    # Union-find to cluster
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    red_set = set(red)
    for p in red:
        parent[p] = p

    for x, y in red:
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx == 0 and dy == 0:
                    continue
                n = (x + dx, y + dy)
                if n in red_set:
                    union((x, y), n)

    # Group by root
    groups = {}
    for p in red:
        r = find(p)
        groups.setdefault(r, []).append(p)

    clusters = []
    for members in groups.values():
        if len(members) < min_size:
            continue
        xs = [m[0] for m in members]
        ys = [m[1] for m in members]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        # Filter very thin (single-pixel) clusters that are pure lines
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        clusters.append((x0, y0, x1, y1, bw, bh, len(members)))

    clusters.sort(key=lambda c: (c[1], c[0]))
    print(f'\n[CLUSTERS] found {len(clusters)} clusters:')
    for i, (x0, y0, x1, y1, bw, bh, cnt) in enumerate(clusters, 1):
        print(f'  #{i}: bbox=({x0},{y0})..({x1},{y1}) size={bw}x{bh} pixels={cnt}')
        # Save crop
        crop = img.crop((max(0, x0 - 5), max(0, y0 - 5), min(w, x1 + 5), min(h, y1 + 5)))
        crop_path = img_path.parent / f'red_cluster_{i}_{img_path.stem}.png'
        crop.save(crop_path)

    # Also crop each horizontal band
    print('\n[ALL-RED-CROP]')
    xs = [r[0] for r in red]
    ys = [r[1] for r in red]
    all_crop = img.crop((max(0, min(xs) - 5), max(0, min(ys) - 5), min(w, max(xs) + 5), min(h, max(ys) + 5)))
    all_crop_path = img_path.parent / f'red_ALL_{img_path.stem}.png'
    all_crop.save(all_crop_path)
    print(f'  {all_crop_path}')

    return clusters


if __name__ == '__main__':
    files = sorted(
        Path('logs/files').glob('pasted_*.png'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else files[0]
    clusters_from_red(target)
