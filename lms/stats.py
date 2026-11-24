"""
stats.py - Statistiques et suivi de progression (exigences F4.1 à F4.3).

(F4.4, le nombre de comptes par rôle, est dans admin.comptes_par_role.)

Règle de progression, retenue pour le moment :
    progression = devoirs rendus / nombre de cours publiés
Comme un étudiant ne dépose qu'un devoir par cours, « devoirs rendus » revient
à « nombre de cours pour lesquels il a rendu son devoir ».

Droits :
  - total des cours, progression de l'étudiant : étudiant (ses propres chiffres) ;
  - devoirs par cours : enseignant (ses cours) ou administrateur (tous les cours) ;
  - total des cours : tout utilisateur connecté.
"""

from dataclasses import dataclass
from typing import List, Optional

import auth
import storage
from models import ROLE_ADMIN, ROLE_ENSEIGNANT, ROLE_ETUDIANT, ROLES


# --- Résultats --------------------------------------------------------------

@dataclass
class Progression:
    """Suivi d'un étudiant."""
    devoirs_rendus: int
    cours_publies: int
    pourcentage: float             # 0.0 à 100.0
    devoirs_notes: int
    moyenne: Optional[float]       # None tant qu'aucun devoir n'est noté


@dataclass
class StatsCours:
    """Chiffres d'un cours."""
    id_cours: int
    titre: str
    devoirs_deposes: int
    devoirs_notes: int
    moyenne: Optional[float]       # moyenne des notes du cours, None si aucune note


# --- Calcul de la progression -----------------------------------------------

def calculer_progression(devoirs_rendus: int, cours_publies: int) -> float:
    """Pourcentage = devoirs rendus / cours publiés * 100.
    Retourne 0.0 s'il n'y a aucun cours publié (évite la division par zéro).
    Plafonné à 100 % par sécurité."""
    if cours_publies <= 0:
        return 0.0
    return min(100.0, devoirs_rendus / cours_publies * 100)


# --- Statistiques générales (F4.1) ------------------------------------------

def total_cours(acteur) -> int:
    """Nombre total de cours publiés."""
    auth.exiger_role(acteur, *ROLES)
    return storage.compter_cours()


# --- Statistiques par cours (F4.2) ------------------------------------------

def devoirs_par_cours(acteur) -> List[StatsCours]:
    """Nombre de devoirs déposés par cours. Un enseignant voit ses cours,
    l'administrateur voit tous les cours."""
    acteur = auth.exiger_role(acteur, ROLE_ENSEIGNANT, ROLE_ADMIN)
    proprietaire = acteur.id_user if acteur.role == ROLE_ENSEIGNANT else None

    resultat = []
    for cours in storage.lister_cours(proprietaire):
        devoirs = storage.lister_devoirs(id_cours=cours.id_cours)
        notes = [d.note for d in devoirs if d.est_note]
        resultat.append(StatsCours(
            cours.id_cours, cours.titre,
            devoirs_deposes=len(devoirs),
            devoirs_notes=len(notes),
            moyenne=sum(notes) / len(notes) if notes else None,
        ))
    return resultat


# --- Suivi de l'étudiant (F4.3) ---------------------------------------------

def ma_progression(acteur) -> Progression:
    """Progression, nombre de devoirs notés et moyenne de l'étudiant connecté."""
    acteur = auth.exiger_role(acteur, ROLE_ETUDIANT)
    devoirs = storage.lister_devoirs(etudiant=acteur.id_user)
    cours_publies = storage.compter_cours()
    return Progression(
        devoirs_rendus=len(devoirs),
        cours_publies=cours_publies,
        pourcentage=calculer_progression(len(devoirs), cours_publies),
        devoirs_notes=sum(1 for d in devoirs if d.est_note),
        moyenne=storage.moyenne_etudiant(acteur.id_user),
    )


def barre_progression(pourcentage: float, largeur: int = 20) -> str:
    """Barre de texte pour l'interface console, ex. '[#########-----------] 45 %'."""
    remplis = round(largeur * pourcentage / 100)
    return f"[{'#' * remplis}{'-' * (largeur - remplis)}] {pourcentage:.0f} %"


if __name__ == "__main__":
    # Test rapide dans un dossier temporaire : python stats.py
    import tempfile
    from pathlib import Path

    import assignments
    import courses
    import fichiers

    def essayer(description, fonction):
        try:
            fonction()
            print(f"ERREUR ({description}) : aucune exception")
        except (ValueError, PermissionError) as e:
            print(f"{description} -> {type(e).__name__} : {e}")

    print("Règle seule : 1/4 =", calculer_progression(1, 4), "| 0/0 =", calculer_progression(0, 0))

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        storage.DB_PATH = base / "test.db"
        fichiers.BASE_DIR = base
        fichiers.UPLOADS_DIR = base / "uploads"
        storage.init_db()

        auth.creer_admin_par_defaut()
        admin = auth.connecter("admin", "admin123")
        prof1 = auth.inscrire("Trabelsi", "Ali", ROLE_ENSEIGNANT, "ali", "secret1")
        prof2 = auth.inscrire("Gharbi", "Leila", ROLE_ENSEIGNANT, "leila", "secret1")
        sami = auth.inscrire("Ben Ali", "Sami", ROLE_ETUDIANT, "sami", "secret1")
        nour = auth.inscrire("Mejri", "Nour", ROLE_ETUDIANT, "nour", "secret1")

        pdf = base / "cours.pdf"
        pdf.write_bytes(b"%PDF cours")
        tp = base / "tp.txt"
        tp.write_text("mon devoir")

        print("Progression sans cours :", ma_progression(sami))

        c1 = courses.publier_cours(prof1, "Python", "Bases", pdf)
        c2 = courses.publier_cours(prof1, "SQL", "Requêtes", pdf)
        c3 = courses.publier_cours(prof2, "Statistiques", "Bases", pdf)
        c4 = courses.publier_cours(prof2, "Marketing", "Digital", pdf)
        print("Total des cours (vu par un étudiant) :", total_cours(sami))

        d1 = assignments.deposer_devoir(sami, c1.id_cours, tp)
        d2 = assignments.deposer_devoir(sami, c2.id_cours, tp)
        d3 = assignments.deposer_devoir(nour, c1.id_cours, tp)
        assignments.noter_devoir(prof1, d1.id_devoir, 16)
        assignments.noter_devoir(prof1, d3.id_devoir, 12)

        p = ma_progression(sami)
        print("Sami :", p)
        print("      ", barre_progression(p.pourcentage))
        print("Nour :", barre_progression(ma_progression(nour).pourcentage))

        print("Cours de prof1 :")
        for s in devoirs_par_cours(prof1):
            print("  ", s)
        print("Cours de prof2 (aucun devoir) :", [(s.titre, s.devoirs_deposes) for s in devoirs_par_cours(prof2)])
        print("Vue admin :", [(s.titre, s.devoirs_deposes) for s in devoirs_par_cours(admin)])

        essayer("étudiant demande les devoirs par cours", lambda: devoirs_par_cours(sami))
        essayer("enseignant demande une progression", lambda: ma_progression(prof1))
        essayer("admin demande une progression", lambda: ma_progression(admin))