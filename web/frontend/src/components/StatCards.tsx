import { SessionSummary } from "../types";

interface StatCardsProps {
  summary?: SessionSummary;
}

export function StatCards({ summary }: StatCardsProps) {
  const cards = [
    { label: "回合数", value: summary?.stats.rallies ?? "--" },
    { label: "FPS", value: summary?.stats.fps?.toFixed(1) ?? "--" },
    { label: "处理耗时", value: summary ? `${summary.processing_time_sec}s` : "--" },
    {
      label: "分辨率",
      value: summary ? `${summary.stats.frame_width}×${summary.stats.frame_height}` : "--",
    },
  ];

  return (
    <section className="cards-grid">
      {cards.map((card) => (
        <article className="stat-card" key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </article>
      ))}
    </section>
  );
}
