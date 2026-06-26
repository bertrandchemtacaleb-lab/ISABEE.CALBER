"""
payments.py
-----------
Role : gerer le cycle de vie des paiements de ressources payantes.

Paiement exclusivement en presentiel : aucune integration Mobile
Money n'est prevue. Le flux est volontairement simple et adapte a un
encaissement physique :
1. l'utilisateur demande l'acces a un document payant (demander_paiement) ;
2. il se rend au service competent et regle le montant en especes ;
3. un administrateur constate l'encaissement et valide manuellement le
   paiement dans l'interface (valider_paiement), ce qui debloque le
   telechargement du document pour cet utilisateur uniquement.

Ce module ne realise aucun affichage : il est consomme par app.py
(cote etudiant) et par admin.py (validation des paiements).
"""

from datetime import datetime

from database import executer, recuperer_un, recuperer_tous
from models import Paiement
from utils import journaliser

FORMAT_DATE_HEURE = "%Y-%m-%d %H:%M:%S"


def demander_paiement(document_id: int, user_id: int) -> tuple[bool, str]:
    """
    Enregistre une demande de paiement pour un document payant.
    Le document reste indisponible au telechargement jusqu'a ce
    qu'un administrateur valide manuellement le paiement.
    """
    document = recuperer_un("SELECT * FROM subjects WHERE id = ?", (document_id,))
    if document is None:
        return False, "Document introuvable."
    if document["type_acces"] != "payant":
        return False, "Ce document est gratuit, aucun paiement n'est necessaire."

    existant = recuperer_un(
        "SELECT * FROM payments WHERE document_id = ? AND user_id = ?", (document_id, user_id)
    )
    if existant is not None:
        if existant["statut_paiement"] == "valide":
            return False, "Ce document a deja ete paye et valide."
        if existant["statut_paiement"] == "en_attente":
            return False, "Une demande de paiement est deja en attente de validation pour ce document."
        # statut "refuse" : on autorise une nouvelle demande en reactivant la ligne existante,
        # plutot que d'en creer une seconde (la table impose une seule ligne par couple document/utilisateur).
        executer(
            """
            UPDATE payments
            SET statut_paiement = 'en_attente', date_demande = ?,
                date_validation = NULL, valide_par = NULL, reference_caisse = NULL
            WHERE id = ?
            """,
            (datetime.now().strftime(FORMAT_DATE_HEURE), existant["id"]),
        )
        journaliser("Nouvelle demande de paiement", "succes", user_id=user_id, details=str(document_id))
        return True, "Nouvelle demande de paiement enregistree. Rendez-vous au service competent."

    executer(
        """
        INSERT INTO payments (document_id, user_id, montant, mode_paiement, statut_paiement)
        VALUES (?, ?, ?, 'presentiel', 'en_attente')
        """,
        (document_id, user_id, document["prix"]),
    )
    journaliser("Demande de paiement", "succes", user_id=user_id, details=str(document_id))
    return True, (
        "Demande de paiement enregistree. Rendez-vous au service competent pour regler "
        "le montant en presentiel, puis attendez la validation par un administrateur."
    )


def valider_paiement(paiement_id: int, valide_par: int, reference_caisse: str = "") -> tuple[bool, str]:
    """Valide manuellement un paiement, apres constat de l'encaissement en presentiel."""
    executer(
        """
        UPDATE payments
        SET statut_paiement = 'valide', date_validation = ?, valide_par = ?, reference_caisse = ?
        WHERE id = ?
        """,
        (datetime.now().strftime(FORMAT_DATE_HEURE), valide_par, reference_caisse or None, paiement_id),
    )
    journaliser("Validation paiement", "succes", user_id=valide_par, details=str(paiement_id))
    return True, "Paiement valide. Le document est desormais accessible a l'utilisateur."


def refuser_paiement(paiement_id: int, refuse_par: int) -> tuple[bool, str]:
    """Refuse un paiement (encaissement non constate ou litige)."""
    executer(
        """
        UPDATE payments SET statut_paiement = 'refuse', date_validation = ?, valide_par = ?
        WHERE id = ?
        """,
        (datetime.now().strftime(FORMAT_DATE_HEURE), refuse_par, paiement_id),
    )
    journaliser("Refus paiement", "succes", user_id=refuse_par, details=str(paiement_id))
    return True, "Paiement refuse."


def statut_paiement_utilisateur(document_id: int, user_id: int) -> str | None:
    """Retourne le statut de paiement de cet utilisateur pour ce document, ou None si aucune demande."""
    ligne = recuperer_un(
        "SELECT statut_paiement FROM payments WHERE document_id = ? AND user_id = ?",
        (document_id, user_id),
    )
    return ligne["statut_paiement"] if ligne else None


def utilisateur_a_acces(type_acces: str, document_id: int, user_id: int) -> bool:
    """
    Determine si un utilisateur peut telecharger un document : toujours
    vrai pour un document gratuit, vrai pour un document payant
    uniquement si le paiement de cet utilisateur a ete valide.
    """
    if type_acces != "payant":
        return True
    return statut_paiement_utilisateur(document_id, user_id) == "valide"


def paiements_en_attente_detailles() -> list[dict]:
    """
    Paiements en attente de validation, avec les informations du
    document et de l'utilisateur deja jointes, pretes pour
    l'affichage administrateur.
    """
    lignes = recuperer_tous(
        """
        SELECT p.*, s.titre AS titre_document,
               u.nom AS nom_utilisateur, u.prenom AS prenom_utilisateur,
               u.matricule AS matricule_utilisateur
        FROM payments p
        JOIN subjects s ON s.id = p.document_id
        JOIN users u ON u.id = p.user_id
        WHERE p.statut_paiement = 'en_attente'
        ORDER BY p.date_demande
        """
    )
    return [dict(l) for l in lignes]


def paiements_utilisateur(user_id: int) -> list[Paiement]:
    """Historique des demandes de paiement d'un utilisateur, plus recentes en premier."""
    lignes = recuperer_tous(
        "SELECT * FROM payments WHERE user_id = ? ORDER BY date_demande DESC", (user_id,)
    )
    return [Paiement.depuis_ligne(l) for l in lignes]


def nombre_paiements_valides() -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM payments WHERE statut_paiement = 'valide'")
    return ligne["total"] if ligne else 0


def nombre_paiements_en_attente() -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM payments WHERE statut_paiement = 'en_attente'")
    return ligne["total"] if ligne else 0


def nombre_ressources_payantes() -> int:
    ligne = recuperer_un("SELECT COUNT(*) AS total FROM subjects WHERE type_acces = 'payant'")
    return ligne["total"] if ligne else 0
