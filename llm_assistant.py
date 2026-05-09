from __future__ import annotations

from dataclasses import dataclass

from app import Article


@dataclass(frozen=True)
class PharmacistContext:
    system_prompt: str
    user_context: str

    def as_text(self) -> str:
        return (
            "SYSTEM PROMPT\n"
            f"{self.system_prompt}\n\n"
            "CONTEXTE UTILISATEUR\n"
            f"{self.user_context}"
        )


def build_pharmacist_context(
    symptoms: str, inventory: list[Article]
) -> PharmacistContext:
    available_articles = [
        article
        for article in inventory
        if article.quantite_stock > 0
    ]
    stock_lines = "\n".join(
        (
            f"- {article.nom} ({article.id_unique}), "
            f"{article.classe_therapeutique}, stock {article.quantite_stock}"
        )
        for article in available_articles
    )

    system_prompt = (
        "Tu es un assistant pour pharmacien. Tu aides a structurer un "
        "echange avec un client, mais tu ne poses pas de diagnostic et tu ne "
        "remplaces pas la validation du pharmacien. En cas de symptomes "
        "graves, persistants, grossesse, enfant tres jeune, allergie connue "
        "ou interaction possible, recommande une evaluation medicale ou la "
        "validation directe du pharmacien."
    )
    user_context = (
        f"Symptomes decrits par le client:\n{symptoms.strip() or '[non renseigne]'}\n\n"
        "Medicaments actuellement disponibles dans le stock local:\n"
        f"{stock_lines or '- Aucun medicament disponible'}\n\n"
        "Tache attendue: proposer des questions de clarification et preparer "
        "un resume pour le pharmacien. Ne pas delivrer automatiquement un "
        "medicament."
    )

    return PharmacistContext(
        system_prompt=system_prompt,
        user_context=user_context,
    )
