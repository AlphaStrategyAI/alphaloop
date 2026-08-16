import { useEffect, useRef } from "react";
import { Chart, registerables } from "chart.js";
import type { RadarPoint } from "../types";
import { radarDrawOptions } from "../animations/radarDraw";

Chart.register(...registerables);

interface Props {
  data: RadarPoint[];
  compareData?: RadarPoint[] | null;
  height?: number;
}

export function RadarChart({ data, compareData, height = 320 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;

    if (chartRef.current) {
      chartRef.current.destroy();
    }

    const labels = data.map((d) => d.axis);
    const values = data.map((d) => d.value);

    const datasets: any[] = [
      {
        label: "Pass-rate",
        data: values,
        backgroundColor: "rgba(91,108,255,0.2)",
        borderColor: "#5b6cff",
        borderWidth: 2,
        pointBackgroundColor: "#5b6cff",
        pointRadius: 4,
      },
    ];

    if (compareData && compareData.length > 0) {
      datasets.push({
        label: "Compare",
        data: compareData.map((d) => d.value),
        backgroundColor: "rgba(245,158,11,0.15)",
        borderColor: "#f59e0b",
        borderWidth: 1.5,
        pointBackgroundColor: "#f59e0b",
        pointRadius: 3,
        borderDash: [4, 4],
      });
    }

    chartRef.current = new Chart(ctx, {
      type: "radar",
      data: { labels, datasets },
      options: {
        ...radarDrawOptions,
        scales: {
          r: {
            beginAtZero: true,
            min: 0,
            max: 1,
            ticks: {
              color: "#5c6573",
              backdropColor: "transparent",
            },
            grid: { color: "#2a3142" },
            angleLines: { color: "#2a3142" },
            pointLabels: { color: "#e5e9f0", font: { family: "JetBrains Mono", size: 11 } },
          },
        },
        plugins: {
          legend: {
            labels: { color: "#e5e9f0", font: { family: "JetBrains Mono" } },
          },
        },
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [data, compareData]);

  return (
    <div style={{ height }} data-testid="radar-chart">
      <canvas ref={canvasRef} />
    </div>
  );
}

export default RadarChart;
