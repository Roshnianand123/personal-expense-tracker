let categoryChartInstance = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today in form
    const dateInput = document.getElementById('date');
    if (dateInput && !dateInput.value) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }

    // Initial fetch of chart data & summary KPIs
    loadSummaryData();
    loadChartData();

    // Attach refresh button listener
    const refreshBtn = document.getElementById('btn-refresh-chart');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadSummaryData();
            loadChartData();
        });
    }
});

/**
 * Fetches aggregate totals from /summary and updates KPI cards
 */
async function loadSummaryData() {
    try {
        const response = await fetch('/summary');
        if (!response.ok) {
            throw new Error(`Summary fetch failed: ${response.status}`);
        }
        const data = await response.json();

        const totalEl = document.getElementById('kpi-total');
        const countEl = document.getElementById('kpi-count');
        const topCatEl = document.getElementById('kpi-top-category');

        if (totalEl) {
            totalEl.textContent = `$${data.total_amount.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            })}`;
        }

        if (countEl) {
            countEl.textContent = data.transaction_count.toString();
        }

        if (topCatEl) {
            const categories = data.by_category || {};
            const keys = Object.keys(categories);
            if (keys.length > 0) {
                // Find category with highest spend
                let maxCat = keys[0];
                let maxVal = categories[maxCat];
                for (const cat of keys) {
                    if (categories[cat] > maxVal) {
                        maxVal = categories[cat];
                        maxCat = cat;
                    }
                }
                topCatEl.textContent = `${maxCat} ($${maxVal.toFixed(2)})`;
            } else {
                topCatEl.textContent = 'None';
            }
        }
    } catch (err) {
        console.error('Error loading summary data:', err);
    }
}

/**
 * Fetches aggregated data from /chart-data and renders the Chart.js bar chart
 */
async function loadChartData() {
    const canvas = document.getElementById('categoryChart');
    const emptyState = document.getElementById('chart-empty-state');
    if (!canvas) return;

    try {
        const response = await fetch('/chart-data');
        if (!response.ok) {
            throw new Error(`Chart data fetch failed: ${response.status}`);
        }
        const chartData = await response.json();

        const labels = chartData.labels || [];
        const values = (chartData.datasets && chartData.datasets[0]) ? chartData.datasets[0].data : [];

        if (labels.length === 0 || values.length === 0) {
            canvas.style.display = 'none';
            if (emptyState) emptyState.style.display = 'flex';
            if (categoryChartInstance) {
                categoryChartInstance.destroy();
                categoryChartInstance = null;
            }
            return;
        }

        canvas.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';

        // Vibrant palette for categories
        const palette = [
            'rgba(99, 102, 241, 0.85)',   // Indigo
            'rgba(16, 185, 129, 0.85)',   // Emerald
            'rgba(244, 63, 94, 0.85)',    // Rose
            'rgba(245, 158, 11, 0.85)',   // Amber
            'rgba(14, 165, 233, 0.85)',   // Sky
            'rgba(168, 85, 247, 0.85)',   // Purple
            'rgba(236, 72, 153, 0.85)',   // Pink
            'rgba(20, 184, 166, 0.85)'    // Teal
        ];

        const borderPalette = palette.map(color => color.replace('0.85', '1.0'));
        const bgColors = labels.map((_, i) => palette[i % palette.length]);
        const borderColors = labels.map((_, i) => borderPalette[i % borderPalette.length]);

        const ctx = canvas.getContext('2d');

        if (categoryChartInstance) {
            categoryChartInstance.data.labels = labels;
            categoryChartInstance.data.datasets[0].data = values;
            categoryChartInstance.data.datasets[0].backgroundColor = bgColors;
            categoryChartInstance.data.datasets[0].borderColor = borderColors;
            categoryChartInstance.update();
        } else {
            categoryChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Amount ($)',
                        data: values,
                        backgroundColor: bgColors,
                        borderColor: borderColors,
                        borderWidth: 1.5,
                        borderRadius: 8,
                        maxBarThickness: 45
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 750,
                        easing: 'easeOutQuart'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleColor: '#f8fafc',
                            bodyColor: '#cbd5e1',
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 6,
                            usePointStyle: true,
                            callbacks: {
                                label: function (context) {
                                    return ` $${context.parsed.y.toFixed(2)}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: {
                                    family: "'Plus Jakarta Sans', sans-serif",
                                    size: 11
                                }
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.06)'
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: {
                                    family: "'Plus Jakarta Sans', sans-serif",
                                    size: 11
                                },
                                callback: function (value) {
                                    return '$' + value;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (err) {
        console.error('Error loading chart data:', err);
    }
}
