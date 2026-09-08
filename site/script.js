const sales = [
  35491.94, 46100.9, 43418.22, 37836.09, 36284.84, 42420.21,
  53574.38, 52556.67, 36487.3, 60340.76, 46959.68, 30596.87,
  35307.51, 39348.55, 45937.96, 56941.39, 53076.89, 42117.13,
  50362.76, 39526.68, 56970.09, 49766.15, 66393.19,
];

function drawSalesChart() {
  const host = document.querySelector("#sales-chart");
  if (!host) return;

  const width = 720;
  const height = 230;
  const max = Math.max(...sales);
  const min = Math.min(...sales);
  const points = sales.map((value, index) => {
    const x = (index / (sales.length - 1)) * width;
    const y = height - 18 - ((value - min) / (max - min)) * (height - 45);
    return [x, y];
  });
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  const peakIndex = sales.indexOf(max);
  const [peakX, peakY] = points[peakIndex];

  host.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#c7d956" stop-opacity=".34" />
          <stop offset="100%" stop-color="#c7d956" stop-opacity="0" />
        </linearGradient>
      </defs>
      <line x1="0" y1="60" x2="720" y2="60" stroke="rgba(255,255,255,.1)" />
      <line x1="0" y1="125" x2="720" y2="125" stroke="rgba(255,255,255,.1)" />
      <polygon points="${area}" fill="url(#area-fill)" />
      <polyline points="${line}" fill="none" stroke="#c7d956" stroke-width="3" vector-effect="non-scaling-stroke" />
      <circle cx="${peakX}" cy="${peakY}" r="5" fill="#ff7440" vector-effect="non-scaling-stroke" />
      <text x="${Math.min(peakX + 12, 620)}" y="${Math.max(peakY - 10, 16)}" fill="#f4f0e7" font-family="DM Mono, monospace" font-size="12">$${(max / 1000).toFixed(1)}k peak</text>
    </svg>`;
}

function revealOnScroll() {
  const items = document.querySelectorAll(".reveal");
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    items.forEach((item) => item.classList.add("visible"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  items.forEach((item) => observer.observe(item));
}

drawSalesChart();
revealOnScroll();
