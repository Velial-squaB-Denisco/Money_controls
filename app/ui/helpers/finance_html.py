import json

from app.ui import theme
from app.ui.helpers.dashboard_html import get_chart_script


EXTRA_CSS = """
    .page-title {
        font-size: 20px;
        font-weight: 700;
        color: @text;
        margin-bottom: 12px;
    }

    .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
    }

    .card {
        background-color: @card;
        border: 1px solid @border;
        border-radius: 16px;
        padding: 16px;
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 16px;
    }

    .span6 { grid-column: span 6; }
    .span12 { grid-column: span 12; }

    .chart-title {
        font-size: 14px;
        font-weight: 700;
        color: @text;
        margin-bottom: 10px;
    }

    .chart-box {
        height: 280px;
        position: relative;
    }

    .stat-title {
        color: @muted;
        font-size: 12px;
        margin-bottom: 6px;
    }

    .stat-value {
        font-size: 20px;
        font-weight: 700;
        color: @text;
    }

    .stat-value.income { color: @income; }
    .stat-value.expense { color: @expense; }
"""


INIT_JS = """
window.addEventListener('load', function () {
    if (!window.Chart) return;

    Chart.defaults.color = COLORS.muted;
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

    (DATA.charts || []).forEach(function (ch) {
        var el = document.getElementById(ch.id);
        if (!el) return;

        if ((ch.labels || []).length < 2) {
            el.parentElement.innerHTML =
                '<div style="color:' + COLORS.muted +
                ';padding:60px 20px;text-align:center;font-size:14px;">' +
                'Пока недостаточно данных</div>';
            return;
        }

        var total = 0;
        (ch.datasets || []).forEach(function (ds) {
            (ds.data || []).forEach(function (v) {
                total += Math.abs(v || 0);
            });
        });

        if (total === 0) {
            el.parentElement.innerHTML =
                '<div style="color:' + COLORS.muted +
                ';padding:60px 20px;text-align:center;font-size:14px;">' +
                'Пока недостаточно данных</div>';
            return;
        }

        var datasets = (ch.datasets || []).map(function (ds) {
            return {
                label: ds.label,
                data: ds.data,
                backgroundColor: ds.fill ? ds.color + '33' : ds.color,
                borderColor: ds.color,
                borderWidth: ds.line ? 2 : 0,
                fill: !!ds.fill,
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHitRadius: 30,
                borderRadius: 6
            };
        });

        new Chart(el, {
            type: ch.type,
            data: { labels: ch.labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: ch.index_axis ? 'y' : 'x',
                interaction: {
                    mode: ch.index_axis ? 'nearest' : 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: (ch.datasets || []).length > 1,
                        position: 'bottom'
                    },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { grid: { color: COLORS.border } }
                }
            }
        });
    });
});
"""


def build_finance_html(payload: dict, theme_name: str) -> str:
    colors = theme.get_colors(theme_name)

    extra_css = EXTRA_CSS
    for key, value in colors.items():
        extra_css = extra_css.replace(f"@{key}", value)

    css = theme.build_web_css(theme_name) + extra_css

    cards_html = ""
    for card in payload.get("cards", []):
        cards_html += f"""
        <div class="card">
            <div class="stat-title">{card['title']}</div>
            <div class="stat-value {card.get('value_class', '')}">{card['value']}</div>
        </div>
        """

    charts_html = ""
    for chart in payload.get("charts", []):
        charts_html += f"""
        <div class="card span6">
            <div class="chart-title">{chart['title']}</div>
            <div class="chart-box"><canvas id="{chart['id']}"></canvas></div>
        </div>
        """

    payload_json = json.dumps(payload, ensure_ascii=False)
    for key, value in colors.items():
        payload_json = payload_json.replace(f"@{key}", value)

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
        <div class="page-title">{payload.get('title', '')}</div>
        <div class="cards">{cards_html}</div>
        <div class="grid">{charts_html}</div>

        <script>
        const DATA = {payload_json};
        const COLORS = {colors_json};
        </script>

        {get_chart_script()}

        <script>
        {INIT_JS}
        </script>
    </body>
    </html>
    """


def build_empty_html(theme_name: str) -> str:
    colors = theme.get_colors(theme_name)

    extra_css = EXTRA_CSS
    for key, value in colors.items():
        extra_css = extra_css.replace(f"@{key}", value)

    css = theme.build_web_css(theme_name) + extra_css

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
        <div class="page-title">Вклады и кредиты</div>
        <div class="card">
            <div class="stat-title">Нет данных</div>
            <div class="stat-value">Выбери вклад или кредит сверху</div>
        </div>
    </body>
    </html>
    """