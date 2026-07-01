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
    const style = getComputedStyle(document.documentElement);
    const brandAccent = style.getPropertyValue('--color-brand-accent').trim() || '#0891B2';
    const ink = style.getPropertyValue('--color-ink').trim() || '#12161F';
    const border = style.getPropertyValue('--color-border').trim() || '#E5E7EB';
    const textSecondary = style.getPropertyValue('--color-text-secondary').trim() || '#4B5563';
    const textMuted = style.getPropertyValue('--color-text-muted').trim() || '#9CA3AF';
    const bgPrimary = style.getPropertyValue('--color-bg-primary').trim() || '#FFFFFF';

    const ctx = canvasRef.current.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(8, 145, 178, 0.18)');
    gradient.addColorStop(1, 'rgba(8, 145, 178, 0)');

    chartRef.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Fiyat (₺)',
          data: prices,
          borderColor: brandAccent,
          backgroundColor: gradient,
          borderWidth: 2.5,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: brandAccent,
          pointBorderColor: bgPrimary,
          pointBorderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: brandAccent,
          pointHoverBorderColor: bgPrimary,
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
            backgroundColor: ink,
            titleColor: textMuted,
            bodyColor: bgPrimary,
            titleFont: { family: 'Inter', size: 11 },
            bodyFont: { family: 'JetBrains Mono', size: 13, weight: 'bold' },
            padding: 10,
            borderColor: 'transparent',
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
            grid: { color: border, drawBorder: false },
            ticks: {
              color: textSecondary,
              font: { family: 'JetBrains Mono', size: 10 },
              callback: (value) => `${(value / 1000).toFixed(value >= 1000 ? 0 : 1)}K`,
            },
            border: { display: false },
          },
          x: {
            grid: { display: false },
            ticks: {
              color: textSecondary,
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
