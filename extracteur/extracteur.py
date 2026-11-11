
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse


from bs4 import BeautifulSoup


# ============================================================
# CHEMINS
# ============================================================

PROJET = Path(__file__).resolve().parent.parent

MEMOIRE = PROJET / "memoire_sites" / "configurations"

SORTIE = PROJET / "data" / "extraction"


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def lire_json(fichier):
    return json.loads(
        Path(fichier).read_text(encoding="utf-8")
    )


def enregistrer_json(fichier, donnees):
    fichier = Path(fichier)
    fichier.parent.mkdir(parents=True, exist_ok=True)

    fichier.write_text(
        json.dumps(
            donnees,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def extraire_valeur(conteneur, champ):
    selecteur = champ.get("selecteur", "")
    attribut = champ.get("attribut", "text")

    if not selecteur:
        return ""

    element = conteneur.select_one(selecteur)

    if element is None:
        return ""

    if attribut == "text":
        return element.get_text(" ", strip=True)

    valeur = element.get(attribut, "")

    if isinstance(valeur, list):
        return " ".join(valeur)

    return str(valeur or "")


# ============================================================
# NORMALISATION DES LIENS
# ============================================================

def normaliser_liens(donnees, configuration, site):
    """
    Applique les règles d'URL définies dans le JSON.

    Aucune règle spécifique à Indeed n'est codée ici.
    """

    regles = configuration.get("normalisation", {})

    modele = regles.get("modele_lien")

    if modele:
        try:
            donnees["lien"] = modele.format(**donnees)
        except (KeyError, ValueError):
            pass

    elif donnees.get("lien"):
        lien = donnees["lien"]

        if not urlparse(lien).scheme:
            donnees["lien"] = urljoin(
                f"https://{site}/",
                lien
            )

    return donnees


# ============================================================
# MOTEUR D'EXTRACTION
# ============================================================

def extraire_html(fichier_html, fichier_config, site):

    fichier_html = Path(fichier_html)
    configuration = lire_json(fichier_config)

    html = fichier_html.read_text(
        encoding="utf-8",
        errors="replace"
    )

    soup = BeautifulSoup(html, "html.parser")

    resultats = []

    for structure in configuration.get("structures", []):

        selecteur_conteneur = structure.get(
            "conteneur", ""
        )

        if not selecteur_conteneur:
            continue

        conteneurs = soup.select(selecteur_conteneur)

        print(
            f"Structure : {structure.get('nom', 'inconnue')}"
        )
        print(f"Éléments trouvés : {len(conteneurs)}")

        for conteneur in conteneurs:

            donnees = {}

            for champ in structure.get("champs", []):

                nom = champ.get("nom")

                if not nom:
                    continue

                donnees[nom] = extraire_valeur(
                    conteneur,
                    champ
                )

            donnees = normaliser_liens(
                donnees,
                configuration,
                site
            )

            resultats.append({
                "structure": structure.get("nom"),
                "donnees": donnees
            })

    return resultats


# ============================================================
# EXÉCUTION
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Extracteur HTML universel"
    )

    parser.add_argument(
        "--html",
        required=True,
        help="Chemin du fichier HTML"
    )

    parser.add_argument(
        "--site",
        required=True,
        help="Domaine du site, ex. fr.indeed.com"
    )

    parser.add_argument(
        "--structure",
        default="offres",
        help="Nom de la configuration JSON"
    )

    args = parser.parse_args()

    fichier_config = (
        MEMOIRE
        / args.site
        / f"{args.structure}.json"
    )

    if not fichier_config.is_file():
        print(
            "Configuration introuvable :",
            fichier_config
        )
        return

    resultats = extraire_html(
        args.html,
        fichier_config,
        args.site
    )

    SORTIE.mkdir(parents=True, exist_ok=True)

    fichier_sortie = (
        SORTIE / f"{args.site}_{args.structure}.json"
    )

    enregistrer_json(
        fichier_sortie,
        resultats
    )

    print("=" * 55)
    print("EXTRACTION TERMINÉE")
    print("=" * 55)
    print("Site :", args.site)
    print("Résultats :", len(resultats))
    print("Fichier :", fichier_sortie)


if __name__ == "__main__":
    main()
