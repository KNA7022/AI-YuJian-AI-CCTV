"""Derive a 4-corner court quadrilateral from the bright court region.

Prints the candidate corners as a JSON array suitable for the calibration API and
writes an overlay showing the fitted quadrilateral for human confirmation.

Usage: python scripts/fit_court_quad.py [snapshot.jpg] [out_overlay.jpg]
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

SNAPSHOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".runtime/verify/app_snapshot.jpg")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else ".runtime/verify/court_quad.jpg")


def order_corners(points):
    """Order as top-left, top-right, bottom-right, bottom-left."""
    points = np.array(points, dtype=np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).ravel()
    ordered[0] = points[np.argmin(total)]
    ordered[2] = points[np.argmax(total)]
    ordered[1] = points[np.argmin(diff)]
    ordered[3] = points[np.argmax(diff)]
    return ordered


def main() -> int:
    image = cv2.imread(str(SNAPSHOT))
    if image is None:
        print(f"cannot read {SNAPSHOT}")
        return 1
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)
    _, bright = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((25, 25), np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea)

    perimeter = cv2.arcLength(largest, True)
    quad = None
    for epsilon in np.linspace(0.005, 0.06, 40):
        approx = cv2.approxPolyDP(largest, epsilon * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2)
            print(f"fitted quadrilateral at epsilon={epsilon:.4f}")
            break
    if quad is None:
        hull = cv2.convexHull(largest).reshape(-1, 2)
        print("no clean 4-gon found; falling back to convex-hull extremes")
        sums = hull.sum(axis=1)
        diffs = np.diff(hull, axis=1).ravel()
        quad = np.array([hull[np.argmin(sums)], hull[np.argmin(diffs)],
                         hull[np.argmax(sums)], hull[np.argmax(diffs)]], dtype=np.float32)

    ordered = order_corners(quad)
    corners = [[int(round(x)), int(round(y))] for x, y in ordered]
    print("candidate corners (TL, TR, BR, BL):", json.dumps(corners))

    area = cv2.contourArea(ordered.astype(np.float32))
    print(f"quad area ratio: {area/(width*height):.3f}")
    print(f"image bounds check: all_inside="
          f"{all(0 <= x < width and 0 <= y < height for x, y in corners)}")

    overlay = image.copy()
    cv2.polylines(overlay, [ordered.astype(np.int32)], True, (0, 255, 255), 4)
    for index, (x, y) in enumerate(corners, start=1):
        cv2.circle(overlay, (x, y), 14, (0, 0, 255), -1)
        cv2.putText(overlay, str(index), (x + 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4, cv2.LINE_AA)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), overlay)
    print(f"wrote overlay: {OUT}")
    Path(".runtime/verify/corners.json").write_text(json.dumps(corners), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
