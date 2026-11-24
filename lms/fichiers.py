"""
fichiers.py - Gestion des fichiers déposés (cours et devoirs).

Module partagé par courses.py et assignments.py : il valide un fichier
(existence, extension, taille), le copie dans le dossier uploads/ avec un nom
unique, et le supprime proprement.

Les chemins enregistrés en base sont RELATIFS au dossier du programme
(ex. 'uploads/cours/3fa9c1d2_cours1.pdf') : la base reste valable si on
déplace le dossier du projet.
"""

import secrets
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
SOUS_COURS = "cours"
SOUS_DEVOIRS = "devoirs"

EXTENSIONS_AUTORISEES = (".pdf", ".txt")
TAILLE_MAX = 10 * 1024 * 1024      # 10 Mo


def nettoyer_nom(nom: str) -> str:
    """Garde uniquement le nom du fichier (pas de dossier) et remplace les
    caractères douteux par '_' (évite les noms du type '../../x')."""
    nom = Path(nom).name
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in nom)


def valider_fichier(source) -> Path:
    """Vérifie que le fichier existe, a une extension autorisée et une taille raisonnable."""
    chemin = Path(source)
    if chemin.is_dir():
        raise ValueError("Ce chemin est un dossier : indiquez le chemin complet d'un "
                         "fichier (ex. C:\\Users\\vous\\Desktop\\cours.pdf).")
    if not chemin.is_file():
        raise ValueError(f"Fichier introuvable : {chemin}")
    if chemin.suffix.lower() not in EXTENSIONS_AUTORISEES:
        raise ValueError("Type de fichier non autorisé (extensions acceptées : "
                         + ", ".join(EXTENSIONS_AUTORISEES) + ").")
    taille = chemin.stat().st_size
    if taille == 0:
        raise ValueError("Le fichier est vide.")
    if taille > TAILLE_MAX:
        raise ValueError(f"Fichier trop volumineux (maximum {TAILLE_MAX // (1024 * 1024)} Mo).")
    return chemin


def copier_fichier(source, sous_dossier: str) -> str:
    """Valide puis copie le fichier dans uploads/<sous_dossier>/ sous un nom
    unique. Retourne le chemin relatif à enregistrer en base."""
    chemin = valider_fichier(source)
    destination_dir = UPLOADS_DIR / sous_dossier
    destination_dir.mkdir(parents=True, exist_ok=True)
    nom_final = f"{secrets.token_hex(4)}_{nettoyer_nom(chemin.name)}"
    shutil.copy2(chemin, destination_dir / nom_final)
    return (Path("uploads") / sous_dossier / nom_final).as_posix()


def chemin_absolu(chemin_relatif: str) -> Path:
    """Chemin complet d'un fichier enregistré en base."""
    return BASE_DIR / chemin_relatif


def supprimer_fichier(chemin_relatif: str) -> None:
    """Supprime le fichier s'il existe. Refuse de toucher à un fichier situé
    hors du dossier uploads/ (protection contre un chemin falsifié en base)."""
    if not chemin_relatif:
        return
    chemin = chemin_absolu(chemin_relatif).resolve()
    if not chemin.is_relative_to(UPLOADS_DIR.resolve()):
        raise PermissionError("Chemin de fichier en dehors du dossier uploads.")
    chemin.unlink(missing_ok=True)


if __name__ == "__main__":
    # Test rapide dans un dossier temporaire : python fichiers.py
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        BASE_DIR = Path(tmp)
        UPLOADS_DIR = BASE_DIR / "uploads"

        pdf = BASE_DIR / "cours 1 (final).pdf"
        pdf.write_bytes(b"%PDF-1.4 test")
        rel = copier_fichier(pdf, SOUS_COURS)
        print("Copié :", rel, "| existe :", chemin_absolu(rel).is_file())
        supprimer_fichier(rel)
        print("Après suppression, existe :", chemin_absolu(rel).exists())

        exe = BASE_DIR / "virus.exe"
        exe.write_bytes(b"x")
        gros = BASE_DIR / "gros.txt"
        with open(gros, "wb") as f:
            f.truncate(TAILLE_MAX + 1)
        for source in (exe, gros, BASE_DIR / "absent.pdf"):
            try:
                copier_fichier(source, SOUS_COURS)
            except ValueError as e:
                print("Refusé :", e)
        try:
            supprimer_fichier("../../etc/passwd")
        except PermissionError as e:
            print("Refusé :", e)