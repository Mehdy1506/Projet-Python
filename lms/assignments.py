"""
assignments.py - Dépôt, évaluation et consultation des devoirs (F3.1, F3.2, F3.3).

Règles :
  - un étudiant dépose UN SEUL devoir par cours ; il peut le remplacer tant qu'il
    n'est pas noté ;
  - seul l'enseignant propriétaire du cours voit les devoirs de ce cours, les
    télécharge et les note (l'administrateur ne note pas) ;
  - un étudiant ne voit que ses propres devoirs et ses propres notes.
"""

import shutil
from pathlib import Path
from typing import List, Optional, Tuple

import auth
import fichiers
import storage
from models import Cours, Devoir, Utilisateur, ROLE_ENSEIGNANT, ROLE_ETUDIANT


# --- Fonctions internes -----------------------------------------------------

def _charger_cours(id_cours: int) -> Cours:
    cours = storage.get_cours(id_cours)
    if cours is None:
        raise ValueError("Cours introuvable.")
    return cours


def _charger_devoir(id_devoir: int) -> Devoir:
    devoir = storage.get_devoir(id_devoir)
    if devoir is None:
        raise ValueError("Devoir introuvable.")
    return devoir


def _exiger_proprietaire(acteur: Utilisateur, id_cours: int) -> Cours:
    """Vérifie que l'enseignant est bien le propriétaire du cours."""
    cours = _charger_cours(id_cours)
    if cours.enseignant != acteur.id_user:
        raise PermissionError("Ce cours n'est pas le vôtre.")
    return cours


# --- Dépôt (étudiant) -------------------------------------------------------

def deposer_devoir(acteur, id_cours: int, fichier_source) -> Devoir:
    """Dépose le devoir de l'étudiant pour un cours, ou remplace son dépôt
    précédent s'il n'a pas encore été noté."""
    acteur = auth.exiger_role(acteur, ROLE_ETUDIANT)
    _charger_cours(id_cours)

    existants = storage.lister_devoirs(id_cours=id_cours, etudiant=acteur.id_user)
    nouveau_chemin = fichiers.copier_fichier(fichier_source, fichiers.SOUS_DEVOIRS)

    try:
        if not existants:
            return storage.ajouter_devoir(
                Devoir(None, id_cours, acteur.id_user, nouveau_chemin))

        devoir = existants[0]
        if devoir.est_note:
            raise ValueError("Ce devoir a déjà été noté : il ne peut plus être remplacé.")
        ancien_chemin = devoir.fichier
        devoir.fichier = nouveau_chemin
        storage.modifier_devoir(devoir)
    except Exception:
        fichiers.supprimer_fichier(nouveau_chemin)   # pas de fichier orphelin
        raise
    fichiers.supprimer_fichier(ancien_chemin)
    return devoir


# --- Évaluation (enseignant) ------------------------------------------------

def devoirs_du_cours(acteur, id_cours: int) -> List[Tuple[Utilisateur, Devoir]]:
    """Liste des (étudiant, devoir) d'un cours, réservée à son propriétaire."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT)
    _exiger_proprietaire(acteur, id_cours)
    resultat = []
    for devoir in storage.lister_devoirs(id_cours=id_cours):
        etudiant = storage.get_utilisateur(devoir.etudiant)
        resultat.append((etudiant, devoir))
    return resultat


def telecharger_devoir(acteur, id_devoir: int, dossier_destination) -> Path:
    """Copie le fichier d'un devoir dans le dossier choisi (pour le corriger)."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT)
    devoir = _charger_devoir(id_devoir)
    _exiger_proprietaire(acteur, devoir.id_cours)

    source = fichiers.chemin_absolu(devoir.fichier)
    if not source.is_file():
        raise ValueError("Le fichier de ce devoir est introuvable sur le disque.")
    dossier = Path(dossier_destination)
    dossier.mkdir(parents=True, exist_ok=True)
    destination = dossier / source.name.split("_", 1)[1]   # nom sans préfixe unique
    shutil.copy2(source, destination)
    return destination


def noter_devoir(acteur, id_devoir: int, note) -> Devoir:
    """Attribue (ou corrige) la note d'un devoir. Note entre 0 et 20."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT)
    devoir = _charger_devoir(id_devoir)
    _exiger_proprietaire(acteur, devoir.id_cours)

    try:
        valeur = float(str(note).replace(",", "."))   # accepte "15,5"
    except ValueError:
        raise ValueError("La note doit être un nombre.") from None
    devoir.attribuer_note(valeur)   # vérifie l'intervalle 0-20
    storage.modifier_devoir(devoir)
    return devoir


# --- Consultation (étudiant) ------------------------------------------------

def mon_devoir(acteur, id_cours: int) -> Optional[Devoir]:
    """Le devoir déposé par l'étudiant pour ce cours (None s'il n'a rien déposé)."""
    acteur = auth.exiger_role(acteur, ROLE_ETUDIANT)
    devoirs = storage.lister_devoirs(id_cours=id_cours, etudiant=acteur.id_user)
    return devoirs[0] if devoirs else None


def mes_notes(acteur) -> List[Tuple[Cours, Devoir]]:
    """Tous les devoirs de l'étudiant avec leur cours (la note vaut None si non noté)."""
    acteur = auth.exiger_role(acteur, ROLE_ETUDIANT)
    resultat = []
    for devoir in storage.lister_devoirs(etudiant=acteur.id_user):
        resultat.append((storage.get_cours(devoir.id_cours), devoir))
    return resultat


def ma_moyenne(acteur) -> Optional[float]:
    """Moyenne des notes de l'étudiant (None s'il n'a aucune note) - F4.3."""
    acteur = auth.exiger_role(acteur, ROLE_ETUDIANT)
    return storage.moyenne_etudiant(acteur.id_user)


if __name__ == "__main__":
    # Test rapide dans un dossier temporaire : python assignments.py
    import tempfile
    import courses
    from models import ROLE_ENSEIGNANT as ENS

    def essayer(description, fonction):
        try:
            fonction()
            print(f"ERREUR ({description}) : aucune exception")
        except (ValueError, PermissionError) as e:
            print(f"{description} -> {type(e).__name__} : {e}")

    def fichiers_devoirs(base):
        return sorted(p.name for p in (base / "uploads" / "devoirs").glob("*"))

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        storage.DB_PATH = base / "test.db"
        fichiers.BASE_DIR = base
        fichiers.UPLOADS_DIR = base / "uploads"
        storage.init_db()

        auth.creer_admin_par_defaut()
        admin = auth.connecter("admin", "admin123")
        prof1 = auth.inscrire("Trabelsi", "Ali", ENS, "ali", "secret1")
        prof2 = auth.inscrire("Gharbi", "Leila", ENS, "leila", "secret1")
        etu1 = auth.inscrire("Ben Ali", "Sami", ROLE_ETUDIANT, "sami", "secret1")
        etu2 = auth.inscrire("Mejri", "Nour", ROLE_ETUDIANT, "nour", "secret1")

        cours_pdf = base / "cours.pdf"
        cours_pdf.write_bytes(b"%PDF cours")
        cours = courses.publier_cours(prof1, "Python", "Bases", cours_pdf)

        tp_v1 = base / "tp_v1.txt"
        tp_v1.write_text("version 1")
        tp_v2 = base / "tp_v2.txt"
        tp_v2.write_text("version 2")

        d = deposer_devoir(etu1, cours.id_cours, tp_v1)
        print("Déposé :", d.id_devoir, d.fichier)
        d = deposer_devoir(etu1, cours.id_cours, tp_v2)
        print("Remplacé -> devoirs en base :", len(storage.lister_devoirs()),
              "| fichiers :", fichiers_devoirs(base))

        essayer("dépôt par un enseignant", lambda: deposer_devoir(prof1, cours.id_cours, tp_v1))
        essayer("dépôt pour un cours inexistant", lambda: deposer_devoir(etu1, 999, tp_v1))
        essayer("doublon direct en base",
                lambda: storage.ajouter_devoir(Devoir(None, cours.id_cours, etu1.id_user, "x")))

        deposer_devoir(etu2, cours.id_cours, tp_v1)
        print("Le prof voit :", [(e.nom_complet, dv.note) for e, dv in devoirs_du_cours(prof1, cours.id_cours)])
        essayer("autre enseignant liste les devoirs", lambda: devoirs_du_cours(prof2, cours.id_cours))
        essayer("étudiant liste les devoirs", lambda: devoirs_du_cours(etu1, cours.id_cours))
        print("Téléchargé :", telecharger_devoir(prof1, d.id_devoir, base / "corrections").name)

        essayer("note de 25", lambda: noter_devoir(prof1, d.id_devoir, 25))
        essayer("note 'abc'", lambda: noter_devoir(prof1, d.id_devoir, "abc"))
        essayer("notation par un étudiant", lambda: noter_devoir(etu1, d.id_devoir, 10))
        essayer("notation par l'admin", lambda: noter_devoir(admin, d.id_devoir, 10))
        essayer("notation par un autre enseignant", lambda: noter_devoir(prof2, d.id_devoir, 10))

        noter_devoir(prof1, d.id_devoir, "15,5")
        essayer("remplacement après notation", lambda: deposer_devoir(etu1, cours.id_cours, tp_v1))
        print("Notes de Sami :", [(c.titre, dv.note) for c, dv in mes_notes(etu1)])
        print("Moyenne de Sami :", ma_moyenne(etu1), "| de Nour :", ma_moyenne(etu2))
        print("Devoir de Nour (étudiant 2) visible par Sami ? mon_devoir ne renvoie que le sien :",
              mon_devoir(etu1, cours.id_cours).etudiant == etu1.id_user)