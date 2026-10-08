from __future__ import annotations

from flask import Flask, send_from_directory

from api.routes import api_bp
from config import FRONTEND_STATIC_DIR

app = Flask(
    __name__,
    static_folder=str(FRONTEND_STATIC_DIR),
    static_url_path="",
)
app.register_blueprint(api_bp)


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(debug=True)