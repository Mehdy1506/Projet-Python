"""
storage.py - Accès à la base de données SQLite du LMS.

Ce module est le seul à écrire du SQL. Les autres modules (auth, courses,
assignments, ...) l'appellent avec des objets de models.py et récupèrent des
objets de models.py : ils ne connaissent ni les tables ni les requêtes.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple

from models import Cours, Devoir, Utilisateur

# --- Emplacement de la base -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "lms.db"   # modifiable (ex. dans les tests)

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id_user      INTEGER PRIMARY KEY AUTOINCREMENT,
    nom          TEXT NOT NULL,
    prenom       TEXT NOT NULL,
    role         TEXT NOT NULL
                 CHECK (role IN ('administrateur', 'enseignant', 'étudiant')),
    login        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    mot_de_passe TEXT NOT NULL,
    actif        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cours (
    id_cours    INTEGER PRIMARY KEY AUTOINCREMENT,
    titre       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    enseignant  INTEGER NOT NULL
                REFERENCES utilisateurs(id_user) ON DELETE CASCADE,
    fichier     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS devoirs (
    id_devoir INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cours  INTEGER NOT NULL
              REFERENCES cours(id_cours) ON DELETE CASCADE,
    etudiant  INTEGER NOT NULL
              REFERENCES utilisateurs(id_user) ON DELETE CASCADE,
    fichier   TEXT NOT NULL,
    note      REAL
              CHECK (note IS NULL OR (note >= 0 AND note <= 20)),
    UNIQUE (id_cours, etudiant)   -- un seul devoir par étudiant et par cours
);
"""


# --- Connexion --------------------------------------------------------------

@contextmanager
def _connexion():
    """Ouvre une connexion, valide la transaction à la fin (commit),
    l'annule en cas d'erreur (rollback) et ferme toujours la connexion."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row            # accès aux colonnes par nom
    conn.execute("PRAGMA foreign_keys = ON")  # désactivé par défaut dans SQLite
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Crée les tables si elles n'existent pas (à appeler au démarrage)."""
    with _connexion() as conn:
        conn.executescript(SCHEMA)


# --- Conversion ligne SQL -> objet ------------------------------------------

def _vers_utilisateur(row: sqlite3.Row) -> Utilisateur:
    return Utilisateur(row["id_user"], row["nom"], row["prenom"], row["role"],
                       row["login"], row["mot_de_passe"], bool(row["actif"]))


def _vers_cours(row: sqlite3.Row) -> Cours:
    return Cours(row["id_cours"], row["titre"], row["description"],
                 row["enseignant"], row["fichier"])


def _vers_devoir(row: sqlite3.Row) -> Devoir:
    return Devoir(row["id_devoir"], row["id_cours"], row["etudiant"],
                  row["fichier"], row["note"])


# --- Utilisateurs -----------------------------------------------------------

def ajouter_utilisateur(u: Utilisateur) -> Utilisateur:
    """Enregistre l'utilisateur, lui attribue son id et le retourne."""
    try:
        with _connexion() as conn:
            cur = conn.execute(
                "INSERT INTO utilisateurs (nom, prenom, role, login, "
                "mot_de_passe, actif) VALUES (?, ?, ?, ?, ?, ?)",
                (u.nom, u.prenom, u.role, u.login, u.mot_de_passe, int(u.actif)),
            )
            u.id_user = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Ce login est déjà utilisé.") from None
    return u


def get_utilisateur(id_user: int) -> Optional[Utilisateur]:
    with _connexion() as conn:
        row = conn.execute("SELECT * FROM utilisateurs WHERE id_user = ?",
                           (id_user,)).fetchone()
    return _vers_utilisateur(row) if row else None


def get_utilisateur_par_login(login: str) -> Optional[Utilisateur]:
    with _connexion() as conn:
        row = conn.execute("SELECT * FROM utilisateurs WHERE login = ?",
                           (login.strip(),)).fetchone()
    return _vers_utilisateur(row) if row else None


def lister_utilisateurs(role: Optional[str] = None) -> List[Utilisateur]:
    """Tous les utilisateurs, ou seulement ceux d'un rôle donné."""
    sql, params = "SELECT * FROM utilisateurs", ()
    if role is not None:
        sql, params = sql + " WHERE role = ?", (role,)
    with _connexion() as conn:
        rows = conn.execute(sql + " ORDER BY nom, prenom", params).fetchall()
    return [_vers_utilisateur(r) for r in rows]


def modifier_utilisateur(u: Utilisateur) -> None:
    try:
        with _connexion() as conn:
            cur = conn.execute(
                "UPDATE utilisateurs SET nom=?, prenom=?, role=?, login=?, "
                "mot_de_passe=?, actif=? WHERE id_user=?",
                (u.nom, u.prenom, u.role, u.login, u.mot_de_passe,
                 int(u.actif), u.id_user),
            )
            if cur.rowcount == 0:
                raise ValueError("Utilisateur introuvable.")
    except sqlite3.IntegrityError:
        raise ValueError("Ce login est déjà utilisé.") from None


def supprimer_utilisateur(id_user: int) -> bool:
    """Supprime l'utilisateur ET (en cascade) ses cours et ses devoirs."""
    with _connexion() as conn:
        cur = conn.execute("DELETE FROM utilisateurs WHERE id_user = ?",
                           (id_user,))
    return cur.rowcount > 0


# --- Cours ------------------------------------------------------------------

def ajouter_cours(c: Cours) -> Cours:
    try:
        with _connexion() as conn:
            cur = conn.execute(
                "INSERT INTO cours (titre, description, enseignant, fichier) "
                "VALUES (?, ?, ?, ?)",
                (c.titre, c.description, c.enseignant, c.fichier),
            )
            c.id_cours = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Enseignant inexistant.") from None
    return c


def get_cours(id_cours: int) -> Optional[Cours]:
    with _connexion() as conn:
        row = conn.execute("SELECT * FROM cours WHERE id_cours = ?",
                           (id_cours,)).fetchone()
    return _vers_cours(row) if row else None


def lister_cours(enseignant: Optional[int] = None) -> List[Cours]:
    """Tous les cours, ou seulement ceux d'un enseignant."""
    sql, params = "SELECT * FROM cours", ()
    if enseignant is not None:
        sql, params = sql + " WHERE enseignant = ?", (enseignant,)
    with _connexion() as conn:
        rows = conn.execute(sql + " ORDER BY titre", params).fetchall()
    return [_vers_cours(r) for r in rows]


def modifier_cours(c: Cours) -> None:
    with _connexion() as conn:
        cur = conn.execute(
            "UPDATE cours SET titre=?, description=?, enseignant=?, fichier=? "
            "WHERE id_cours=?",
            (c.titre, c.description, c.enseignant, c.fichier, c.id_cours),
        )
        if cur.rowcount == 0:
            raise ValueError("Cours introuvable.")


def supprimer_cours(id_cours: int) -> bool:
    """Supprime le cours ET (en cascade) les devoirs qui lui sont liés."""
    with _connexion() as conn:
        cur = conn.execute("DELETE FROM cours WHERE id_cours = ?", (id_cours,))
    return cur.rowcount > 0


# --- Devoirs ----------------------------------------------------------------

def ajouter_devoir(d: Devoir) -> Devoir:
    try:
        with _connexion() as conn:
            cur = conn.execute(
                "INSERT INTO devoirs (id_cours, etudiant, fichier, note) "
                "VALUES (?, ?, ?, ?)",
                (d.id_cours, d.etudiant, d.fichier, d.note),
            )
            d.id_devoir = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise ValueError("Un devoir a déjà été déposé pour ce cours.") from None
        raise ValueError("Cours ou étudiant inexistant.") from None
    return d


def get_devoir(id_devoir: int) -> Optional[Devoir]:
    with _connexion() as conn:
        row = conn.execute("SELECT * FROM devoirs WHERE id_devoir = ?",
                           (id_devoir,)).fetchone()
    return _vers_devoir(row) if row else None


def lister_devoirs(id_cours: Optional[int] = None,
                   etudiant: Optional[int] = None) -> List[Devoir]:
    """Devoirs filtrés (facultativement) par cours et/ou par étudiant."""
    conditions, params = [], []
    if id_cours is not None:
        conditions.append("id_cours = ?")
        params.append(id_cours)
    if etudiant is not None:
        conditions.append("etudiant = ?")
        params.append(etudiant)
    sql = "SELECT * FROM devoirs"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    with _connexion() as conn:
        rows = conn.execute(sql + " ORDER BY id_devoir", params).fetchall()
    return [_vers_devoir(r) for r in rows]


def modifier_devoir(d: Devoir) -> None:
    """Met à jour un devoir (utilisé surtout pour enregistrer la note)."""
    with _connexion() as conn:
        cur = conn.execute(
            "UPDATE devoirs SET fichier=?, note=? WHERE id_devoir=?",
            (d.fichier, d.note, d.id_devoir),
        )
        if cur.rowcount == 0:
            raise ValueError("Devoir introuvable.")


def supprimer_devoir(id_devoir: int) -> bool:
    with _connexion() as conn:
        cur = conn.execute("DELETE FROM devoirs WHERE id_devoir = ?",
                           (id_devoir,))
    return cur.rowcount > 0


# --- Requêtes pour les statistiques -----------------------------------------

def compter_cours() -> int:
    with _connexion() as conn:
        return conn.execute("SELECT COUNT(*) FROM cours").fetchone()[0]


def compter_devoirs_par_cours() -> List[Tuple[int, str, int]]:
    """Liste de (id_cours, titre, nombre de devoirs), y compris les cours
    sans devoir (LEFT JOIN)."""
    with _connexion() as conn:
        rows = conn.execute(
            "SELECT c.id_cours, c.titre, COUNT(d.id_devoir) AS nb "
            "FROM cours c LEFT JOIN devoirs d ON d.id_cours = c.id_cours "
            "GROUP BY c.id_cours ORDER BY c.titre"
        ).fetchall()
    return [(r["id_cours"], r["titre"], r["nb"]) for r in rows]


def compter_utilisateurs_par_role() -> dict:
    with _connexion() as conn:
        rows = conn.execute(
            "SELECT role, COUNT(*) AS nb FROM utilisateurs GROUP BY role"
        ).fetchall()
    return {r["role"]: r["nb"] for r in rows}


def moyenne_etudiant(id_user: int) -> Optional[float]:
    """Moyenne des notes d'un étudiant (None s'il n'a aucune note)."""
    with _connexion() as conn:
        row = conn.execute(
            "SELECT AVG(note) FROM devoirs "
            "WHERE etudiant = ? AND note IS NOT NULL", (id_user,)
        ).fetchone()
    return row[0]


if __name__ == "__main__":
    # Test rapide dans un dossier temporaire : python storage.py
    import tempfile
    from models import ROLE_ENSEIGNANT, ROLE_ETUDIANT

    with tempfile.TemporaryDirectory() as tmp:
        DB_PATH = Path(tmp) / "test.db"
        init_db()

        prof = ajouter_utilisateur(
            Utilisateur(None, "Trabelsi", "Ali", ROLE_ENSEIGNANT, "ali", "h1"))
        etu = ajouter_utilisateur(
            Utilisateur(None, "Ben Ali", "Sami", ROLE_ETUDIANT, "sami", "h2"))
        try:
            ajouter_utilisateur(
                Utilisateur(None, "X", "Y", ROLE_ETUDIANT, "SAMI", "h3"))
        except ValueError as e:
            print("Doublon refusé :", e)

        cours = ajouter_cours(Cours(None, "Python", "Bases", prof.id_user, "p.pdf"))
        devoir = ajouter_devoir(Devoir(None, cours.id_cours, etu.id_user, "tp1.pdf"))
        devoir.attribuer_note(16)
        modifier_devoir(devoir)

        print("Moyenne :", moyenne_etudiant(etu.id_user))
        print("Devoirs par cours :", compter_devoirs_par_cours())
        print("Comptes par rôle :", compter_utilisateurs_par_role())

        supprimer_cours(cours.id_cours)
        print("Devoirs après suppression du cours :", lister_devoirs())