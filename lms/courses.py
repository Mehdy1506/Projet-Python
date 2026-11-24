"""
courses.py - Gestion des cours (exigences F2.1, F2.2, F2.3).

Droits :
  - publier un cours           : enseignant ;
  - modifier un cours          : l'enseignant propriétaire uniquement ;
  - supprimer un cours         : l'enseignant propriétaire OU un administrateur ;
  - consulter / télécharger    : tout utilisateur connecté (étudiant, enseignant, admin).
L'administrateur ne peut donc pas modifier un cours, seulement le consulter ou le supprimer.
"""

import shutil
from pathlib import Path
from typing import List, Optional

import auth
import fichiers
import storage
from models import Cours, ROLE_ADMIN, ROLE_ENSEIGNANT, ROLES


# --- Fonctions internes -----------------------------------------------------

def _charger_cours(id_cours: int) -> Cours:
    cours = storage.get_cours(id_cours)
    if cours is None:
        raise ValueError("Cours introuvable.")
    return cours


# --- Publication et modification --------------------------------------------

def publier_cours(acteur, titre: str, description: str, fichier_source) -> Cours:
    """Un enseignant publie un cours : le fichier (PDF ou texte) est copié dans uploads/cours/."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT)
    cours = Cours(None, titre, description, acteur.id_user, "")   # valide le titre
    cours.fichier = fichiers.copier_fichier(fichier_source, fichiers.SOUS_COURS)
    try:
        return storage.ajouter_cours(cours)
    except Exception:
        fichiers.supprimer_fichier(cours.fichier)   # pas de fichier orphelin
        raise


def modifier_cours(acteur, id_cours: int, titre: Optional[str] = None,
                   description: Optional[str] = None,
                   nouveau_fichier=None) -> Cours:
    """Modifie les champs fournis (None = inchangé). Réservé au propriétaire."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT)
    cours = _charger_cours(id_cours)
    if cours.enseignant != acteur.id_user:
        raise PermissionError("Vous ne pouvez modifier que vos propres cours.")

    ancien_fichier = cours.fichier
    # Reconstruction : les validations de models.py sont rejouées.
    modifie = Cours(cours.id_cours,
                    titre if titre is not None else cours.titre,
                    description if description is not None else cours.description,
                    cours.enseignant, cours.fichier)
    if nouveau_fichier is not None:
        modifie.fichier = fichiers.copier_fichier(nouveau_fichier, fichiers.SOUS_COURS)
    try:
        storage.modifier_cours(modifie)
    except Exception:
        if nouveau_fichier is not None:
            fichiers.supprimer_fichier(modifie.fichier)
        raise
    if nouveau_fichier is not None:
        fichiers.supprimer_fichier(ancien_fichier)   # l'ancien fichier n'est plus utile
    return modifie


# --- Suppression ------------------------------------------------------------

def supprimer_cours(acteur, id_cours: int) -> None:
    """Supprime le cours, ses devoirs (en cascade en base) et tous leurs fichiers."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT, ROLE_ADMIN)
    cours = _charger_cours(id_cours)
    if acteur.role == ROLE_ENSEIGNANT and cours.enseignant != acteur.id_user:
        raise PermissionError("Vous ne pouvez supprimer que vos propres cours.")

    devoirs = storage.lister_devoirs(id_cours=id_cours)   # à lire AVANT la cascade
    storage.supprimer_cours(id_cours)
    fichiers.supprimer_fichier(cours.fichier)
    for devoir in devoirs:
        fichiers.supprimer_fichier(devoir.fichier)


# --- Consultation -----------------------------------------------------------

def lister_cours(acteur, enseignant: Optional[int] = None) -> List[Cours]:
    """Tous les cours, ou seulement ceux d'un enseignant donné."""
    auth.exiger_role(acteur, *ROLES)
    return storage.lister_cours(enseignant)


def mes_cours(acteur) -> List[Cours]:
    """Les cours publiés par l'enseignant connecté."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT)
    return storage.lister_cours(acteur.id_user)


def consulter_cours(acteur, id_cours: int) -> Cours:
    auth.exiger_role(acteur, *ROLES)
    return _charger_cours(id_cours)


def telecharger_cours(acteur, id_cours: int, dossier_destination) -> Path:
    """Copie le fichier du cours dans le dossier choisi et retourne le chemin de la copie."""
    auth.exiger_role(acteur, *ROLES)
    cours = _charger_cours(id_cours)
    source = fichiers.chemin_absolu(cours.fichier)
    if not source.is_file():
        raise ValueError("Le fichier de ce cours est introuvable sur le disque.")
    dossier = Path(dossier_destination)
    dossier.mkdir(parents=True, exist_ok=True)
    # Nom d'origine sans le préfixe unique (ex. '3fa9c1d2_cours1.pdf' -> 'cours1.pdf')
    destination = dossier / source.name.split("_", 1)[1]
    shutil.copy2(source, destination)
    return destination


if __name__ == "__main__":
    # Test rapide dans un dossier temporaire : python courses.py
    import tempfile
    from models import Devoir, ROLE_ETUDIANT

    def essayer(description, fonction):
        try:
            fonction()
            print(f"ERREUR ({description}) : aucune exception")
        except (ValueError, PermissionError) as e:
            print(f"{description} -> {type(e).__name__} : {e}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        storage.DB_PATH = base / "test.db"
        fichiers.BASE_DIR = base
        fichiers.UPLOADS_DIR = base / "uploads"
        storage.init_db()

        admin = auth.creer_admin_par_defaut() and auth.connecter("admin", "admin123")
        prof1 = auth.inscrire("Trabelsi", "Ali", ROLE_ENSEIGNANT, "ali", "secret1")
        prof2 = auth.inscrire("Gharbi", "Leila", ROLE_ENSEIGNANT, "leila", "secret1")
        etu = auth.inscrire("Ben Ali", "Sami", ROLE_ETUDIANT, "sami", "secret1")

        pdf = base / "python.pdf"
        pdf.write_bytes(b"%PDF-1.4 cours")
        pdf2 = base / "python_v2.pdf"
        pdf2.write_bytes(b"%PDF-1.4 cours v2")

        cours = publier_cours(prof1, "Python", "Bases du langage", pdf)
        print("Publié :", cours.id_cours, cours.fichier)
        print("Étudiant voit :", [c.titre for c in lister_cours(etu)])
        print("Admin voit :", [c.titre for c in lister_cours(admin)])
        print("Téléchargé :", telecharger_cours(etu, cours.id_cours, base / "telechargements").name)

        essayer("étudiant qui publie", lambda: publier_cours(etu, "X", "", pdf))
        exe = base / "virus.exe"
        exe.write_bytes(b"x")
        essayer("publication d'un .exe", lambda: publier_cours(prof1, "X", "", exe))
        essayer("modification par un autre enseignant",
                lambda: modifier_cours(prof2, cours.id_cours, titre="Piraté"))
        essayer("modification par l'admin",
                lambda: modifier_cours(admin, cours.id_cours, titre="Piraté"))
        essayer("suppression par un autre enseignant",
                lambda: supprimer_cours(prof2, cours.id_cours))

        ancien = cours.fichier
        modifie = modifier_cours(prof1, cours.id_cours, titre="Python avancé", nouveau_fichier=pdf2)
        print("Modifié :", modifie.titre, "| ancien fichier supprimé :",
              not fichiers.chemin_absolu(ancien).exists())

        # Un devoir (avec son fichier) pour vérifier le nettoyage à la suppression
        devoir_fichier = fichiers.copier_fichier(pdf, fichiers.SOUS_DEVOIRS)
        storage.ajouter_devoir(Devoir(None, cours.id_cours, etu.id_user, devoir_fichier))

        supprimer_cours(admin, cours.id_cours)
        print("Après suppression par l'admin : cours =", storage.compter_cours(),
              "| devoirs =", len(storage.lister_devoirs()),
              "| fichiers restants =", [p.name for p in (base / "uploads").rglob("*") if p.is_file()])