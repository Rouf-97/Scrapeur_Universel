
import json
import shutil
from pathlib import Path

from bs4 import BeautifulSoup


RACINE = Path(__file__).resolve().parents[1]

ANALYSES = RACINE / "data" / "input" / "analyses_codex"

MEMOIRE = RACINE / "memoire_sites" / "configurations"

CAPTURES = (
    RACINE.parent
    / "Collecteur_Universel"
    / "HTML"
    / "captures"
)


def valider_configuration(configuration, fichier_html):
    """
    Vérifie les sélecteurs CSS sur le HTML source.
    Ne modifie aucun fichier.
    """

    soup = BeautifulSoup(
        fichier_html.read_text(
            encoding="utf-8",
            errors="replace"
        ),
        "html.parser"
    )

    structures = configuration.get("structures", [])

    if not structures:
        return False, "Aucune structure définie"

    total_conteneurs = 0
    total_champs_valides = 0

    for structure in structures:

        conteneur = structure.get("conteneur")

        if not conteneur:
            return False, "Conteneur manquant"

        try:
            elements = soup.select(conteneur)
        except Exception as erreur:
            return False, f"Sélecteur invalide : {erreur}"

        print(
            f"  {structure.get('nom')} : "
            f"{len(elements)} conteneurs"
        )

        total_conteneurs += len(elements)

        for champ in structure.get("champs", []):

            selecteur = champ.get("selecteur")

            if not selecteur:
                continue

            try:
                trouves = sum(
                    bool(element.select_one(selecteur))
                    for element in elements
                )
            except Exception as erreur:
                return False, f"Champ invalide : {erreur}"

            if trouves:
                total_champs_valides += 1

            print(
                f"    {champ.get('nom')} : "
                f"{trouves}/{len(elements)}"
            )

    valide = (
        total_conteneurs > 0
        and total_champs_valides > 0
    )

    return valide, (
        f"{total_conteneurs} conteneurs, "
        f"{total_champs_valides} champs exploitables"
    )


def recuperer_configuration(site):
    """
    Recherche une configuration Codex existante,
    la valide et l'enregistre dans la mémoire.
    """

    if not ANALYSES.is_dir():
        print("[MÉMOIRE] Aucun dossier d'analyses.")
        return None

    candidats = []

    for fichier in ANALYSES.glob("*/selecteurs.json"):

        try:
            config = json.loads(
                fichier.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

        if config.get("metadata", {}).get("site") == site:
            candidats.append((fichier, config))

    if not candidats:
        print(f"[MÉMOIRE] Aucun JSON Codex pour {site}")
        return None

    candidats.sort(
        key=lambda element: element[0].stat().st_mtime,
        reverse=True
    )

    for fichier, config in candidats:

        source = config.get(
            "metadata", {}
        ).get("source_html")

        if not source:
            continue

        html = Path(source)

        if not html.is_file():
            print(f"[SOURCE INTROUVABLE] {html}")
            continue

        # Vérifier que le HTML appartient au collecteur.
        if not html.resolve().is_relative_to(
            CAPTURES.resolve()
        ):
            print("[REFUS] HTML hors du collecteur.")
            continue

        print(f"\n[VALIDATION] {fichier.name}")
        print(f"Site : {site}")

        valide, diagnostic = valider_configuration(
            config,
            html
        )

        print(f"Résultat : {diagnostic}")

        if not valide:
            print("[REFUS] Configuration non validée.")
            continue

        dossier = MEMOIRE / site
        dossier.mkdir(parents=True, exist_ok=True)

        destination = dossier / "principal.json"

        if destination.exists():
            print(
                "[MÉMOIRE] Configuration déjà présente :",
                destination
            )
            return destination

        shutil.copy2(fichier, destination)

        print(
            "[MÉMOIRE] Configuration enregistrée :",
            destination
        )

        return destination

    return None
