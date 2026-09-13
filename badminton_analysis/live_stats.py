"""Timestamp-based singles statistics, independent of rendering cadence."""
import math


class MovementStats:
    def __init__(self):
        self.previous = {}
        self.totals = {side: {"distance_m": 0.0, "active_sec": 0.0, "speed_mps": 0.0, "max_speed_mps": 0.0}
                       for side in ("upper", "lower")}

    def reset_continuity(self):
        self.previous.clear()
        for value in self.totals.values():
            value["speed_mps"] = 0.0

    def update(self, side, position, timestamp):
        stats = self.totals[side]
        stats["speed_mps"] = 0.0
        if position is None:
            self.previous.pop(side, None)
            return
        old = self.previous.get(side)
        if old is not None and timestamp <= old[1]:
            return
        self.previous[side] = (position, timestamp)
        if old is None:
            return
        dt = timestamp - old[1]
        distance = math.dist(position, old[0])
        if dt > 1.0 or distance / dt > 8.0:
            return
        stats["active_sec"] += dt
        if distance < 0.03:
            return
        speed = distance / dt
        stats["distance_m"] += distance
        stats["speed_mps"] = speed
        stats["max_speed_mps"] = max(stats["max_speed_mps"], speed)

    def snapshot(self):
        return {side: {**{key: round(value, 3) for key, value in stats.items()},
                       "avg_speed_mps": round(stats["distance_m"] / stats["active_sec"], 3) if stats["active_sec"] else 0}
                for side, stats in self.totals.items()}
