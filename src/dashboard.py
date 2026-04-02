"""
Analytics Dashboard - Token Savings Visualization
Simple HTML dashboard showing compaction metrics
"""

from flask import Flask, render_template_string, jsonify
from datetime import datetime, timedelta
import json
import os

from src.storage import MockStorage


app = Flask(__name__)
storage = MockStorage()


# Demo data for visualization
def get_demo_stats():
    """Generate demo statistics for the dashboard"""
    return {
        "total_sessions": 47,
        "total_tokens_saved": 156234,
        "average_savings": 34.5,
        "total_compactions": 89,
        "daily_savings": [
            {"date": "2026-03-25", "tokens_saved": 5200, "compactions": 3},
            {"date": "2026-03-26", "tokens_saved": 8900, "compactions": 5},
            {"date": "2026-03-27", "tokens_saved": 12300, "compactions": 7},
            {"date": "2026-03-28", "tokens_saved": 15600, "compactions": 9},
            {"date": "2026-03-29", "tokens_saved": 18200, "compactions": 11},
            {"date": "2026-03-30", "tokens_saved": 21400, "compactions": 13},
            {"date": "2026-03-31", "tokens_saved": 24800, "compactions": 15},
            {"date": "2026-04-01", "tokens_saved": 27834, "compactions": 17},
        ],
        "usage_trends": {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "gpt4_usage": [45, 52, 48, 61, 55, 38, 42],
            "claude_usage": [30, 35, 42, 38, 45, 28, 32],
        }
    }


# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Context Compaction Analytics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1419;
            color: #e7e9ea;
            min-height: 100vh;
        }
        .header {
            background: #1a1f26;
            padding: 20px 30px;
            border-bottom: 1px solid #2f3943;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 24px;
            font-weight: 600;
            color: #1d9bf0;
        }
        .header .refresh {
            background: #1d9bf0;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1a1f26;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid #2f3943;
        }
        .stat-card .label {
            font-size: 14px;
            color: #8b98a5;
            margin-bottom: 8px;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: 700;
            color: #1d9bf0;
        }
        .stat-card .sub {
            font-size: 12px;
            color: #8b98a5;
            margin-top: 4px;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }
        .chart-card {
            background: #1a1f26;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid #2f3943;
        }
        .chart-card h3 {
            font-size: 18px;
            margin-bottom: 20px;
            color: #e7e9ea;
        }
        .recent-activity {
            margin-top: 30px;
        }
        .activity-table {
            width: 100%;
            border-collapse: collapse;
            background: #1a1f26;
            border-radius: 12px;
            overflow: hidden;
        }
        .activity-table th, .activity-table td {
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid #2f3943;
        }
        .activity-table th {
            background: #22272e;
            font-weight: 600;
            color: #8b98a5;
            font-size: 12px;
            text-transform: uppercase;
        }
        .activity-table tr:last-child td {
            border-bottom: none;
        }
        .badge {
            background: #1d9bf0;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
        }
        .badge.success { background: #00ba7c; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Context Compaction Analytics</h1>
        <button class="refresh" onclick="loadStats()">Refresh</button>
    </div>
    
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Sessions</div>
                <div class="value">{{ stats.total_sessions }}</div>
                <div class="sub">Active sessions compacted</div>
            </div>
            <div class="stat-card">
                <div class="label">Tokens Saved</div>
                <div class="value">{{ "{:,}".format(stats.total_tokens_saved) }}</div>
                <div class="sub">Total tokens preserved</div>
            </div>
            <div class="stat-card">
                <div class="label">Avg Savings</div>
                <div class="value">{{ stats.average_savings }}%</div>
                <div class="sub">Average compression rate</div>
            </div>
            <div class="stat-card">
                <div class="label">Compactions</div>
                <div class="value">{{ stats.total_compactions }}</div>
                <div class="sub">Total compaction operations</div>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-card">
                <h3>Token Savings Over Time</h3>
                <canvas id="savingsChart"></canvas>
            </div>
            <div class="chart-card">
                <h3>Usage by Model</h3>
                <canvas id="usageChart"></canvas>
            </div>
        </div>
        
        <div class="recent-activity">
            <h3 style="margin-bottom: 20px; font-size: 18px;">Recent Compaction Activity</h3>
            <table class="activity-table">
                <thead>
                    <tr>
                        <th>Session</th>
                        <th>Original</th>
                        <th>Compacted</th>
                        <th>Saved</th>
                        <th>Savings %</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody id="activityBody">
                    <!-- Populated by JS -->
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const stats = {{ stats | tojson }};
        
        // Initialize charts
        const savingsCtx = document.getElementById('savingsChart').getContext('2d');
        new Chart(savingsCtx, {
            type: 'line',
            data: {
                labels: stats.daily_savings.map(d => d.date.slice(5)),
                datasets: [{
                    label: 'Tokens Saved',
                    data: stats.daily_savings.map(d => d.tokens_saved),
                    borderColor: '#1d9bf0',
                    backgroundColor: 'rgba(29, 155, 240, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: '#2f3943' } },
                    y: { grid: { color: '#2f3943' } }
                }
            }
        });
        
        const usageCtx = document.getElementById('usageChart').getContext('2d');
        new Chart(usageCtx, {
            type: 'doughnut',
            data: {
                labels: ['GPT-4', 'Claude'],
                datasets: [{
                    data: [55, 45],
                    backgroundColor: ['#1d9bf0', '#00ba7c']
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } }
            }
        });
        
        // Populate activity table
        const activityHtml = stats.daily_savings.slice(-5).map((d, i) => `
            <tr>
                <td>session_${i + 1}</td>
                <td>${(d.tokens_saved * 2.5).toFixed(0)}</td>
                <td>${d.tokens_saved.toFixed(0)}</td>
                <td>${(d.tokens_saved * 0.6).toFixed(0)}</td>
                <td><span class="badge success">37.5%</span></td>
                <td>${d.date}</td>
            </tr>
        `).join('');
        document.getElementById('activityBody').innerHTML = activityHtml;
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Render dashboard"""
    stats = get_demo_stats()
    return render_template_string(DASHBOARD_HTML, stats=stats)


@app.route('/api/stats')
def api_stats():
    """API endpoint for stats"""
    return jsonify(get_demo_stats())


@app.route('/api/history')
def api_history():
    """API endpoint for history"""
    return jsonify(storage.get_all_history(20))


if __name__ == '__main__':
    print("🚀 Starting Analytics Dashboard on http://localhost:8050")
    app.run(host='0.0.0.0', port=8050, debug=True)
