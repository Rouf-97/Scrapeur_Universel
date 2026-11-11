
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


RACINE = Path(__file__).resolve().parent
CONFIGURATIONS = RACINE / "configurations"
HISTORIQUE = RACINE / "historique.json"


def lire_json(chemin, defaut=None):
    if not chemin.exists():
        return defaut if defaut is not None else {}

    return json.loads(chemin.read_text(encoding="utf-8"))


def enregistrer_json(chemin, donnees):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(donnees, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def empreinte_html(fichier_html):
    fichier_html = Path(fichier_html)
    h = hashlib.sha256()

    with fichier_html.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(65536), b""):
            h.update(bloc)

    return h.hexdigest()


def normaliser_site(site):
    site = site.strip().lower()

    if "://" in site:
        site = urlparse(site).hostname or ""

    return site.replace("/", "_").replace("\\", "_")


def chemin_configuration(site, structure="principal"):
    domaine = normaliser_site(site)
    return CONFIGURATIONS / domaine / f"{structure}.json"


def rechercher_configuration(site, structure="principal"):
    chemin = chemin_configuration(site, structure)

    if not chemin.is_file():
        return None

    return lire_json(chemin)


def enregistrer_configuration(site, configuration, structure="principal"):
    if not isinstance(configuration, dict):
        raise ValueError("La configuration doit être un objet JSON.")

    if not isinstance(configuration.get("structures"), list):
        raise ValueError("La configuration doit contenir 'structures'.")

    chemin = chemin_configuration(site, structure)
    enregistrer_json(chemin, configuration)
    return chemin


def html_deja_traite(fichier_html):
    empreinte = empreinte_html(fichier_html)
    historique = lire_json(HISTORIQUE, {"fichiers": {}})

    return empreinte in historique.get("fichiers", {})


def enregistrer_traitement(fichier_html, site, configuration):
    empreinte = empreinte_html(fichier_html)
    historique = lire_json(HISTORIQUE, {"fichiers": {}})

    historique.setdefault("fichiers", {})[empreinte] = {
        "site": normaliser_site(site),
        "source_html": str(Path(fichier_html).resolve()),
        "configuration": str(configuration),
        "date_traitement": datetime.now(timezone.utc).isoformat()
    }

    enregistrer_json(HISTORIQUE, historique)
    return empreinte


if __name__ == "__main__":
    print("Module de mémoire prêt.")
    print("Dossier :", CONFIGURATIONS)
    print("Historique :", HISTORIQUE)
