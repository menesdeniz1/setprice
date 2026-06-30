import { useEffect, useRef } from 'react';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

export default function PriceChart({ data }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || data.length === 0) return;

    if (chartRef.current) {
      chartRef.current.destroy();
    }

    const labels = data.map(h =>
      new Date(h.recorded_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })
    );
    const prices = data.map(h => h.price);

    // Gradient fill
    const ctx = canvasRef.current.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.2)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0)');

    chartRef.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Fiyat (₺)',
          data: prices,
          borderColor: '#06B6D4',
          backgroundColor: gradient,
          borderWidth: 2.5,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#06B6D4',
          pointBorderColor: '#111827',
          pointBorderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: '#06B6D4',
          pointHoverBorderColor: 'white',
          pointHoverBorderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: 'index',
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1E293B',
            titleColor: '#94A3B8',
            bodyColor: '#F1F5F9',
            titleFont: { family: 'Inter', size: 11 },
            bodyFont: { family: 'JetBrains Mono', size: 13, weight: 'bold' },
            padding: 10,
            borderColor: 'rgba(255,255,255,0.06)',
            borderWidth: 1,
            cornerRadius: 8,
            displayColors: false,
            callbacks: {
              label: (context) => `${context.parsed.y.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ₺`,
            },
          },
        },
        scales: {
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.03)', drawBorder: false },
            ticks: {
              color: '#475569',
              font: { family: 'JetBrains Mono', size: 10 },
              callback: (value) => `${(value / 1000).toFixed(value >= 1000 ? 0 : 1)}K`,
            },
            border: { display: false },
          },
          x: {
            grid: { display: false },
            ticks: {
              color: '#475569',
              font: { family: 'Inter', size: 10 },
              maxRotation: 0,
            },
            border: { display: false },
          },
        },
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, [data]);

  return (
    <div style={{
      background: 'var(--color-bg-primary)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--color-border)',
      padding: 'var(--space-4)',
      height: '220px',
    }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
