import html

import markdown

from app.ui import theme


def render_markdown(text: str) -> str:
    safe_text = html.escape(text or "")

    return markdown.markdown(
        safe_text,
        extensions=[
            "tables",
            "fenced_code",
            "sane_lists",
        ],
    )


def page_html(body_html: str, theme_name: str) -> str:
    css = theme.build_web_css(theme_name)

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
    {body_html}
    </body>
    </html>
    """


def markdown_page_html(markdown_text: str, theme_name: str) -> str:
    body_html = render_markdown(markdown_text)

    return page_html(body_html, theme_name)


def plain_page_html(text: str, theme_name: str) -> str:
    escaped = html.escape(text or "")
    body_html = escaped.replace("\n", "<br>")

    return page_html(body_html, theme_name)


def chat_page_html(messages: list[dict], theme_name: str) -> str:
    if not messages:
        body_html = "<div class='empty'>Нет сообщений</div>"
        return page_html(body_html, theme_name)

    blocks = []

    for message in messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")

        if role == "user":
            role_label = "Вы"
            escaped_content = html.escape(content)
            content_html = escaped_content.replace("\n", "<br>")
        else:
            role_label = "Ассистент"
            content_html = render_markdown(content)

        blocks.append(
            f"""
            <div class="msg {role}">
                <div class="role">{role_label}</div>
                <div class="content">{content_html}</div>
            </div>
            """
        )

    body_html = "\n".join(blocks)

    return page_html(body_html, theme_name)