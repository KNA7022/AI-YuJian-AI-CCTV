"""Incremental analytics shared by live overlays, charts and exported records."""
from collections import deque
from pathlib import Path
import json
import math

from .live_stats import MovementStats
from .media.files import replace_when_ready


class RallyTracker:
    """Conservative motion-based candidate rallies; manual boundaries can correct them."""
    def __init__(self, automatic=True, idle_seconds=2.0):
        self.automatic = automatic
        self.idle_seconds = idle_seconds
        self.count = 0
        self.active = False
        self.last_ball = None
        self.last_seen = None
        self.last_motion = None
        self.motion_since = None
        self.started = None
        self.intervals = []

    def start(self, timestamp, source):
        self.finish(timestamp)
        self.count += 1
        self.active = True
        self.started = timestamp
        self.source = source

    def finish(self, timestamp):
        if self.active:
            self.intervals.append({"id": self.count, "start_sec": self.started,
                                   "end_sec": timestamp, "source": self.source})
        self.active = False
        self.last_ball = self.last_seen = self.last_motion = self.motion_since = None

    def update(self, timestamp, point):
        before = self.count
        if not self.automatic:
            return False
        if point is not None:
            moving = self.last_ball is not None and math.dist(point, self.last_ball) > 2
            if moving:
                self.motion_since = self.motion_since if self.motion_since is not None else timestamp
                if not self.active and timestamp-self.motion_since >= 0.25:
                    self.start(timestamp, "automatic_estimate")
                self.last_motion = timestamp
            elif not self.active:
                self.motion_since = None
            self.last_ball = point
            self.last_seen = timestamp
        if self.active and self.last_motion is not None and timestamp-self.last_motion > self.idle_seconds:
            self.finish(self.last_motion)
        return self.count != before

    def snapshot(self):
        return {"count": self.count, "active": self.active, "started_sec": self.started,
                "mode": "automatic_estimate" if self.automatic else "manual", "completed": self.intervals}


class LiveAnalytics:
    def __init__(self, automatic=True):
        import numpy as np
        self.match = MovementStats()
        self.rally = MovementStats()
        self.rallies = RallyTracker(automatic)
        self.positions = {side: deque(maxlen=60) for side in ("upper", "lower")}
        self.grids = {scope: {side: np.zeros((134, 61), dtype=np.int64) for side in self.positions}
                      for scope in ("match", "rally")}
        self.sample_count = 0

    def reset_rally(self):
        self.rally = MovementStats()
        for grid in self.grids["rally"].values():
            grid.fill(0)

    def disconnect(self, timestamp):
        self.rallies.finish(timestamp)
        self.match.reset_continuity()
        self.rally.reset_continuity()
        for history in self.positions.values():
            history.clear()

    def update(self, players, timestamp, ball_point, manual=False):
        if manual:
            self.rallies.start(timestamp, "manual")
            self.reset_rally()
        elif self.rallies.update(timestamp, ball_point):
            self.reset_rally()
        for side, record in players.items():
            point = record["court"]
            self.match.update(side, point, timestamp)
            self.rally.update(side, point if self.rallies.active else None, timestamp)
            if point is None:
                self.positions[side].clear()
                continue
            self.positions[side].append(point)
            x, y = point
            if 0 <= x < 6.1 and 0 <= y < 13.4:
                for scope in ("match", "rally"):
                    if scope == "match" or self.rallies.active:
                        self.grids[scope][side][min(133, int(y*10)), min(60, int(x*10))] += 1
        self.sample_count += 1

    def stats(self):
        match, rally = self.match.snapshot(), self.rally.snapshot()
        return {side: {**values, "current_speed": values["speed_mps"],
                       "match_distance": values["distance_m"], "match_avg_speed": values["avg_speed_mps"],
                       "match_max_speed": values["max_speed_mps"], "rally_distance": rally[side]["distance_m"],
                       "rally_avg_speed": rally[side]["avg_speed_mps"], "rally_max_speed": rally[side]["max_speed_mps"]}
                for side, values in match.items()}

    def write_charts(self, directory, language="zh"):
        import cv2
        import numpy as np
        from .visualization.stats import StatsVisualizer
        painter = StatsVisualizer(680, 450, language)
        for scope, sides in self.grids.items():
            for kind in ("heatmap", "scatter"):
                image = np.full((450, 680, 3), (32, 38, 34), dtype=np.uint8)
                for side_index, (side, grid) in enumerate(sides.items()):
                    offset = 30 + side_index*340
                    panel = image[55:415, offset:offset+280]
                    if kind == "heatmap":
                        scaled = np.log1p(grid)
                        scaled = (scaled/max(1, scaled.max())*255).astype(np.uint8)
                        colored = cv2.applyColorMap(cv2.resize(scaled, (280, 360)), cv2.COLORMAP_TURBO)
                        panel[:] = colored
                    else:
                        ys, xs = np.nonzero(grid)
                        for x, y in zip(xs, ys):
                            cv2.circle(panel, (int(x/61*279), int(y/134*359)), 2, (70, 220, 160), -1)
                    cv2.rectangle(panel, (1, 1), (278, 358), (245, 245, 245), 1)
                    for y in (0.5, (6.7-1.98)/13.4, (6.7+1.98)/13.4):
                        cv2.line(panel, (0, int(y*360)), (279, int(y*360)), (245,245,245), 1)
                    for x in (0.46/6.1, 1-0.46/6.1):
                        cv2.line(panel, (int(x*280), 0), (int(x*280), 359), (245,245,245), 1)
                    label = ("远场球员" if side == "upper" else "近场球员") if language == "zh" else side.title()
                    painter.add_text(image, label, (offset, 18), .6, (240,240,240), 1)
                label = f"{'整场' if scope == 'match' else '当前回合'} · {'热力图' if kind == 'heatmap' else '散点图'}" if language == "zh" else f"{scope.title()} {kind}"
                painter.add_text(image, label, (30, 420), .45, (240,240,240), 1)
                ok, encoded = cv2.imencode(".jpg", image)
                if ok:
                    path = Path(directory)/f"{scope}_{kind}.jpg"
                    temp = path.with_suffix(".tmp")
                    temp.write_bytes(encoded.tobytes())
                    replace_when_ready(temp, path)
