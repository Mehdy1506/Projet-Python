"""
admin.py - Gestion des comptes par l'administrateur (exigence F1.4 et F4.4).

Toutes les fonctions prennent en premier paramètre l'utilisateur qui agit
(`acteur`) et vérifient qu'il est bien un administrateur actif.

Règle de sécurité : un administrateur ne peut ni supprimer, ni désactiver,
ni changer le rôle de SON PROPRE compte. Comme l'acteur est forcément un
administrateur actif, il en reste toujours au moins un : on ne peut jamais
se retrouver sans administrateur.
"""

from typing import Dict, List, Optional

import auth
import fichiers
import storage
from models import ROLE_ADMIN, ROLES, Utilisateur


# --- Fonctions internes -----------------------------------------------------

def _verifier_acteur(acteur: Optional[Utilisateur]) -> Utilisateur:
    """Vérifie que l'acteur est un admin actif, d'après l'état ACTUEL de la base
    (l'objet en mémoire a pu devenir obsolète : compte désactivé entre-temps)."""
    auth.exiger_role(acteur, ROLE_ADMIN)
    a_jour = storage.get_utilisateur(acteur.id_user)
    auth.exiger_role(a_jour, ROLE_ADMIN)
    return a_jour


def _charger_cible(id_user: int) -> Utilisateur:
    cible = storage.get_utilisateur(id_user)
    if cible is None:
        raise ValueError("Utilisateur introuvable.")
    return cible


def _refuser_si_soi_meme(acteur: Utilisateur, cible: Utilisateur, action: str) -> None:
    if acteur.id_user == cible.id_user:
        raise PermissionError(f"Vous ne pouvez pas {action} votre propre compte.")


# --- Gestion des comptes ----------------------------------------------------

def creer_compte(acteur: Utilisateur, nom: str, prenom: str, role: str,
                 login: str, mot_de_passe: str) -> Utilisateur:
    """Crée un compte de n'importe quel rôle (y compris administrateur)."""
    _verifier_acteur(acteur)
    auth.valider_mot_de_passe(mot_de_passe)
    u = Utilisateur(None, nom, prenom, role, login,
                    auth.hasher_mot_de_passe(mot_de_passe))
    return storage.ajouter_utilisateur(u)


def lister_comptes(acteur: Utilisateur, role: Optional[str] = None) -> List[Utilisateur]:
    _verifier_acteur(acteur)
    if role is not None and role not in ROLES:
        raise ValueError(f"Rôle invalide : {role!r}.")
    return storage.lister_utilisateurs(role)


def modifier_compte(acteur: Utilisateur, id_user: int, nom: Optional[str] = None,
                    prenom: Optional[str] = None, login: Optional[str] = None,
                    role: Optional[str] = None) -> Utilisateur:
    """Modifie les champs fournis (ceux laissés à None ne changent pas)."""
    acteur = _verifier_acteur(acteur)
    cible = _charger_cible(id_user)

    if role is not None and role != cible.role:
        _refuser_si_soi_meme(acteur, cible, "changer le rôle de")
        # Changer le rôle d'un compte qui possède déjà des données les rendrait incohérents.
        if storage.lister_cours(enseignant=cible.id_user) or \
                storage.lister_devoirs(etudiant=cible.id_user):
            raise ValueError("Ce compte possède des cours ou des devoirs : "
                             "son rôle ne peut plus être changé.")

    # On reconstruit l'objet : les validations de models.py sont rejouées.
    modifie = Utilisateur(
        cible.id_user,
        nom if nom is not None else cible.nom,
        prenom if prenom is not None else cible.prenom,
        role if role is not None else cible.role,
        login if login is not None else cible.login,
        cible.mot_de_passe,
        cible.actif,
    )
    storage.modifier_utilisateur(modifie)
    return modifie


def desactiver_compte(acteur: Utilisateur, id_user: int) -> None:
    acteur = _verifier_acteur(acteur)
    cible = _charger_cible(id_user)
    _refuser_si_soi_meme(acteur, cible, "désactiver")
    cible.actif = False
    storage.modifier_utilisateur(cible)


def activer_compte(acteur: Utilisateur, id_user: int) -> None:
    _verifier_acteur(acteur)
    cible = _charger_cible(id_user)
    cible.actif = True
    storage.modifier_utilisateur(cible)


def supprimer_compte(acteur: Utilisateur, id_user: int) -> None:
    """Supprime le compte ET, en cascade, ses cours et ses devoirs
    (fichiers du disque compris)."""
    acteur = _verifier_acteur(acteur)
    cible = _charger_cible(id_user)
    _refuser_si_soi_meme(acteur, cible, "supprimer")

    # Fichiers à effacer : à lister AVANT la suppression, car la cascade
    # en base fait disparaître les lignes qui contiennent leurs chemins.
    a_effacer = []
    for cours in storage.lister_cours(enseignant=id_user):
        a_effacer.append(cours.fichier)
        a_effacer += [d.fichier for d in storage.lister_devoirs(id_cours=cours.id_cours)]
    a_effacer += [d.fichier for d in storage.lister_devoirs(etudiant=id_user)]

    storage.supprimer_utilisateur(id_user)
    for chemin in a_effacer:
        try:
            fichiers.supprimer_fichier(chemin)
        except PermissionError:
            pass    # chemin hors de uploads/ : on n'y touche pas


def reinitialiser_mot_de_passe(acteur: Utilisateur, id_user: int,
                               nouveau_mdp: str) -> None:
    _verifier_acteur(acteur)
    cible = _charger_cible(id_user)
    auth.valider_mot_de_passe(nouveau_mdp)
    if nouveau_mdp == auth.ADMIN_MDP_DEFAUT:
        raise ValueError("Choisissez un mot de passe différent de celui par défaut.")
    cible.mot_de_passe = auth.hasher_mot_de_passe(nouveau_mdp)
    storage.modifier_utilisateur(cible)


# --- Statistiques (F4.4) ----------------------------------------------------

def comptes_par_role(acteur: Utilisateur) -> Dict[str, int]:
    """Nombre de comptes par rôle (les rôles sans compte valent 0)."""
    _verifier_acteur(acteur)
    comptes = storage.compter_utilisateurs_par_role()
    return {role: comptes.get(role, 0) for role in ROLES}


if __name__ == "__main__":
    # Test rapide dans une base temporaire : python admin.py
    import tempfile
    from pathlib import Path
    from models import Cours, ROLE_ENSEIGNANT, ROLE_ETUDIANT

    def essayer(description, fonction):
        try:
            fonction()
            print(f"ERREUR ({description}) : aucune exception")
        except (ValueError, PermissionError) as e:
            print(f"{description} -> {type(e).__name__} : {e}")

    with tempfile.TemporaryDirectory() as tmp:
        storage.DB_PATH = Path(tmp) / "test.db"
        fichiers.BASE_DIR = Path(tmp)
        fichiers.UPLOADS_DIR = Path(tmp) / "uploads"
        storage.init_db()
        auth.creer_admin_par_defaut()
        admin = auth.connecter("admin", "admin123")

        prof = creer_compte(admin, "Trabelsi", "Ali", ROLE_ENSEIGNANT, "ali", "secret1")
        etu = creer_compte(admin, "Ben Ali", "Sami", ROLE_ETUDIANT, "sami", "secret1")
        admin2 = creer_compte(admin, "Second", "Admin", ROLE_ADMIN, "admin2", "secret1")
        print("Comptes par rôle :", comptes_par_role(admin))

        modifier_compte(admin, etu.id_user, prenom="Samir")
        print("Prénom modifié :", storage.get_utilisateur(etu.id_user).prenom)

        desactiver_compte(admin, etu.id_user)
        essayer("connexion d'un compte désactivé", lambda: auth.connecter("sami", "secret1"))
        activer_compte(admin, etu.id_user)
        reinitialiser_mot_de_passe(admin, etu.id_user, "nouveau1")
        print("Connexion après réinitialisation :",
              auth.connecter("sami", "nouveau1").nom_complet)

        essayer("étudiant qui crée un compte",
                lambda: creer_compte(etu, "A", "B", ROLE_ETUDIANT, "x", "secret1"))
        essayer("admin qui se supprime", lambda: supprimer_compte(admin, admin.id_user))
        essayer("admin qui se désactive", lambda: desactiver_compte(admin, admin.id_user))
        essayer("admin qui se rétrograde",
                lambda: modifier_compte(admin, admin.id_user, role=ROLE_ETUDIANT))

        modele = Path(tmp) / "p.pdf"
        modele.write_bytes(b"%PDF test")
        fichier_cours = fichiers.copier_fichier(modele, fichiers.SOUS_COURS)
        storage.ajouter_cours(Cours(None, "Python", "Bases", prof.id_user, fichier_cours))
        essayer("changement de rôle d'un enseignant ayant un cours",
                lambda: modifier_compte(admin, prof.id_user, role=ROLE_ETUDIANT))

        # admin2 est désactivé : son objet en mémoire est périmé mais la base fait foi.
        desactiver_compte(admin, admin2.id_user)
        essayer("action d'un admin désactivé", lambda: lister_comptes(admin2))

        supprimer_compte(admin, prof.id_user)
        print("Cours restants après suppression de l'enseignant :", storage.compter_cours(),
              "| fichier du cours encore sur le disque :",
              fichiers.chemin_absolu(fichier_cours).exists())