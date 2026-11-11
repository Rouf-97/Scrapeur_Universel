
from memoire_sites.validation_config import recuperer_configuration
import subprocess
import sys
from pathlib import Path
from collections import defaultdict
import argparse
import json

from extracteur.extracteur import extraire_html


# ============================================================
# CONFIGURATION
# ============================================================

RACINE = Path(__file__).resolve().parent

DOSSIER_HTML = (
    RACINE.parent
    / "Collecteur_Universel"
    / "HTML"
    / "captures"
)

CONFIGURATIONS = RACINE / "memoire_sites" / "configurations"
SORTIE = RACINE / "data" / "extraction"


# ============================================================
# DÉTECTION AUTOMATIQUE DES SITES
# ============================================================

def detecter_sites():

    sites = defaultdict(list)

    if not DOSSIER_HTML.is_dir():
        raise FileNotFoundError(
            f"Dossier des captures introuvable : {DOSSIER_HTML}"
        )

    for fichier in sorted(DOSSIER_HTML.rglob("*")):

        if not fichier.is_file():
            continue

        if fichier.suffix.lower() not in (".html", ".htm"):
            continue

        relatif = fichier.relative_to(DOSSIER_HTML)

        if len(relatif.parts) < 2:
            site = "site_inconnu"
        else:
            site = relatif.parts[0]

        sites[site].append(fichier)

    return dict(sorted(sites.items()))


# ============================================================
# SÉLECTION DES SITES
# ============================================================

def choisir_sites(sites, mode=None):

    if not sites:
        print("Aucun fichier HTML trouvé.")
        return []

    print("\n========== SITES DÉTECTÉS ==========")

    noms = list(sites.keys())

    for numero, site in enumerate(noms, 1):

        nombre = len(sites[site])

        print(
            f"{numero:2}. {site:<30} "
            f"{nombre} HTML"
        )

    print("====================================")

    if mode is None:

        print("\nModes disponibles :")
        print("1. Automatique : tous les sites")
        print("2. Sélection : choisir les sites")

        while True:

            choix = input("\nChoisir le mode (1/2) : ").strip()

            if choix == "1":
                mode = "auto"
                break

            if choix == "2":
                mode = "selection"
                break

            print("Choix invalide.")

    if mode == "auto":
        return noms

    if mode != "selection":
        raise ValueError(f"Mode inconnu : {mode}")

    print("\nIndique les numéros séparés par des virgules.")
    print("Exemple : 1,3")

    while True:

        saisie = input("Sites à traiter : ").strip()

        try:

            numeros = [
                int(element.strip())
                for element in saisie.split(",")
            ]

            if not numeros:
                raise ValueError()

            if any(
                numero < 1 or numero > len(noms)
                for numero in numeros
            ):
                raise ValueError()

            return [
                noms[numero - 1]
                for numero in dict.fromkeys(numeros)
            ]

        except ValueError:
            print("Sélection invalide. Réessaie.")


# ============================================================
# TRAITEMENT DES FICHIERS HTML
# ============================================================


def preparer_configuration_automatiquement(site):
    """
    1. Recherche une analyse Codex existante.
    2. Si absente, prépare les blocs HTML.
    3. Demande confirmation avant Codex.
    4. Lance Codex pour le site sélectionné.
    5. Valide et mémorise la configuration.
    """

    print(f"\n[AUTOMATISATION] Site : {site}")

    # 1. Réutiliser une analyse Codex déjà disponible
    configuration = recuperer_configuration(site)

    if configuration:
        print("[OK] Configuration récupérée.")
        return configuration

    # 2. Préparer l'inventaire et les blocs
    print("[SCANNER] Préparation des HTML...")

    commande_scanner = [
        sys.executable,
        str(RACINE / "scanner" / "analyse_structure.py")
    ]

    try:
        subprocess.run(
            commande_scanner,
            cwd=RACINE,
            check=True
        )
    except (subprocess.CalledProcessError, OSError) as erreur:
        print(f"[ERREUR SCANNER] {erreur}")
        return None

    # Revérifier la mémoire après préparation
    configuration = recuperer_configuration(site)

    if configuration:
        return configuration

    # 3. Confirmation avant consommation de tokens
    print(f"\n[CODEX NÉCESSAIRE] {site}")
    print("Aucune configuration exploitable trouvée.")

    reponse = input(
        "Lancer l'analyse Codex pour ce site ? (o/n) : "
    ).strip().lower()

    if reponse not in ("o", "oui"):
        print("[CODEX] Analyse annulée.")
        return None

    # 4. Lancer Codex sur le site demandé
    print(f"\n[CODEX] Analyse de {site}...")

    commande_codex = [
        sys.executable,
        str(RACINE / "scanner" / "codex_analyse.py"),
        "--site",
        site
    ]

    try:
        subprocess.run(
            commande_codex,
            cwd=RACINE,
            check=True
        )
    except (subprocess.CalledProcessError, OSError) as erreur:
        print(f"[ERREUR CODEX] {erreur}")
        return None

    # 5. Vérifier et mémoriser le résultat
    print("\n[MÉMOIRE] Validation de l'analyse Codex...")

    configuration = recuperer_configuration(site)

    if not configuration:
        print(
            "[ÉCHEC] Codex n'a pas produit "
            "de configuration exploitable."
        )
        return None

    print("[OK] Configuration validée et mémorisée.")

    return configuration



def traiter_sites(sites, selection):

    SORTIE.mkdir(parents=True, exist_ok=True)

    statistiques = {
        "html_analyses": 0,
        "html_extraits": 0,
        "html_ignores": 0,
        "sans_configuration": 0,
        "aucune_extraction": 0,
        "erreurs": 0,
        "elements_extraits": 0
    }

    for site in selection:

        fichiers = sites[site]

        print(f"\n========== {site} ==========")
        print(f"HTML disponibles : {len(fichiers)}")

        dossier_config = CONFIGURATIONS / site

        configurations = (
            sorted(dossier_config.glob("*.json"))
            if dossier_config.is_dir()
            else []
        )


        if not configurations:

            print(
                "[CONFIGURATION ABSENTE] "
                "Démarrage de l'automatisation..."
            )

            configuration_trouvee = (
                preparer_configuration_automatiquement(site)
            )

            if configuration_trouvee:
                configurations = [configuration_trouvee]
                print("[MÉMOIRE OK] Extraction activée.")

            else:
                print(
                    "[ANALYSE NON DISPONIBLE] "
                    "Site ignoré."
                )

                statistiques["sans_configuration"] += len(fichiers)
                statistiques["html_ignores"] += len(fichiers)
                statistiques["html_analyses"] += len(fichiers)

                continue


        print(
            f"Configurations trouvées : {len(configurations)}"
        )

        for fichier in fichiers:

            statistiques["html_analyses"] += 1

            resultats_fichier = []

            for configuration in configurations:

                try:

                    resultats = extraire_html(
                        fichier,
                        configuration,
                        site
                    )

                    resultats_fichier.extend(resultats)

                except Exception as erreur:

                    print(
                        f"[ERREUR] {fichier.name} "
                        f"({configuration.name}) : {erreur}"
                    )

                    statistiques["erreurs"] += 1

            if not resultats_fichier:

                print(
                    f"[AUCUNE EXTRACTION] {fichier.name}"
                )

                statistiques["aucune_extraction"] += 1
                statistiques["html_ignores"] += 1

                continue

            destination = (
                SORTIE
                / fichier.relative_to(DOSSIER_HTML)
            ).with_suffix(".json")

            destination.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            destination.write_text(
                json.dumps(
                    resultats_fichier,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

            print(
                f"[EXTRACTION OK] {fichier.name} "
                f"({len(resultats_fichier)} éléments)"
            )

            statistiques["html_extraits"] += 1
            statistiques["elements_extraits"] += len(
                resultats_fichier
            )

    return statistiques


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Scrapeur Universel"
    )

    parser.add_argument(
        "--mode",
        choices=["auto", "selection"],
        default=None,
        help="Mode automatique ou sélection manuelle"
    )

    args = parser.parse_args()

    print("\n====================================")
    print("         SCRAPEUR UNIVERSEL")
    print("====================================")

    try:
        sites = detecter_sites()
    except FileNotFoundError as erreur:
        print(erreur)
        return

    if not sites:
        print("Aucun HTML disponible.")
        return

    try:
        selection = choisir_sites(sites, args.mode)
    except (EOFError, KeyboardInterrupt):
        print("\nSélection annulée.")
        return

    print("\nSites sélectionnés :")

    for site in selection:
        print(f" - {site}")

    statistiques = traiter_sites(sites, selection)

    print("\n========== BILAN ==========")

    print(
        f"HTML analysés       : "
        f"{statistiques['html_analyses']}"
    )

    print(
        f"HTML extraits       : "
        f"{statistiques['html_extraits']}"
    )

    print(
        f"HTML ignorés        : "
        f"{statistiques['html_ignores']}"
    )

    print(
        f"Sans configuration  : "
        f"{statistiques['sans_configuration']}"
    )

    print(
        f"Aucune extraction   : "
        f"{statistiques['aucune_extraction']}"
    )

    print(
        f"Erreurs rencontrées : "
        f"{statistiques['erreurs']}"
    )

    print(
        f"Éléments extraits   : "
        f"{statistiques['elements_extraits']}"
    )

    print(f"Résultats           : {SORTIE}")
    print("===========================\n")


if __name__ == "__main__":
    main()
