import { MouseEvent, useMemo, useState } from "react";

interface CalibrationCanvasProps {
  imageUrl: string;
  corners: number[][];
  onChange: (nextCorners: number[][]) => void;
}

export function CalibrationCanvas({ imageUrl, corners, onChange }: CalibrationCanvasProps) {
  const [size, setSize] = useState({ width: 1000, height: 1000 });
  const polygon = useMemo(() => corners.map((point) => point.join(",")).join(" "), [corners]);

  function handleClick(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * size.width);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * size.height);
    if (corners.length >= 4) {
      onChange([...corners.slice(0, 3), [x, y]]);
      return;
    }
    onChange([...corners, [x, y]]);
  }

  return (
    <div className="calibration-frame">
      <div className="calibration-hint">请按顺序点击四个球场角点：左上、右上、右下、左下。</div>
      <div className="calibration-stage">
        <div className="calibration-image-shell" onClick={handleClick}>
          <img
            src={imageUrl}
            alt="标定画面"
            className="calibration-image"
            onLoad={(event) => {
              setSize({
                width: event.currentTarget.naturalWidth || 1000,
                height: event.currentTarget.naturalHeight || 1000,
              });
            }}
          />
          <svg viewBox={`0 0 ${size.width} ${size.height}`} preserveAspectRatio="none" className="calibration-overlay">
            {corners.length >= 2 && <polyline points={polygon} fill="none" stroke="var(--accent)" strokeWidth="6" />}
            {corners.length === 4 && <polygon points={polygon} fill="rgba(255, 111, 60, 0.15)" stroke="var(--accent)" strokeWidth="6" />}
            {corners.map((point, index) => (
              <g key={`${point[0]}-${point[1]}`}>
                <circle cx={point[0]} cy={point[1]} r="18" fill="var(--panel)" stroke="white" strokeWidth="4" />
                <text x={point[0]} y={point[1] + 6} textAnchor="middle" fill="white" fontSize="24">
                  {index + 1}
                </text>
              </g>
            ))}
          </svg>
        </div>
      </div>
    </div>
  );
}
