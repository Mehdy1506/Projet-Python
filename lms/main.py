"""
main.py - Interface console du LMS (point d'entrée : python main.py).

Ce module ne contient AUCUNE règle métier : il demande des saisies, appelle les
modules de logique (auth, admin, courses, assignments, stats) et affiche leurs
résultats ou leurs erreurs. Les droits sont vérifiés par ces modules, pas ici :
les menus par rôle ne servent qu'à ne proposer que les actions utiles.
"""

import getpass
import sys
from pathlib import Path

import admin
import assignments
import auth
import courses
import fichiers
import stats
import storage
from models import ROLE_ADMIN, ROLE_ENSEIGNANT, ROLE_ETUDIANT, ROLES


# ============================================================================
# Saisie et affichage
# ============================================================================

def saisir(invite: str, defaut: str = "") -> str:
    """Demande un texte. Une saisie vide retourne la valeur par défaut."""
    texte = f"{invite} [{defaut}] : " if defaut else f"{invite} : "
    return input(texte).strip() or defaut


def saisir_mdp(invite: str = "Mot de passe") -> str:
    """Saisie masquée dans un vrai terminal, saisie normale sinon (tests, redirection)."""
    if sys.stdin.isatty():
        return getpass.getpass(f"{invite} : ")
    return input(f"{invite} : ")


def saisir_nouveau_mdp() -> str:
    """Demande un nouveau mot de passe deux fois."""
    mdp = saisir_mdp("Nouveau mot de passe")
    if mdp != saisir_mdp("Confirmez le mot de passe"):
        raise ValueError("Les deux mots de passe sont différents.")
    return mdp


def saisir_entier(invite: str) -> int:
    texte = saisir(invite)
    try:
        return int(texte)
    except ValueError:
        raise ValueError("Veuillez saisir un nombre entier.") from None


def saisir_chemin(invite: str) -> str:
    """Chemin de fichier ; retire les guillemets ajoutés par un glisser-déposer."""
    return saisir(invite).strip("\"'")


def confirmer(question: str) -> bool:
    return saisir(f"{question} (o/n)", "n").lower() in ("o", "oui", "y", "yes")


def choisir_role(roles) -> str:
    for i, role in enumerate(roles, 1):
        print(f"  {i}. {role}")
    choix = saisir_entier("Rôle")
    if not 1 <= choix <= len(roles):
        raise ValueError("Choix invalide.")
    return roles[choix - 1]


def titre(texte: str) -> None:
    print(f"\n=== {texte} ===")


def afficher_comptes(comptes) -> None:
    if not comptes:
        print("  (aucun compte)")
        return
    print(f"  {'ID':<4} {'Nom':<28} {'Rôle':<15} {'Login':<14} Statut")
    for u in comptes:
        statut = "actif" if u.actif else "DÉSACTIVÉ"
        print(f"  {u.id_user:<4} {u.nom_complet:<28} {u.role:<15} {u.login:<14} {statut}")


def afficher_cours(liste) -> None:
    if not liste:
        print("  (aucun cours)")
        return
    print(f"  {'ID':<4} {'Titre':<28} {'Enseignant':<24} Description")
    for c in liste:
        prof = storage.get_utilisateur(c.enseignant)
        nom = prof.nom_complet if prof else "?"
        print(f"  {c.id_cours:<4} {c.titre:<28} {nom:<24} {c.description}")


def afficher_note(note) -> str:
    return "non noté" if note is None else f"{note:g} / 20"


# ============================================================================
# Actions communes
# ============================================================================

def changer_mon_mdp(user) -> None:
    titre("Changer mon mot de passe")
    ancien = saisir_mdp("Ancien mot de passe")
    nouveau = saisir_nouveau_mdp()
    auth.changer_mot_de_passe(user, ancien, nouveau)
    print("  ✓ Mot de passe modifié.")


def telecharger(fonction_telechargement) -> None:
    """Demande le dossier de destination puis appelle la fonction de téléchargement."""
    defaut = str(fichiers.BASE_DIR / "telechargements")
    dossier = saisir("Dossier de destination", defaut)
    copie = fonction_telechargement(dossier)
    print(f"  ✓ Fichier enregistré : {copie}")


# ============================================================================
# Actions de l'administrateur
# ============================================================================

def admin_lister_comptes(user) -> None:
    titre("Comptes")
    filtre = None
    if saisir("Filtrer (o/n)", "n").lower() in ("o", "oui"):
        filtre = choisir_role(ROLES)
    afficher_comptes(admin.lister_comptes(user, filtre))


def admin_creer_compte(user) -> None:
    titre("Créer un compte")
    nom, prenom = saisir("Nom"), saisir("Prénom")
    role = choisir_role(ROLES)
    login = saisir("Login")
    mdp = saisir_nouveau_mdp()
    u = admin.creer_compte(user, nom, prenom, role, login, mdp)
    print(f"  ✓ Compte créé : {u.nom_complet} ({u.role}), id {u.id_user}.")


def admin_modifier_compte(user) -> None:
    titre("Modifier un compte")
    afficher_comptes(admin.lister_comptes(user))
    id_user = saisir_entier("ID du compte")
    print("Laissez vide pour ne rien changer.")
    nom = saisir("Nouveau nom") or None
    prenom = saisir("Nouveau prénom") or None
    login = saisir("Nouveau login") or None
    role = None
    if saisir("Changer le rôle (o/n)", "n").lower() in ("o", "oui"):
        role = choisir_role(ROLES)
    admin.modifier_compte(user, id_user, nom, prenom, login, role)
    print("  ✓ Compte modifié.")


def admin_desactiver(user) -> None:
    titre("Désactiver un compte")
    afficher_comptes(admin.lister_comptes(user))
    admin.desactiver_compte(user, saisir_entier("ID du compte"))
    print("  ✓ Compte désactivé.")


def admin_activer(user) -> None:
    titre("Réactiver un compte")
    afficher_comptes(admin.lister_comptes(user))
    admin.activer_compte(user, saisir_entier("ID du compte"))
    print("  ✓ Compte réactivé.")


def admin_supprimer(user) -> None:
    titre("Supprimer un compte")
    afficher_comptes(admin.lister_comptes(user))
    id_user = saisir_entier("ID du compte")
    print("  Attention : ses cours et ses devoirs seront supprimés aussi.")
    if confirmer("Confirmer la suppression"):
        admin.supprimer_compte(user, id_user)
        print("  ✓ Compte supprimé.")
    else:
        print("  Suppression annulée.")


def admin_reinitialiser_mdp(user) -> None:
    titre("Réinitialiser un mot de passe")
    afficher_comptes(admin.lister_comptes(user))
    id_user = saisir_entier("ID du compte")
    admin.reinitialiser_mot_de_passe(user, id_user, saisir_nouveau_mdp())
    print("  ✓ Mot de passe réinitialisé.")


def admin_comptes_par_role(user) -> None:
    titre("Comptes par rôle")
    for role, nombre in admin.comptes_par_role(user).items():
        print(f"  {role:<15} {nombre}")


def lister_tous_les_cours(user) -> None:
    titre("Cours")
    afficher_cours(courses.lister_cours(user))


def telecharger_un_cours(user) -> None:
    titre("Télécharger un cours")
    afficher_cours(courses.lister_cours(user))
    id_cours = saisir_entier("ID du cours")
    telecharger(lambda dossier: courses.telecharger_cours(user, id_cours, dossier))


def supprimer_un_cours(user) -> None:
    """Utilisé par l'administrateur (tous les cours) et l'enseignant (les siens)."""
    titre("Supprimer un cours")
    liste = courses.mes_cours(user) if user.est_enseignant() else courses.lister_cours(user)
    afficher_cours(liste)
    id_cours = saisir_entier("ID du cours")
    print("  Attention : les devoirs déposés pour ce cours seront supprimés aussi.")
    if confirmer("Confirmer la suppression"):
        courses.supprimer_cours(user, id_cours)
        print("  ✓ Cours supprimé.")
    else:
        print("  Suppression annulée.")


def afficher_stats_cours(user) -> None:
    titre("Devoirs par cours")
    lignes = stats.devoirs_par_cours(user)
    if not lignes:
        print("  (aucun cours)")
        return
    print(f"  {'ID':<4} {'Cours':<28} {'Déposés':<9} {'Notés':<7} Moyenne")
    for s in lignes:
        moyenne = "-" if s.moyenne is None else f"{s.moyenne:.2f}"
        print(f"  {s.id_cours:<4} {s.titre:<28} {s.devoirs_deposes:<9} {s.devoirs_notes:<7} {moyenne}")
    print(f"  Total des cours publiés : {stats.total_cours(user)}")


# ============================================================================
# Actions de l'enseignant
# ============================================================================

def prof_publier(user) -> None:
    titre("Publier un cours")
    intitule = saisir("Titre")
    description = saisir("Description")
    chemin = saisir_chemin("Chemin du fichier (PDF ou TXT)")
    c = courses.publier_cours(user, intitule, description, chemin)
    print(f"  ✓ Cours publié : « {c.titre} » (id {c.id_cours}).")


def prof_mes_cours(user) -> None:
    titre("Mes cours")
    afficher_cours(courses.mes_cours(user))


def prof_modifier(user) -> None:
    titre("Modifier un cours")
    afficher_cours(courses.mes_cours(user))
    id_cours = saisir_entier("ID du cours")
    print("Laissez vide pour ne rien changer.")
    nouveau_titre = saisir("Nouveau titre") or None
    description = saisir("Nouvelle description") or None
    fichier = saisir_chemin("Nouveau fichier") or None
    courses.modifier_cours(user, id_cours, nouveau_titre, description, fichier)
    print("  ✓ Cours modifié.")


def _afficher_devoirs(user, id_cours: int):
    lignes = assignments.devoirs_du_cours(user, id_cours)
    if not lignes:
        print("  (aucun devoir déposé)")
        return lignes
    print(f"  {'ID':<4} {'Étudiant':<28} Note")
    for etudiant, devoir in lignes:
        print(f"  {devoir.id_devoir:<4} {etudiant.nom_complet:<28} {afficher_note(devoir.note)}")
    return lignes


def prof_devoirs(user) -> None:
    titre("Devoirs d'un cours")
    afficher_cours(courses.mes_cours(user))
    _afficher_devoirs(user, saisir_entier("ID du cours"))


def prof_telecharger_devoir(user) -> None:
    titre("Télécharger un devoir")
    afficher_cours(courses.mes_cours(user))
    if not _afficher_devoirs(user, saisir_entier("ID du cours")):
        return
    id_devoir = saisir_entier("ID du devoir")
    telecharger(lambda dossier: assignments.telecharger_devoir(user, id_devoir, dossier))


def prof_noter(user) -> None:
    titre("Noter un devoir")
    afficher_cours(courses.mes_cours(user))
    if not _afficher_devoirs(user, saisir_entier("ID du cours")):
        return
    id_devoir = saisir_entier("ID du devoir")
    note = saisir("Note sur 20")
    d = assignments.noter_devoir(user, id_devoir, note)
    print(f"  ✓ Note enregistrée : {afficher_note(d.note)}.")


# ============================================================================
# Actions de l'étudiant
# ============================================================================

def etu_deposer(user) -> None:
    titre("Déposer ou remplacer un devoir")
    afficher_cours(courses.lister_cours(user))
    id_cours = saisir_entier("ID du cours")
    existant = assignments.mon_devoir(user, id_cours)
    if existant is not None:
        etat = "déjà noté, il ne pourra pas être remplacé" if existant.est_note else "il sera remplacé"
        print(f"  Vous avez déjà déposé un devoir pour ce cours : {etat}.")
    chemin = saisir_chemin("Chemin du fichier (PDF ou TXT)")
    assignments.deposer_devoir(user, id_cours, chemin)
    print("  ✓ Devoir déposé.")


def etu_mes_notes(user) -> None:
    titre("Mes notes")
    lignes = assignments.mes_notes(user)
    if not lignes:
        print("  (aucun devoir déposé)")
        return
    print(f"  {'Cours':<28} Note")
    for cours, devoir in lignes:
        print(f"  {cours.titre:<28} {afficher_note(devoir.note)}")
    moyenne = assignments.ma_moyenne(user)
    print(f"  Moyenne : {'-' if moyenne is None else f'{moyenne:.2f} / 20'}")


def etu_progression(user) -> None:
    titre("Ma progression")
    p = stats.ma_progression(user)
    print(f"  {stats.barre_progression(p.pourcentage)}")
    print(f"  Devoirs rendus : {p.devoirs_rendus} sur {p.cours_publies} cours publiés")
    print(f"  Devoirs notés  : {p.devoirs_notes}")
    print(f"  Moyenne        : {'-' if p.moyenne is None else f'{p.moyenne:.2f} / 20'}")


# ============================================================================
# Menus
# ============================================================================

MENU_ADMIN = [
    ("Lister les comptes", admin_lister_comptes),
    ("Créer un compte", admin_creer_compte),
    ("Modifier un compte", admin_modifier_compte),
    ("Désactiver un compte", admin_desactiver),
    ("Réactiver un compte", admin_activer),
    ("Supprimer un compte", admin_supprimer),
    ("Réinitialiser un mot de passe", admin_reinitialiser_mdp),
    ("Nombre de comptes par rôle", admin_comptes_par_role),
    ("Lister les cours", lister_tous_les_cours),
    ("Télécharger un cours", telecharger_un_cours),
    ("Supprimer un cours", supprimer_un_cours),
    ("Devoirs par cours", afficher_stats_cours),
    ("Changer mon mot de passe", changer_mon_mdp),
]

MENU_ENSEIGNANT = [
    ("Publier un cours", prof_publier),
    ("Mes cours", prof_mes_cours),
    ("Modifier un cours", prof_modifier),
    ("Supprimer un cours", supprimer_un_cours),
    ("Devoirs d'un cours", prof_devoirs),
    ("Télécharger un devoir", prof_telecharger_devoir),
    ("Noter un devoir", prof_noter),
    ("Statistiques de mes cours", afficher_stats_cours),
    ("Changer mon mot de passe", changer_mon_mdp),
]

MENU_ETUDIANT = [
    ("Lister les cours", lister_tous_les_cours),
    ("Télécharger un cours", telecharger_un_cours),
    ("Déposer ou remplacer un devoir", etu_deposer),
    ("Mes notes", etu_mes_notes),
    ("Ma progression", etu_progression),
    ("Changer mon mot de passe", changer_mon_mdp),
]

MENUS = {ROLE_ADMIN: MENU_ADMIN, ROLE_ENSEIGNANT: MENU_ENSEIGNANT, ROLE_ETUDIANT: MENU_ETUDIANT}


def executer(action, user) -> None:
    """Lance une action ; toute erreur prévue est affichée sans arrêter le programme."""
    try:
        action(user)
    except (ValueError, PermissionError, OSError) as erreur:
        print(f"\n  ✗ {erreur}")


def menu_utilisateur(user) -> None:
    """Boucle du menu d'un utilisateur connecté, jusqu'à la déconnexion."""
    options = MENUS[user.role]
    while True:
        # Le compte a pu être désactivé ou supprimé pendant la session.
        try:
            user = auth.exiger_role(user, user.role)
        except PermissionError as erreur:
            print(f"\n  ✗ {erreur} Déconnexion.")
            return

        titre(f"Menu {user.role} - {user.nom_complet}")
        for i, (libelle, _) in enumerate(options, 1):
            print(f"  {i:>2}. {libelle}")
        print("   0. Se déconnecter")

        choix = saisir("Votre choix")
        if choix == "0":
            return
        if choix.isdigit() and 1 <= int(choix) <= len(options):
            executer(options[int(choix) - 1][1], user)
        else:
            print("\n  ✗ Choix invalide.")


# ============================================================================
# Accueil
# ============================================================================

def se_connecter() -> None:
    titre("Connexion")
    login = saisir("Login")
    user = auth.connecter(login, saisir_mdp())

    # Le compte administrateur par défaut doit changer son mot de passe d'abord.
    while auth.doit_changer_mot_de_passe(user):
        print("\n  Vous utilisez le mot de passe par défaut : veuillez le changer.")
        try:
            nouveau = saisir_nouveau_mdp()
            auth.changer_mot_de_passe(user, auth.ADMIN_MDP_DEFAUT, nouveau)
            user = auth.connecter(login, nouveau)
            print("  ✓ Mot de passe modifié.")
        except (ValueError, PermissionError) as erreur:
            print(f"\n  ✗ {erreur}")

    menu_utilisateur(user)


def s_inscrire() -> None:
    titre("Inscription")
    nom, prenom = saisir("Nom"), saisir("Prénom")
    role = choisir_role((ROLE_ENSEIGNANT, ROLE_ETUDIANT))
    login = saisir("Login")
    u = auth.inscrire(nom, prenom, role, login, saisir_nouveau_mdp())
    print(f"  ✓ Compte créé pour {u.nom_complet}. Vous pouvez vous connecter.")


def main() -> None:
    storage.init_db()
    if auth.creer_admin_par_defaut():
        print(f"Premier lancement : compte administrateur créé "
              f"({auth.ADMIN_LOGIN_DEFAUT} / {auth.ADMIN_MDP_DEFAUT}). "
              f"Le mot de passe devra être changé à la première connexion.")

    try:
        while True:
            titre("LMS simplifié")
            print("  1. Se connecter")
            print("  2. S'inscrire (enseignant ou étudiant)")
            print("  0. Quitter")
            choix = saisir("Votre choix")
            if choix == "0":
                break
            if choix == "1":
                executer(lambda _: se_connecter(), None)
            elif choix == "2":
                executer(lambda _: s_inscrire(), None)
            else:
                print("\n  ✗ Choix invalide.")
    except (EOFError, KeyboardInterrupt):
        print()
    print("Au revoir.")


if __name__ == "__main__":
    main()