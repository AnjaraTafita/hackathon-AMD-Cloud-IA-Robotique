from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INVENTORY_PATH = BASE_DIR / "data" / "inventory.csv"
DEFAULT_DB_PATH = BASE_DIR / "data" / "pharmacy.sqlite"


@dataclass(frozen=True)
class Article:
    id_unique: str
    nom: str
    classe_therapeutique: str
    emplacement_rayon: str
    quantite_stock: int
    prix: float
    image_path: Path

    @property
    def prix_formate(self) -> str:
        return f"{self.prix:,.0f} Ar".replace(",", " ")


@dataclass(frozen=True)
class SelectionResult:
    ok: bool
    code: str
    messages: tuple[str, ...]
    article: Article | None = None


@dataclass(frozen=True)
class StockUpdateResult:
    ok: bool
    code: str
    messages: tuple[str, ...]
    article: Article | None = None


def resolve_project_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _article_from_row(row: sqlite3.Row) -> Article:
    return Article(
        id_unique=row["id_unique"],
        nom=row["nom"],
        classe_therapeutique=row["classe_therapeutique"],
        emplacement_rayon=row["emplacement_rayon"],
        quantite_stock=row["quantite_stock"],
        prix=row["prix"],
        image_path=Path(row["image_path"]),
    )


def _load_inventory_from_csv(path: str | Path = DEFAULT_INVENTORY_PATH) -> list[Article]:
    inventory_path = resolve_project_path(path)
    articles: list[Article] = []

    with inventory_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required_fields = {
            "id_unique",
            "nom",
            "classe_therapeutique",
            "emplacement_rayon",
            "quantite_stock",
            "prix",
            "image_path",
        }
        missing_fields = required_fields.difference(reader.fieldnames or [])
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Inventaire invalide: colonnes manquantes: {missing}")

        for line_number, row in enumerate(reader, start=2):
            try:
                articles.append(
                    Article(
                        id_unique=row["id_unique"].strip(),
                        nom=row["nom"].strip(),
                        classe_therapeutique=row["classe_therapeutique"].strip(),
                        emplacement_rayon=row["emplacement_rayon"].strip(),
                        quantite_stock=int(row["quantite_stock"]),
                        prix=float(row["prix"]),
                        image_path=Path(row["image_path"].strip()),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"Inventaire invalide a la ligne {line_number}: {exc}"
                ) from exc

    return articles


def connect_database(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = resolve_project_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_database(
    db_path: str | Path = DEFAULT_DB_PATH,
    seed_csv: str | Path = DEFAULT_INVENTORY_PATH,
) -> None:
    with connect_database(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id_unique TEXT PRIMARY KEY,
                nom TEXT NOT NULL,
                classe_therapeutique TEXT NOT NULL,
                emplacement_rayon TEXT NOT NULL,
                quantite_stock INTEGER NOT NULL CHECK (quantite_stock >= 0),
                prix REAL NOT NULL CHECK (prix >= 0),
                image_path TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id_unique)
            )
            """
        )

        row = connection.execute("SELECT COUNT(*) AS total FROM articles").fetchone()
        if row["total"] > 0:
            return

        articles = _load_inventory_from_csv(seed_csv)
        connection.executemany(
            """
            INSERT INTO articles (
                id_unique,
                nom,
                classe_therapeutique,
                emplacement_rayon,
                quantite_stock,
                prix,
                image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    article.id_unique,
                    article.nom,
                    article.classe_therapeutique,
                    article.emplacement_rayon,
                    article.quantite_stock,
                    article.prix,
                    str(article.image_path),
                )
                for article in articles
            ),
        )


def load_inventory(path: str | Path = DEFAULT_DB_PATH) -> list[Article]:
    data_path = resolve_project_path(path)
    if data_path.suffix.casefold() == ".csv":
        return _load_inventory_from_csv(data_path)

    init_database(data_path)
    with connect_database(data_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id_unique,
                nom,
                classe_therapeutique,
                emplacement_rayon,
                quantite_stock,
                prix,
                image_path
            FROM articles
            ORDER BY id_unique
            """
        ).fetchall()
    return [_article_from_row(row) for row in rows]


def find_article(inventory: list[Article], query: str) -> Article | None:
    normalized_query = normalize(query)
    if not normalized_query:
        return None

    for article in inventory:
        if normalize(article.id_unique) == normalized_query:
            return article

    for article in inventory:
        if normalize(article.nom) == normalized_query:
            return article

    partial_matches = [
        article for article in inventory if normalized_query in normalize(article.nom)
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]

    return None


def prepare_selection(
    inventory: list[Article], query: str, quantity: int = 1
) -> SelectionResult:
    if quantity <= 0:
        return SelectionResult(
            ok=False,
            code="QUANTITE_INVALIDE",
            messages=("La quantite demandee doit etre superieure a zero.",),
        )

    article = find_article(inventory, query)
    if article is None:
        return SelectionResult(
            ok=False,
            code="ARTICLE_INTROUVABLE",
            messages=(f"Aucun article ne correspond a la requete: {query}",),
        )

    if article.quantite_stock <= 0:
        return SelectionResult(
            ok=False,
            code="RUPTURE_STOCK",
            article=article,
            messages=(
                f"Article trouve: {article.nom} ({article.id_unique})",
                "Statut: rupture de stock.",
            ),
        )

    if article.quantite_stock < quantity:
        return SelectionResult(
            ok=False,
            code="STOCK_INSUFFISANT",
            article=article,
            messages=(
                f"Article trouve: {article.nom} ({article.id_unique})",
                f"Stock insuffisant: {article.quantite_stock} disponible(s), "
                f"{quantity} demande(s).",
            ),
        )

    absolute_image_path = resolve_project_path(article.image_path)
    if not absolute_image_path.exists():
        return SelectionResult(
            ok=False,
            code="IMAGE_MANQUANTE",
            article=article,
            messages=(
                f"Article trouve: {article.nom} ({article.id_unique})",
                f"Image associee introuvable: {article.image_path}",
            ),
        )

    return SelectionResult(
        ok=True,
        code="SELECTION_OK",
        article=article,
        messages=(
            f"Article trouve: {article.nom} ({article.id_unique})",
            f"Classe therapeutique: {article.classe_therapeutique}",
            f"Quantite demandee: {quantity}",
            f"Stock actuel: {article.quantite_stock}",
            f"Prix unitaire: {article.prix_formate}",
            f"Image selectionnee: {article.image_path}",
            f"Robot allant au compartiment: {article.emplacement_rayon}",
            "Etape 1 terminee: pret pour le module 3 (vision par ordinateur).",
        ),
    )


def record_transaction(
    article_id: str,
    quantity: int,
    action: str,
    status: str,
    message: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    init_database(db_path)
    with connect_database(db_path) as connection:
        connection.execute(
            """
            INSERT INTO transactions (
                article_id,
                quantity,
                action,
                status,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                quantity,
                action,
                status,
                message,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )


def confirm_delivery(
    query: str,
    quantity: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> StockUpdateResult:
    if resolve_project_path(db_path).suffix.casefold() == ".csv":
        return StockUpdateResult(
            ok=False,
            code="BASE_SQLITE_REQUISE",
            messages=(
                "Aucune modification effectuee.",
                "La confirmation de delivrance necessite une base SQLite.",
            ),
        )

    init_database(db_path)
    inventory = load_inventory(db_path)
    selection = prepare_selection(inventory, query, quantity)
    if not selection.ok or selection.article is None:
        article_id = selection.article.id_unique if selection.article else "[inconnu]"
        record_transaction(
            article_id,
            quantity,
            "DELIVERY",
            selection.code,
            "Modification refusee: " + " ".join(selection.messages),
            db_path,
        )
        return StockUpdateResult(
            ok=False,
            code=selection.code,
            messages=("Aucune modification effectuee.", *selection.messages),
            article=selection.article,
        )

    article = selection.article
    with connect_database(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE articles
            SET quantite_stock = quantite_stock - ?
            WHERE id_unique = ? AND quantite_stock >= ?
            """,
            (quantity, article.id_unique, quantity),
        )
        if cursor.rowcount != 1:
            return StockUpdateResult(
                ok=False,
                code="MISE_A_JOUR_REFUSEE",
                messages=(
                    "Aucune modification effectuee.",
                    "Le stock a change avant la confirmation. Rechargez le stock.",
                ),
                article=article,
            )

    updated_article = find_article(load_inventory(db_path), article.id_unique)
    new_stock = updated_article.quantite_stock if updated_article else 0
    message = (
        f"Modification confirmee: {quantity} unite(s) delivree(s) pour "
        f"{article.nom}. Nouveau stock: {new_stock}."
    )
    record_transaction(
        article.id_unique,
        quantity,
        "DELIVERY",
        "CONFIRMED",
        message,
        db_path,
    )
    return StockUpdateResult(
        ok=True,
        code="LIVRAISON_CONFIRMEE",
        messages=(
            message,
            "Transaction enregistree dans la base SQLite.",
        ),
        article=updated_article,
    )


def adjust_stock(
    query: str,
    quantity: int,
    operation: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> StockUpdateResult:
    if resolve_project_path(db_path).suffix.casefold() == ".csv":
        return StockUpdateResult(
            ok=False,
            code="BASE_SQLITE_REQUISE",
            messages=(
                "Aucune modification effectuee.",
                "L'ajustement de stock necessite une base SQLite.",
            ),
        )

    if quantity <= 0:
        return StockUpdateResult(
            ok=False,
            code="QUANTITE_INVALIDE",
            messages=("La quantite a ajuster doit etre superieure a zero.",),
        )

    normalized_operation = normalize(operation)
    if normalized_operation not in {"ajouter", "retirer"}:
        return StockUpdateResult(
            ok=False,
            code="OPERATION_INVALIDE",
            messages=("Choisissez une operation: ajouter ou retirer.",),
        )

    init_database(db_path)
    inventory = load_inventory(db_path)
    article = find_article(inventory, query)
    if article is None:
        return StockUpdateResult(
            ok=False,
            code="ARTICLE_INTROUVABLE",
            messages=(f"Aucun article ne correspond a la requete: {query}",),
        )

    if normalized_operation == "retirer" and article.quantite_stock < quantity:
        message = (
            f"Ajustement refuse: stock insuffisant pour {article.nom}. "
            f"Stock actuel: {article.quantite_stock}, retrait demande: {quantity}."
        )
        record_transaction(
            article.id_unique,
            quantity,
            "ADJUST_REMOVE",
            "REFUSED",
            message,
            db_path,
        )
        return StockUpdateResult(
            ok=False,
            code="STOCK_INSUFFISANT",
            messages=(message,),
            article=article,
        )

    delta = quantity if normalized_operation == "ajouter" else -quantity
    with connect_database(db_path) as connection:
        connection.execute(
            """
            UPDATE articles
            SET quantite_stock = quantite_stock + ?
            WHERE id_unique = ?
            """,
            (delta, article.id_unique),
        )

    updated_article = find_article(load_inventory(db_path), article.id_unique)
    new_stock = updated_article.quantite_stock if updated_article else 0
    label = "ajoutee(s)" if normalized_operation == "ajouter" else "retiree(s)"
    message = (
        f"Ajustement confirme: {quantity} unite(s) {label} pour "
        f"{article.nom}. Nouveau stock: {new_stock}."
    )
    record_transaction(
        article.id_unique,
        quantity,
        "ADJUST_ADD" if normalized_operation == "ajouter" else "ADJUST_REMOVE",
        "CONFIRMED",
        message,
        db_path,
    )
    return StockUpdateResult(
        ok=True,
        code="AJUSTEMENT_CONFIRME",
        messages=(
            message,
            "Ajustement enregistre dans la base SQLite.",
        ),
        article=updated_article,
    )


def print_inventory(inventory: list[Article]) -> None:
    print("Inventaire disponible")
    print("-" * 80)
    for article in inventory:
        print(
            f"{article.id_unique:8} | {article.nom:28} | "
            f"{article.emplacement_rayon:8} | stock: {article.quantite_stock:3} | "
            f"{article.prix_formate}"
        )


def run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Simulation des modules 1 et 2: stock + selection d'image."
    )
    parser.add_argument(
        "-q",
        "--query",
        help="Nom ou id_unique de l'article a rechercher.",
    )
    parser.add_argument(
        "-n",
        "--quantity",
        type=int,
        default=1,
        help="Quantite demandee pour la simulation.",
    )
    parser.add_argument(
        "--inventory",
        default=str(DEFAULT_DB_PATH),
        help="Chemin de la base SQLite ou d'un CSV d'inventaire.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirmer la delivrance et decrementer le stock dans SQLite.",
    )
    parser.add_argument(
        "--adjust",
        choices=("ajouter", "retirer"),
        help="Ajuster le stock SQLite en ajoutant ou retirant la quantite.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Afficher l'inventaire puis quitter.",
    )
    args = parser.parse_args()

    inventory = load_inventory(args.inventory)

    if args.list:
        print_inventory(inventory)
        return 0

    query = args.query
    if not query:
        query = input("Nom ou ID de l'article: ").strip()

    if args.confirm:
        result = confirm_delivery(query, args.quantity, args.inventory)
        print("\n".join(result.messages))
        return 0 if result.ok else 1

    if args.adjust:
        result = adjust_stock(query, args.quantity, args.adjust, args.inventory)
        print("\n".join(result.messages))
        return 0 if result.ok else 1

    result = prepare_selection(inventory, query, args.quantity)
    print("\n".join(result.messages))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(run_cli())
