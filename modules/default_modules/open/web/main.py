from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="IRIS - Abrir Web Module")

#rodar manualmente módulo
# uvicorn modules.default_modules.open.web.main:app --host 127.0.0.1 --port 4101 --reload

def build_color_page(color: str, title: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8" />
        <title>{title}</title>
        <style>
            html, body {{
                margin: 0;
                width: 100%;
                height: 100%;
                background: {color};
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }}

            h1 {{
                font-size: 48px;
                text-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
            }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
    </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok", "module": "abrir_web"}


@app.get("/web/verde", response_class=HTMLResponse)
def open_green_page():
    return build_color_page("#2ECC71", "IRIS - Página Verde")


@app.get("/web/vermelho", response_class=HTMLResponse)
def open_red_page():
    return build_color_page("#E74C3C", "IRIS - Página Vermelha")