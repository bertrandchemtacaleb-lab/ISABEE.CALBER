"""
settings.py
-----------
Role : gerer les parametres globaux de la plateforme (table settings),
modifiables par un administrateur depuis l'interface, sans intervention
sur le code source.

Nouveau en V2 : parametres de securite (duree d'expiration de session)
et de monetisation (prix par defaut d'un document payant) exposes ici,
afin que ces valeurs soient ajustables sans modification du code.
"""

from database import executer, recuperer_un, recuperer_tous
from utils import journaliser
from datetime import datetime

PARAMETRES_PAR_DEFAUT = {
    "nom_etablissement": ("ISABEE", "Nom affiche dans l'en-tete de la plateforme."),
    "taille_max_pdf_mo": ("25", "Taille maximale autorisee pour un document, en megaoctets."),
    "validation_obligatoire": ("oui", "Un document doit etre valide avant d'etre visible des etudiants."),
    "moderation_commentaires": ("oui", "Les commentaires sont soumis a moderation avant publication."),
    "expiration_session_minutes": ("30", "Duree d'inactivite, en minutes, avant deconnexion automatique."),
    "prix_document_payant_defaut": ("300", "Prix par defaut, en FCFA, propose pour un nouveau document payant."),
}


def initialiser_parametres_par_defaut() -> None:
    """Insere les parametres par defaut s'ils sont absents de la base."""
    for cle, (valeur, description) in PARAMETRES_PAR_DEFAUT.items():
        if recuperer_un("SELECT id FROM settings WHERE cle = ?", (cle,)) is None:
            executer(
                "INSERT INTO settings (cle, valeur, description) VALUES (?, ?, ?)",
                (cle, valeur, description),
            )


def obtenir_parametre(cle: str, valeur_defaut: str = "") -> str:
    ligne = recuperer_un("SELECT valeur FROM settings WHERE cle = ?", (cle,))
    return ligne["valeur"] if ligne else valeur_defaut


def obtenir_parametre_entier(cle: str, valeur_defaut: int) -> int:
    """Variante typee de obtenir_parametre pour les valeurs numeriques (minutes, FCFA, Mo)."""
    valeur = obtenir_parametre(cle, str(valeur_defaut))
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return valeur_defaut


def definir_parametre(cle: str, valeur: str, modifie_par: int) -> None:
    executer(
        "UPDATE settings SET valeur = ?, modifie_par = ?, date_modification = ? WHERE cle = ?",
        (valeur, modifie_par, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cle),
    )
    journaliser("Modification parametre", "succes", user_id=modifie_par, details=f"{cle} = {valeur}")


def lister_parametres() -> list[dict]:
    lignes = recuperer_tous("SELECT * FROM settings ORDER BY cle")
    return [dict(l) for l in lignes]
