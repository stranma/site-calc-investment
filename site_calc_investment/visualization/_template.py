"""HTML template for the interactive dashboard.

Contains the full HTML template string with placeholders for chart data.
Uses Plotly.js loaded via CDN for interactive charts.
"""

PLOTLY_CDN_URL = "https://cdn.plot.ly/plotly-2.35.0.min.js"

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Investment Dashboard - {job_id}</title>
    <script src="{plotly_cdn_url}"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6fa; color: #2c3e50; }}
        .header {{ background: #2c3e50; color: white; padding: 20px 30px; }}
        .header h1 {{ font-size: 1.5em; font-weight: 600; }}
        .header .subtitle {{ font-size: 0.9em; color: #95a5a6; margin-top: 4px; }}
        .tabs {{ display: flex; background: #34495e; padding: 0 30px; }}
        .tab {{ padding: 12px 24px; color: #bdc3c7; cursor: pointer; border-bottom: 3px solid transparent; font-size: 0.95em; }}
        .tab:hover {{ color: white; }}
        .tab.active {{ color: white; border-bottom-color: #3498db; }}
        .tab-content {{ display: none; padding: 20px 30px; }}
        .tab-content.active {{ display: block; }}
        .kpi-row {{ display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }}
        .kpi-card {{ background: white; border-radius: 8px; padding: 20px; flex: 1; min-width: 200px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .kpi-card .label {{ font-size: 0.85em; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-card .value {{ font-size: 1.8em; font-weight: 700; margin-top: 8px; color: #2c3e50; }}
        .chart-container {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .drill-down-controls {{ background: white; border-radius: 8px; padding: 15px 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }}
        .drill-down-controls label {{ font-weight: 600; font-size: 0.9em; }}
        .drill-down-controls input {{ padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9em; }}
        .drill-down-controls button {{ padding: 6px 16px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; }}
        .drill-down-controls button:hover {{ background: #2980b9; }}
        .no-data {{ text-align: center; color: #95a5a6; padding: 40px; font-size: 1.1em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Investment Planning Dashboard</h1>
        <div class="subtitle">Job: {job_id} | Generated: {timestamp}</div>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="switchTab('financial')">Financial Analysis</div>
        <div class="tab" onclick="switchTab('energy')">Energy Balance</div>
        <div class="tab" onclick="switchTab('device-detail')">Device Detail</div>
    </div>

    <!-- Financial Tab -->
    <div id="tab-financial" class="tab-content active">
        <div class="kpi-row">
            {kpi_cards_html}
        </div>
        <div class="chart-container" id="chart-annual-revenue-costs"></div>
        <div class="chart-container" id="chart-cumulative-cash-flow"></div>
    </div>

    <!-- Energy Tab -->
    <div id="tab-energy" class="tab-content">
        <div class="kpi-row">
            {energy_kpi_html}
        </div>
        <div class="chart-container" id="chart-energy-balance"></div>
    </div>

    <!-- Device Detail Tab -->
    <div id="tab-device-detail" class="tab-content">
        <div class="drill-down-controls">
            <label>From hour:</label>
            <input type="number" id="hour-start" value="0" min="0" step="24">
            <label>To hour:</label>
            <input type="number" id="hour-end" value="{default_window_end}" min="1" step="24">
            <button onclick="updateDeviceCharts()">Show</button>
            <span style="color: #95a5a6; font-size: 0.85em;">Total hours: {total_hours}</span>
        </div>
        <div class="chart-container" id="chart-dispatch"></div>
        <div class="chart-container" id="chart-soc"></div>
    </div>

    <script>
        // Tab switching
        function switchTab(tabName) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            // Find and activate the clicked tab
            document.querySelectorAll('.tab').forEach(el => {{
                if (el.textContent.toLowerCase().includes(tabName.replace('-', ' ').substring(0, 6))) {{
                    el.classList.add('active');
                }}
            }});
            // Trigger resize for Plotly charts
            window.dispatchEvent(new Event('resize'));
        }}

        // Chart data
        var annualRevenueData = {annual_revenue_json};
        var cumulativeCashFlowData = {cumulative_cash_flow_json};
        var energyBalanceData = {energy_balance_json};
        var drillDownData = {drill_down_json};

        // Render static charts
        if (annualRevenueData) {{
            Plotly.newPlot('chart-annual-revenue-costs', annualRevenueData.traces, annualRevenueData.layout, {{responsive: true}});
        }} else {{
            document.getElementById('chart-annual-revenue-costs').innerHTML = '<div class="no-data">Annual revenue data not available (no investment parameters set)</div>';
        }}

        if (cumulativeCashFlowData) {{
            Plotly.newPlot('chart-cumulative-cash-flow', cumulativeCashFlowData.traces, cumulativeCashFlowData.layout, {{responsive: true}});
        }} else {{
            document.getElementById('chart-cumulative-cash-flow').innerHTML = '<div class="no-data">Cash flow data not available (no investment parameters set)</div>';
        }}

        if (energyBalanceData) {{
            Plotly.newPlot('chart-energy-balance', energyBalanceData.traces, energyBalanceData.layout, {{responsive: true}});
        }}

        // Device detail drill-down
        function updateDeviceCharts() {{
            if (!drillDownData || !drillDownData.devices) {{
                document.getElementById('chart-dispatch').innerHTML = '<div class="no-data">Device detail data not available (data omitted due to size limits or no devices present)</div>';
                document.getElementById('chart-soc').innerHTML = '';
                return;
            }}

            var startHour = parseInt(document.getElementById('hour-start').value) || 0;
            var endHour = parseInt(document.getElementById('hour-end').value) || {default_window_end};
            endHour = Math.min(endHour, drillDownData.total_hours);
            startHour = Math.max(0, Math.min(startHour, endHour - 1));

            var hours = [];
            for (var h = startHour; h < endHour; h++) hours.push(h);

            // Dispatch traces
            var dispatchTraces = [];
            var colors = ['#3498db', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12', '#1abc9c', '#e67e22', '#34495e'];
            var ci = 0;
            drillDownData.devices.forEach(function(dev) {{
                Object.keys(dev.flows).forEach(function(mat) {{
                    var vals = dev.flows[mat].slice(startHour, endHour);
                    dispatchTraces.push({{
                        x: hours, y: vals, type: 'scatter', mode: 'lines',
                        name: dev.name + ' (' + mat + ')',
                        line: {{ color: colors[ci % colors.length], width: 1.5 }}
                    }});
                    ci++;
                }});
            }});

            Plotly.newPlot('chart-dispatch', dispatchTraces, {{
                title: {{ text: 'Device Dispatch (Hours ' + startHour + '-' + endHour + ')' }},
                xaxis: {{ title: {{ text: 'Hour' }}, rangeslider: {{ visible: true }} }},
                yaxis: {{ title: {{ text: 'MW' }} }},
                legend: {{ orientation: 'h', y: -0.25 }},
                hovermode: 'x unified'
            }}, {{ responsive: true }});

            // SOC traces
            var socTraces = [];
            ci = 0;
            drillDownData.devices.forEach(function(dev) {{
                if (dev.soc) {{
                    var socVals = dev.soc.slice(startHour, endHour).map(function(v) {{ return v * 100; }});
                    socTraces.push({{
                        x: hours, y: socVals, type: 'scatter', mode: 'lines',
                        name: dev.name + ' SOC',
                        line: {{ color: colors[ci % colors.length], width: 2 }}
                    }});
                    ci++;
                }}
            }});

            if (socTraces.length > 0) {{
                Plotly.newPlot('chart-soc', socTraces, {{
                    title: {{ text: 'State of Charge (Hours ' + startHour + '-' + endHour + ')' }},
                    xaxis: {{ title: {{ text: 'Hour' }}, rangeslider: {{ visible: true }} }},
                    yaxis: {{ title: {{ text: 'SOC (%)' }}, range: [0, 100] }},
                    legend: {{ orientation: 'h', y: -0.25 }},
                    hovermode: 'x unified'
                }}, {{ responsive: true }});
            }} else {{
                document.getElementById('chart-soc').innerHTML = '<div class="no-data">No storage devices with SOC data</div>';
            }}
        }}

        // Initial render of device detail
        updateDeviceCharts();
    </script>
</body>
</html>
"""
