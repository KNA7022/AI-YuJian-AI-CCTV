"""Analyze a camera snapshot to locate the court boundary lines.

Reads the snapshot produced by the live API, detects the bright court surface and
white line structure, then writes a diagnostic overlay with candidate corners so a
human can confirm them visually.

Usage: python scripts/analyze_court_lines.py [snapshot.jpg] [out_overlay.jpg]
"""
import sys
from pathlib import Path

import cv2
import numpy as np

SNAPSHOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".runtime/verify/app_snapshot.jpg")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else ".runtime/verify/court_overlay.jpg")


def main() -> int:
    image = cv2.imread(str(SNAPSHOT))
    if image is None:
        print(f"cannot read {SNAPSHOT}")
        return 1
    height, width = image.shape[:2]
    print(f"image: {width}x{height}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # The court is the brightest large region; find it by Otsu on a blurred image.
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)
    _, bright = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((25, 25), np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"bright-region contours: {len(contours)}")
    if not contours:
        return 1
    largest = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(largest) / (width * height)
    print(f"largest bright region area ratio: {area_ratio:.3f}")

    # White line detection: high local contrast, near-white pixels.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, 175), (180, 60, 255))
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    print(f"near-white pixel ratio: {float(white.mean())/255:.4f}")

    # Long straight lines via probabilistic Hough on Canny edges.
    edges = cv2.Canny(blurred, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=140, minLineLength=int(min(width, height) * 0.18),
                            maxLineGap=40)
    print(f"long lines detected: {0 if lines is None else len(lines)}")

    overlay = image.copy()
    cv2.drawContours(overlay, [largest], -1, (0, 255, 255), 3)
    if lines is not None:
        for line in lines[:80]:
            x1, y1, x2, y2 = line[0]
            cv2.line(overlay, (x1, y1), (x2, y2), (255, 0, 255), 2)
    cv2.putText(overlay, "yellow=largest bright region, magenta=long lines", (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3, cv2.LINE_AA)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), overlay)
    print(f"wrote diagnostic overlay: {OUT}")

    # Row/column brightness profiles help locate the court's extents in the frame.
    column_mean = gray.mean(axis=0)
    row_mean = gray.mean(axis=1)
    top_rows = np.argsort(row_mean)[-5:]
    print(f"brightest rows (y): {sorted(int(r) for r in top_rows)}")
    print(f"row brightness range: {row_mean.min():.0f}..{row_mean.max():.0f}")
    print(f"column brightness range: {column_mean.min():.0f}..{column_mean.max():.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
