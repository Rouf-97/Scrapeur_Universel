
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SOURCE = Path(
    r"C:\Users\Dell\Desktop\application\Collecteur_Universel\HTML\captures"
)

DEFAULT_OUTPUT = Path(
    r"C:\Users\Dell\Desktop\application\Scrapeur_Universel\data\input"
)


def slug(value: str) -> str:
    """Convertit un nom en identifiant utilisable pour les dossiers."""
    result = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
    return result.strip("._-") or "inconnu"


def decode_html(path: Path) -> tuple[str, str]:
    """Lit un HTML en essayant plusieurs encodages."""
    data = path.read_bytes()

    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def prepare(
    source: Path,
    output: Path,
    lines_per_block: int = 90,
    overlap: int = 10
) -> dict:

    source = source.resolve()
    output = output.resolve()

    if not source.is_dir():
        raise FileNotFoundError(
            f"Dossier source introuvable : {source}"
        )

    if lines_per_block <= 0:
        raise ValueError(
            "Le nombre de lignes par bloc doit être supérieur à zéro"
        )

    if not 0 <= overlap < lines_per_block:
        raise ValueError(
            "Le chevauchement doit être positif ou nul "
            "et inférieur à la taille du bloc"
        )

    if source == output or source in output.parents:
        raise ValueError(
            "Le dossier de sortie ne doit pas être dans les captures source"
        )

    groups: dict[Path, list[Path]] = {}

    for file in source.rglob("*"):
        if file.is_file() and file.suffix.lower() in (".html", ".htm"):
            groups.setdefault(file.parent, []).append(file)

    manifest = {
        "source": str(source),
        "output": str(output),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "block_lines": lines_per_block,
        "overlap_lines": overlap,
        "samples": []
    }

    for folder, files in sorted(
        groups.items(),
        key=lambda item: str(item[0]).lower()
    ):

        # Sélection d'un HTML par dossier
        chosen = sorted(
            files,
            key=lambda p: p.name.lower()
        )[0]

        relative = folder.relative_to(source)
        parts = relative.parts

        domain = parts[0] if parts else "site_inconnu"

        fingerprint = hashlib.sha256(
            str(relative).encode("utf-8")
        ).hexdigest()[:10]

        sample_id = (
            slug(domain)
            + "__"
            + slug(folder.name)
            + "__"
            + fingerprint
        )

        sample_dir = output / "blocs" / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        html, encoding = decode_html(chosen)
        lines = html.splitlines()

        step = lines_per_block - overlap
        blocks = []

        for index, start in enumerate(
            range(0, len(lines), step),
            1
        ):

            end = min(
                start + lines_per_block,
                len(lines)
            )

            block_file = (
                sample_dir / f"bloc_{index:04d}.txt"
            )

            content = "\n".join(
                f"{line_no:06d} | {lines[line_no - 1]}"
                for line_no in range(start + 1, end + 1)
            )

            block_file.write_text(
                content + "\n",
                encoding="utf-8"
            )

            blocks.append({
                "file": str(block_file),
                "first_line": start + 1,
                "last_line": end
            })

            if end == len(lines):
                break

        paired_json = chosen.with_suffix(".json")

        metadata = {
            "id": sample_id,
            "domain_hint": domain,
            "capture_folder": str(relative),
            "source_html": str(chosen),
            "paired_json": (
                str(paired_json)
                if paired_json.is_file()
                else None
            ),
            "encoding": encoding,
            "total_lines": len(lines),
            "blocks": blocks
        }

        (sample_dir / "metadata.json").write_text(
            json.dumps(
                metadata,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        manifest["samples"].append(metadata)

    output.mkdir(
        parents=True,
        exist_ok=True
    )

    inventory_file = output / "inventaire.json"

    inventory_file.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return manifest


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Préparer des HTML pour analyse Codex "
            "par blocs de 90 lignes"
        )
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT
    )

    parser.add_argument(
        "--lines",
        type=int,
        default=90
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=10
    )

    args = parser.parse_args()

    result = prepare(
        args.source,
        args.output,
        args.lines,
        args.overlap
    )

    print(
        f"Dossiers analysés : {len(result['samples'])}"
    )

    print(
        "Blocs préparés : "
        f"{sum(len(x['blocks']) for x in result['samples'])}"
    )

    print(
        f"Inventaire : {args.output / 'inventaire.json'}"
    )


if __name__ == "__main__":
    main()
