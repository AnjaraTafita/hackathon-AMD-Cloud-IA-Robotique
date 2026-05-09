from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for

from app import (
    BASE_DIR,
    DEFAULT_DB_PATH,
    adjust_stock,
    confirm_delivery,
    connect_database,
    init_database,
    load_inventory,
    prepare_selection,
    resolve_project_path,
)
from llm_assistant import build_pharmacist_context
from vision import process_image


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("PHARMASTOCK_SECRET_KEY", "pharmastock-dev-secret")
DB_PATH = Path(os.environ.get("PHARMASTOCK_DB_PATH", DEFAULT_DB_PATH))


def _read_positive_int(value: str, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def load_recent_transactions(limit: int = 8) -> list[dict[str, str]]:
    init_database(DB_PATH)
    with connect_database(DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT article_id, quantity, action, status, message, created_at
            FROM transactions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def build_dashboard_context(extra: dict | None = None) -> dict:
    inventory = load_inventory(DB_PATH)
    total_stock = sum(article.quantite_stock for article in inventory)
    low_stock_count = sum(1 for article in inventory if article.quantite_stock <= 20)
    stock_value = sum(article.quantite_stock * article.prix for article in inventory)
    context = {
        "inventory": inventory,
        "transactions": load_recent_transactions(),
        "total_stock": total_stock,
        "low_stock_count": low_stock_count,
        "stock_value": f"{stock_value:,.0f} Ar".replace(",", " "),
        "active_article": None,
        "selection_messages": (),
        "vision_message": None,
        "llm_context": None,
    }
    if extra:
        context.update(extra)
    return context


@app.get("/")
def dashboard():
    return render_template("index.html", **build_dashboard_context())


@app.post("/select")
def select_article():
    query = request.form.get("query", "").strip()
    quantity = _read_positive_int(request.form.get("quantity", "1"))
    inventory = load_inventory(DB_PATH)
    result = prepare_selection(inventory, query, quantity)
    vision_message = None
    if result.ok and result.article is not None:
        image_path = resolve_project_path(result.article.image_path)
        vision_message = process_image(image_path).message
        flash("Selection validee. Vous pouvez vendre l'article.", "success")
    else:
        flash(result.messages[0] if result.messages else "Selection impossible.", "error")
    return render_template(
        "index.html",
        **build_dashboard_context(
            {
                "active_article": result.article,
                "selection_messages": result.messages,
                "vision_message": vision_message,
                "form_query": query,
                "form_quantity": quantity,
            }
        ),
    )


@app.post("/sell")
def sell_article():
    query = request.form.get("query", "").strip()
    quantity = _read_positive_int(request.form.get("quantity", "1"))
    result = confirm_delivery(query, quantity, DB_PATH)
    flash(result.messages[0], "success" if result.ok else "error")
    return redirect(url_for("dashboard"))


@app.post("/adjust")
def adjust_article_stock():
    query = request.form.get("adjust_query", "").strip()
    quantity = _read_positive_int(request.form.get("adjust_quantity", "1"))
    operation = request.form.get("operation", "ajouter")
    result = adjust_stock(query, quantity, operation, DB_PATH)
    flash(result.messages[0], "success" if result.ok else "error")
    return redirect(url_for("dashboard"))


@app.post("/assistant")
def prepare_assistant_context():
    symptoms = request.form.get("symptoms", "").strip()
    context = build_pharmacist_context(symptoms, load_inventory(DB_PATH))
    flash("Contexte LLM prepare pour le pharmacien.", "success")
    return render_template(
        "index.html",
        **build_dashboard_context({"llm_context": context.as_text(), "symptoms": symptoms}),
    )


@app.get("/images/<path:filename>")
def product_image(filename: str):
    image_dir = BASE_DIR / "images"
    requested_path = Path(filename)
    if requested_path.is_absolute() or ".." in requested_path.parts:
        return redirect(url_for("dashboard"))
    return send_from_directory(image_dir, filename)


if __name__ == "__main__":
    init_database(DB_PATH)
    app.run(host="127.0.0.1", port=5000, debug=True)
