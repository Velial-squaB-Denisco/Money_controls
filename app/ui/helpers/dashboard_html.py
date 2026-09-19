import json
from pathlib import Path

from app.ui import theme


CHART_JS_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "chart.umd.min.js"
)


def get_chart_script() -> str:
    if CHART_JS_PATH.exists():
        chart_js = CHART_JS_PATH.read_text(encoding="utf-8")
        return f"<script>{chart_js}</script>"

    return (
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/'
        'dist/chart.umd.min.js"></script>'
    )


DASHBOARD_CSS = """
    .dash {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
    }

    .card {
        background-color: @card;
        border: 1px solid @border;
        border-radius: 16px;
        padding: 16px;
    }

    .stat-title {
        color: @muted;
        font-size: 12px;
        margin-bottom: 6px;
    }

    .stat-value {
        font-size: 22px;
        font-weight: 700;
        color: @text;
    }

    .stat-value.income { color: @income; }
    .stat-value.expense { color: @expense; }

    .stat-delta {
        font-size: 12px;
        color: @muted;
        margin-top: 4px;
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 16px;
    }

    .span4 { grid-column: span 4; }
    .span6 { grid-column: span 6; }
    .span8 { grid-column: span 8; }
    .span12 { grid-column: span 12; }

    .chart-title {
        font-size: 14px;
        font-weight: 700;
        color: @text;
        margin-bottom: 10px;
    }

    .chart-box {
        height: 260px;
        position: relative;
    }

    .overrun-item {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        padding: 8px 0;
        border-bottom: 1px solid @border;
        font-size: 13px;
        color: @text;
    }

    .overrun-item:last-child {
        border-bottom: none;
    }
"""


INIT_JS = """
function hexToRgba(hex, alpha) {
    var result = /^#?([a-f\\d]{2})([a-f\\d]{2})([a-f\\d]{2})$/i.exec(hex);
    if (!result) return hex;
    var r = parseInt(result[1], 16);
    var g = parseInt(result[2], 16);
    var b = parseInt(result[3], 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
}

window.addEventListener('load', function () {
    if (!window.Chart) {
        document.querySelectorAll('.chart-box').forEach(function (el) {
            el.innerHTML = '<div class="empty">Не удалось загрузить Chart.js</div>';
        });
        return;
    }

    Chart.defaults.color = COLORS.muted;
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

    var palette = [
        COLORS.accent, COLORS.income, COLORS.expense,
        '#f59e0b', '#8b5cf6', '#0ea5e9', '#ec4899', '#94a3b8'
    ];

    function commonOptions(showLegend) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: showLegend, position: 'bottom' },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: COLORS.border } }
            }
        };
    }

    new Chart(document.getElementById('balanceChart'), {
        type: 'line',
        data: {
            labels: DATA.balance.labels,
            datasets: [
                {
                    label: 'Чистые активы',
                    data: DATA.balance.net,
                    fill: true,
                    backgroundColor: hexToRgba(COLORS.accent, 0.12),
                    borderColor: COLORS.accent,
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHitRadius: 30
                },
                {
                    label: 'Деньги (наличные + карты)',
                    data: DATA.balance.cash,
                    fill: false,
                    borderColor: COLORS.income,
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHitRadius: 30
                }
            ]
        },
        options: commonOptions(true)
    });

    new Chart(document.getElementById('donutChart'), {
        type: 'doughnut',
        data: {
            labels: DATA.donut.labels,
            datasets: [{
                data: DATA.donut.values,
                backgroundColor: palette,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '62%',
            plugins: { legend: { position: 'right' } }
        }
    });

    new Chart(document.getElementById('flowChart'), {
        type: 'bar',
        data: {
            labels: DATA.flow.labels,
            datasets: [
                { label: 'Доходы', data: DATA.flow.income, backgroundColor: COLORS.income, borderRadius: 6 },
                { label: 'Расходы', data: DATA.flow.expense, backgroundColor: COLORS.expense, borderRadius: 6 }
            ]
        },
        options: commonOptions(true)
    });

    new Chart(document.getElementById('topChart'), {
        type: 'bar',
        data: {
            labels: DATA.top.labels,
            datasets: [{
                label: 'Расходы',
                data: DATA.top.values,
                backgroundColor: COLORS.accent,
                borderRadius: 6,
                barPercentage: 0.7,
                categoryPercentage: 0.8
            }]
        },
        options: (function () {
            var opts = commonOptions(false);
            opts.indexAxis = 'y';
            opts.interaction = { mode: 'nearest', intersect: false, axis: 'y' };
            opts.plugins.tooltip = { mode: 'nearest', intersect: false, axis: 'y' };
            opts.scales.y.grid = { display: false };
            return opts;
        })()
    });

    new Chart(document.getElementById('forecastChart'), {
        type: 'line',
        data: {
            labels: DATA.forecast.labels,
            datasets: [{
                label: 'Прогноз баланса',
                data: DATA.forecast.values,
                fill: true,
                backgroundColor: hexToRgba(COLORS.income, 0.12),
                borderColor: COLORS.income,
                borderWidth: 2,
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHitRadius: 30
            }]
        },
        options: commonOptions(false)
    });
});
"""


def build_dashboard_html(data: dict, theme_name: str) -> str:
    colors = theme.get_colors(theme_name)

    css = theme.build_web_css(theme_name) + DASHBOARD_CSS

    for key, value in colors.items():
        css = css.replace(f"@{key}", value)

    cards_html = ""

    for card in data["cards"]:
        cards_html += f"""
        <div class="card">
            <div class="stat-title">{card['title']}</div>
            <div class="stat-value {card.get('value_class', '')}">{card['value']}</div>
            <div class="stat-delta">{card.get('delta', '')}</div>
        </div>
        """

    if data["overruns"]:
        overruns_html = ""

        for overrun in data["overruns"]:
            overruns_html += f"""
            <div class="overrun-item">
                <span>{overrun['category']}</span>
                <span class="expense">
                    {overrun['spent'] / 100:,.0f} / {overrun['limit'] / 100:,.0f}
                    ({overrun['percent']}%)
                </span>
            </div>
            """
    else:
        overruns_html = "<div class='empty'>Нет перерасходов</div>"

    data_json = json.dumps(data, ensure_ascii=False)
    colors_json = json.dumps(colors, ensure_ascii=False)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
        {css}
        </style>
    </head>
    <body>
        <div class="dash">
            <div class="cards">
                {cards_html}
            </div>

            <div class="grid">
                <div class="card span8">
                    <div class="chart-title">Динамика баланса</div>
                    <div class="chart-box"><canvas id="balanceChart"></canvas></div>
                </div>

                <div class="card span4">
                    <div class="chart-title">Структура расходов за месяц</div>
                    <div class="chart-box"><canvas id="donutChart"></canvas></div>
                </div>

                <div class="card span6">
                    <div class="chart-title">Доходы и расходы по месяцам</div>
                    <div class="chart-box"><canvas id="flowChart"></canvas></div>
                </div>

                <div class="card span6">
                    <div class="chart-title">Топ категорий расходов</div>
                    <div class="chart-box"><canvas id="topChart"></canvas></div>
                </div>

                <div class="card span8">
                    <div class="chart-title">Прогноз баланса</div>
                    <div class="chart-box"><canvas id="forecastChart"></canvas></div>
                </div>

                <div class="card span4">
                    <div class="chart-title">Топ перерасходов</div>
                    <div class="overrun">{overruns_html}</div>
                </div>
            </div>
        </div>

        <script>
        const DATA = {data_json};
        const COLORS = {colors_json};
        </script>

        {get_chart_script()}

        <script>
        {INIT_JS}
        </script>
    </body>
    </html>
    """