/**
 * BIAR Protocol - Chart Components
 * Real-time probability charts using Chart.js
 */

let probabilityChart = null;
let volumeChart = null;

/**
 * Initialize probability chart for a market
 */
function initProbabilityChart(ctx, outcomes, initialProbabilities) {
    if (probabilityChart) {
        probabilityChart.destroy();
    }

    const colors = [
        'rgba(99, 102, 241, 0.8)',
        'rgba(139, 92, 246, 0.8)',
        'rgba(6, 182, 212, 0.8)',
        'rgba(236, 72, 153, 0.8)'
    ];

    probabilityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: outcomes.map((outcome, index) => ({
                label: outcome,
                data: [],
                borderColor: colors[index % colors.length],
                backgroundColor: colors[index % colors.length].replace('0.8', '0.2'),
                tension: 0.4,
                fill: true
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#94a3b8'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(30, 41, 59, 0.9)',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: '#475569',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 1,
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => `${(value * 100).toFixed(0)}%`
                    },
                    grid: {
                        color: '#334155'
                    }
                },
                x: {
                    ticks: {
                        color: '#94a3b8'
                    },
                    grid: {
                        color: '#334155'
                    }
                }
            }
        }
    });

    // Add initial data point
    addProbabilityDataPoint(initialProbabilities);

    return probabilityChart;
}

/**
 * Add new data point to probability chart
 */
function addProbabilityDataPoint(probabilities) {
    if (!probabilityChart) return;

    const now = new Date();
    const timeLabel = now.toLocaleTimeString();

    // Add to all datasets
    probabilityChart.data.labels.push(timeLabel);
    
    Object.values(probabilities).forEach((prob, index) => {
        if (probabilityChart.data.datasets[index]) {
            probabilityChart.data.datasets[index].data.push(prob);
        }
    });

    // Keep only last 20 data points
    if (probabilityChart.data.labels.length > 20) {
        probabilityChart.data.labels.shift();
        probabilityChart.data.datasets.forEach(dataset => dataset.data.shift());
    }

    probabilityChart.update('none'); // Update without animation
}

/**
 * Initialize volume chart
 */
function initVolumeChart(ctx, historicalData = []) {
    if (volumeChart) {
        volumeChart.destroy();
    }

    volumeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: historicalData.map(d => d.date),
            datasets: [{
                label: 'Volume (USDC)',
                data: historicalData.map(d => d.volume),
                backgroundColor: 'rgba(99, 102, 241, 0.6)',
                borderColor: 'rgba(99, 102, 241, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => `$${value.toLocaleString()}`
                    },
                    grid: {
                        color: '#334155'
                    }
                },
                x: {
                    ticks: {
                        color: '#94a3b8'
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });

    return volumeChart;
}

/**
 * Simulate real-time price updates
 */
function simulatePriceUpdates(outcomes, baseProbabilities) {
    let probabilities = { ...baseProbabilities };
    
    setInterval(() => {
        // Randomly adjust probabilities while keeping sum = 1
        const keys = Object.keys(probabilities);
        const randomOutcome = keys[Math.floor(Math.random() * keys.length)];
        
        const change = (Math.random() - 0.5) * 0.05; // ±2.5% change
        
        probabilities[randomOutcome] = Math.max(0.01, Math.min(0.99, 
            probabilities[randomOutcome] + change));
        
        // Normalize to ensure sum = 1
        const total = Object.values(probabilities).reduce((a, b) => a + b, 0);
        Object.keys(probabilities).forEach(key => {
            probabilities[key] /= total;
        });

        addProbabilityDataPoint(probabilities);
        
        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('probabilityUpdate', { 
            detail: probabilities 
        }));
    }, 3000); // Update every 3 seconds
}

/**
 * Create mini sparkline chart for market cards
 */
function createSparkline(canvasId, dataPoints) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    // Set dimensions
    canvas.width = 100;
    canvas.height = 40;

    const gradient = ctx.createLinearGradient(0, 0, 0, 40);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dataPoints.map((_, i) => i),
            datasets: [{
                data: dataPoints,
                borderColor: '#6366f1',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                pointRadius: 0,
                tension: 0.4
            }]
        },
        options: {
            responsive: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { display: false },
                y: { display: false, min: 0, max: 1 }
            }
        }
    });
}

// Export functions globally
window.initProbabilityChart = initProbabilityChart;
window.addProbabilityDataPoint = addProbabilityDataPoint;
window.initVolumeChart = initVolumeChart;
window.simulatePriceUpdates = simulatePriceUpdates;
window.createSparkline = createSparkline;
