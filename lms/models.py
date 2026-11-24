"""
models.py - Classes métier du LMS simplifié.

Ce module ne contient aucune logique d'affichage ni d'accès aux données :
il définit seulement ce qu'est un Utilisateur, un Cours et un Devoir,
et vérifie que leurs valeurs sont cohérentes.
"""

from dataclasses import dataclass
from typing import Optional

# --- Constantes -------------------------------------------------------------

ROLE_ADMIN = "administrateur"
ROLE_ENSEIGNANT = "enseignant"
ROLE_ETUDIANT = "étudiant"
ROLES = (ROLE_ADMIN, ROLE_ENSEIGNANT, ROLE_ETUDIANT)

NOTE_MIN = 0.0
NOTE_MAX = 20.0


# --- Utilisateur ------------------------------------------------------------

@dataclass
class Utilisateur:
    """Un compte de la plateforme (administrateur, enseignant ou étudiant)."""

    id_user: Optional[int]   # None tant que l'utilisateur n'est pas enregistré
    nom: str
    prenom: str
    role: str
    login: str
    mot_de_passe: str        # hash du mot de passe, jamais le texte en clair
    actif: bool = True       # False = compte désactivé par un administrateur

    def __post_init__(self):
        # Nettoyage des espaces superflus
        self.nom = self.nom.strip()
        self.prenom = self.prenom.strip()
        self.login = self.login.strip()

        # Validation
        if not self.nom or not self.prenom:
            raise ValueError("Le nom et le prénom sont obligatoires.")
        if not self.login:
            raise ValueError("Le login est obligatoire.")
        if self.role not in ROLES:
            raise ValueError(f"Rôle invalide : {self.role!r}.")

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}"

    def est_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def est_enseignant(self) -> bool:
        return self.role == ROLE_ENSEIGNANT

    def est_etudiant(self) -> bool:
        return self.role == ROLE_ETUDIANT


# --- Cours ------------------------------------------------------------------

@dataclass
class Cours:
    """Un cours publié par un enseignant."""

    id_cours: Optional[int]
    titre: str
    description: str
    enseignant: int          # Id_user de l'enseignant propriétaire
    fichier: str             # chemin vers le document (PDF ou texte)

    def __post_init__(self):
        self.titre = self.titre.strip()
        self.description = self.description.strip()
        if not self.titre:
            raise ValueError("Le titre du cours est obligatoire.")


# --- Devoir -----------------------------------------------------------------

@dataclass
class Devoir:
    """Un devoir déposé par un étudiant pour un cours."""

    id_devoir: Optional[int]
    id_cours: int
    etudiant: int            # Id_user de l'étudiant
    fichier: str             # nom du fichier déposé
    note: Optional[float] = None   # None tant que le devoir n'est pas noté

    def __post_init__(self):
        if self.note is not None:
            self._verifier_note(self.note)

    @staticmethod
    def _verifier_note(note: float) -> None:
        if not (NOTE_MIN <= note <= NOTE_MAX):
            raise ValueError(
                f"La note doit être comprise entre {NOTE_MIN} et {NOTE_MAX}."
            )

    @property
    def est_note(self) -> bool:
        return self.note is not None

    def attribuer_note(self, note: float) -> None:
        """Enregistre la note après vérification de sa validité."""
        self._verifier_note(note)
        self.note = float(note)


if __name__ == "__main__":
    # Petit test rapide : python models.py
    u = Utilisateur(None, " Ben Ali ", "Sami", ROLE_ETUDIANT, "sami", "hash")
    d = Devoir(None, 1, 2, "tp1.pdf")
    d.attribuer_note(15.5)
    print(u.nom_complet, "-", d.note)