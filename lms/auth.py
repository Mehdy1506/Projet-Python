"""
auth.py - Authentification et contrôle des rôles du LMS.

Ce module s'occupe de :
  - hacher et vérifier les mots de passe (jamais stockés en clair) ;
  - l'inscription libre (enseignant ou étudiant uniquement) ;
  - la connexion ;
  - la création du compte administrateur par défaut ;
  - le contrôle des droits (exiger_role) utilisé par les autres modules.

Convention d'erreurs :
  - ValueError      : donnée invalide (login déjà pris, mot de passe trop court...) ;
  - PermissionError : action interdite pour ce rôle ou compte désactivé.
"""

import hashlib
import hmac
import secrets
from typing import Optional

import storage
from models import (ROLE_ADMIN, ROLE_ENSEIGNANT, ROLE_ETUDIANT, Utilisateur)

# --- Paramètres -------------------------------------------------------------

ITERATIONS = 200_000          # coût du hachage PBKDF2
LONGUEUR_MIN_MDP = 6

# Compte administrateur créé au premier lancement.
ADMIN_LOGIN_DEFAUT = "admin"
ADMIN_MDP_DEFAUT = "admin123"

# Rôles autorisés pour l'inscription libre (pas d'auto-inscription admin).
ROLES_INSCRIPTION = (ROLE_ENSEIGNANT, ROLE_ETUDIANT)


# --- Mots de passe ----------------------------------------------------------

def hasher_mot_de_passe(mot_de_passe: str) -> str:
    """Retourne 'pbkdf2$itérations$sel$hash' (sel aléatoire propre à chaque mot de passe)."""
    sel = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${sel.hex()}${h.hex()}"


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    """Vérifie un mot de passe contre le hash stocké."""
    try:
        _, iterations, sel_hex, hash_hex = hash_stocke.split("$")
        h = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"),
                                bytes.fromhex(sel_hex), int(iterations))
    except (ValueError, TypeError):
        return False      # hash mal formé : on refuse plutôt que de planter
    # compare_digest : comparaison en temps constant
    return hmac.compare_digest(h.hex(), hash_hex)


def valider_mot_de_passe(mot_de_passe: str) -> None:
    if len(mot_de_passe) < LONGUEUR_MIN_MDP:
        raise ValueError(
            f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MDP} caractères.")


# --- Compte administrateur par défaut ---------------------------------------

def creer_admin_par_defaut() -> bool:
    """Crée le compte admin par défaut s'il n'existe aucun administrateur.
    Retourne True si le compte vient d'être créé."""
    if storage.lister_utilisateurs(ROLE_ADMIN):
        return False
    storage.ajouter_utilisateur(Utilisateur(
        None, "Administrateur", "Compte", ROLE_ADMIN,
        ADMIN_LOGIN_DEFAUT, hasher_mot_de_passe(ADMIN_MDP_DEFAUT)))
    return True


def doit_changer_mot_de_passe(u: Utilisateur) -> bool:
    """True si l'utilisateur est un admin qui a encore le mot de passe par défaut.
    L'interface doit alors lui imposer de le changer avant toute autre action."""
    return u.est_admin() and verifier_mot_de_passe(ADMIN_MDP_DEFAUT, u.mot_de_passe)


# --- Inscription et connexion -----------------------------------------------

def inscrire(nom: str, prenom: str, role: str, login: str,
             mot_de_passe: str) -> Utilisateur:
    """Inscription libre : uniquement enseignant ou étudiant."""
    if role not in ROLES_INSCRIPTION:
        raise PermissionError(
            "L'inscription n'est possible que pour un enseignant ou un étudiant.")
    valider_mot_de_passe(mot_de_passe)
    u = Utilisateur(None, nom, prenom, role, login,
                    hasher_mot_de_passe(mot_de_passe))
    return storage.ajouter_utilisateur(u)


def connecter(login: str, mot_de_passe: str) -> Utilisateur:
    """Retourne l'utilisateur si login et mot de passe sont corrects."""
    u = storage.get_utilisateur_par_login(login)
    # Même message dans les deux cas : on ne révèle pas si le login existe.
    if u is None or not verifier_mot_de_passe(mot_de_passe, u.mot_de_passe):
        raise ValueError("Login ou mot de passe incorrect.")
    if not u.actif:
        raise PermissionError("Ce compte est désactivé.")
    return u


def changer_mot_de_passe(u: Utilisateur, ancien: str, nouveau: str) -> None:
    """Change le mot de passe après vérification de l'ancien."""
    if not verifier_mot_de_passe(ancien, u.mot_de_passe):
        raise ValueError("Ancien mot de passe incorrect.")
    valider_mot_de_passe(nouveau)
    if nouveau == ADMIN_MDP_DEFAUT:
        raise ValueError("Choisissez un mot de passe différent de celui par défaut.")
    u.mot_de_passe = hasher_mot_de_passe(nouveau)
    storage.modifier_utilisateur(u)


# --- Contrôle des droits ----------------------------------------------------

def exiger_role(u: Optional[Utilisateur], *roles: str) -> Utilisateur:
    """Lève PermissionError si l'utilisateur n'est pas connecté, n'existe plus,
    est désactivé ou n'a pas l'un des rôles demandés.

    Le compte est relu dans la base : l'objet en mémoire a pu devenir obsolète
    (compte désactivé ou supprimé pendant la session). Retourne l'utilisateur
    à jour. À appeler au début de chaque action sensible."""
    if u is None:
        raise PermissionError("Vous devez être connecté.")
    courant = storage.get_utilisateur(u.id_user)
    if courant is None:
        raise PermissionError("Ce compte n'existe plus.")
    if not courant.actif:
        raise PermissionError("Ce compte est désactivé.")
    if courant.role not in roles:
        raise PermissionError("Vous n'avez pas le droit d'effectuer cette action.")
    return courant


if __name__ == "__main__":
    # Test rapide dans une base temporaire : python auth.py
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        storage.DB_PATH = Path(tmp) / "test.db"
        storage.init_db()

        print("Admin créé :", creer_admin_par_defaut(), "| 2e appel :", creer_admin_par_defaut())

        admin = connecter("admin", "admin123")
        print("Admin doit changer son mdp :", doit_changer_mot_de_passe(admin))
        changer_mot_de_passe(admin, "admin123", "NouveauMdp1")
        print("Après changement :", doit_changer_mot_de_passe(connecter("admin", "NouveauMdp1")))

        etu = inscrire("Ben Ali", "Sami", ROLE_ETUDIANT, "sami", "secret1")
        print("Inscrit :", etu.nom_complet, "| hash :", etu.mot_de_passe[:25] + "...")

        for essai in (lambda: inscrire("X", "Y", ROLE_ADMIN, "hack", "secret1"),
                      lambda: inscrire("X", "Y", ROLE_ETUDIANT, "SAMI", "secret1"),
                      lambda: inscrire("X", "Y", ROLE_ETUDIANT, "court", "123"),
                      lambda: connecter("sami", "mauvais"),
                      lambda: exiger_role(etu, ROLE_ENSEIGNANT, ROLE_ADMIN)):
            try:
                essai()
                print("ERREUR : aucune exception")
            except (ValueError, PermissionError) as e:
                print(type(e).__name__, ":", e)

        etu.actif = False
        storage.modifier_utilisateur(etu)
        try:
            connecter("sami", "secret1")
        except PermissionError as e:
            print("PermissionError :", e)