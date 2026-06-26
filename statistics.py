"""
statistics.py
-------------
Role : calculer les indicateurs et preparer les donnees affichees sur
le tableau de bord administrateur (compteurs, listes recentes,
series pour les graphiques Plotly).

Ce module ne dessine aucun graphique : il retourne des structures de
donnees simples (dictionnaires, listes) que admin.py transmet a
Plotly. Cette separation permet de tester les calculs independamment
de l'affichage.

Nouveau en V2 : series temporelles mensuelles (telechargements,
documents ajoutes, inscriptions), demandees explicitement par le
cahier des charges et absentes de la V1, qui ne proposait qu'une
serie quotidienne sur 30 jours. Repartition gratuit/payant, pour
visualiser le poids de la monetisation parmi les documents publies.
"""

from database import recuperer_un, recuperer_tous


def nombre_documents(statut: str = "valide") -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM subjects WHERE statut = ?", (statut,))
    return ligne["total"] if ligne else 0


def nombre_utilisateurs(role: str) -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM users WHERE role = ?", (role,))
    return ligne["total"] if ligne else 0


def nombre_telechargements() -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM downloads")
    return ligne["total"] if ligne else 0


def indicateurs_generaux() -> dict:
    """Regroupe les indicateurs cles affiches en tete du tableau de bord."""
    return {
        "documents_valides": nombre_documents("valide"),
        "documents_en_attente": nombre_documents("en_attente"),
        "etudiants": nombre_utilisateurs("etudiant"),
        "enseignants": nombre_utilisateurs("enseignant"),
        "contributeurs": nombre_utilisateurs("contributeur"),
        "administrateurs": nombre_utilisateurs("administrateur"),
        "telechargements": nombre_telechargements(),
    }


def telechargements_par_jour(nb_jours: int = 30) -> list[dict]:
    """Serie temporelle quotidienne du nombre de telechargements, pour une courbe Plotly."""
    lignes = recuperer_tous(
        """
        SELECT date(date_telechargement) AS jour, COUNT(*) AS total
        FROM downloads
        WHERE date(date_telechargement) >= date('now', ?)
        GROUP BY jour
        ORDER BY jour
        """,
        (f"-{nb_jours} days",),
    )
    return [{"jour": l["jour"], "total": l["total"]} for l in lignes]


def telechargements_par_mois(nb_mois: int = 12) -> list[dict]:
    """Serie temporelle mensuelle des telechargements, sur les nb_mois derniers mois."""
    lignes = recuperer_tous(
        """
        SELECT strftime('%Y-%m', date_telechargement) AS mois, COUNT(*) AS total
        FROM downloads
        WHERE date(date_telechargement) >= date('now', ?)
        GROUP BY mois
        ORDER BY mois
        """,
        (f"-{nb_mois} months",),
    )
    return [{"mois": l["mois"], "total": l["total"]} for l in lignes]


def documents_par_mois(nb_mois: int = 12) -> list[dict]:
    """Serie temporelle mensuelle des documents ajoutes (tous statuts confondus)."""
    lignes = recuperer_tous(
        """
        SELECT strftime('%Y-%m', date_ajout) AS mois, COUNT(*) AS total
        FROM subjects
        WHERE date(date_ajout) >= date('now', ?)
        GROUP BY mois
        ORDER BY mois
        """,
        (f"-{nb_mois} months",),
    )
    return [{"mois": l["mois"], "total": l["total"]} for l in lignes]


def nouvelles_inscriptions_par_mois(nb_mois: int = 12) -> list[dict]:
    """Serie temporelle mensuelle des nouvelles inscriptions d'utilisateurs."""
    lignes = recuperer_tous(
        """
        SELECT strftime('%Y-%m', date_inscription) AS mois, COUNT(*) AS total
        FROM users
        WHERE date(date_inscription) >= date('now', ?)
        GROUP BY mois
        ORDER BY mois
        """,
        (f"-{nb_mois} months",),
    )
    return [{"mois": l["mois"], "total": l["total"]} for l in lignes]


def documents_par_type() -> list[dict]:
    """Repartition des documents valides par type, pour un diagramme circulaire."""
    lignes = recuperer_tous(
        """
        SELECT type_document, COUNT(*) AS total
        FROM subjects
        WHERE statut = 'valide'
        GROUP BY type_document
        ORDER BY total DESC
        """
    )
    return [{"type_document": l["type_document"], "total": l["total"]} for l in lignes]


def documents_par_acces() -> list[dict]:
    """Repartition gratuit / payant parmi les documents valides."""
    lignes = recuperer_tous(
        """
        SELECT type_acces, COUNT(*) AS total
        FROM subjects
        WHERE statut = 'valide'
        GROUP BY type_acces
        """
    )
    return [{"type_acces": l["type_acces"], "total": l["total"]} for l in lignes]


def documents_par_filiere() -> list[dict]:
    """Repartition des documents valides par filiere, pour un histogramme."""
    lignes = recuperer_tous(
        """
        SELECT filiere, COUNT(*) AS total
        FROM subjects
        WHERE statut = 'valide'
        GROUP BY filiere
        ORDER BY total DESC
        """
    )
    return [{"filiere": l["filiere"], "total": l["total"]} for l in lignes]


def documents_les_plus_telecharges(limite: int = 5) -> list[dict]:
    lignes = recuperer_tous(
        """
        SELECT s.titre, COUNT(d.id) AS total
        FROM subjects s
        JOIN downloads d ON d.document_id = s.id
        GROUP BY s.id
        ORDER BY total DESC
        LIMIT ?
        """,
        (limite,),
    )
    return [{"titre": l["titre"], "total": l["total"]} for l in lignes]
