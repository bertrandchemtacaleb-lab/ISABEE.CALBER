"""
utils.py
--------
Role : regrouper les fonctions transverses utilisees par plusieurs
modules, afin d'eviter la duplication de code.

Contient notamment :
- l'ecriture dans le journal systeme (table logs) ;
- la recuperation de l'adresse IP du client ;
- la validation et l'enregistrement des fichiers PDF et des photos
  de profil ;
- l'echappement HTML systematique des donnees utilisateur avant tout
  affichage dans un bloc unsafe_allow_html ;
- des fonctions de formatage de date.

Ce module ne doit jamais importer admin.py, app.py ni les autres
modules de presentation : il se situe en bas de la hierarchie de
dependances et peut etre importe par n'importe quel autre fichier.

Corrections de securite apportees en V2 (voir audit) :
- fichier_est_pdf_valide() verifie desormais la signature binaire
  reelle du fichier (les 5 premiers octets doivent etre %PDF-), et
  non plus seulement son extension, qui se renomme trivialement.
- echapper_html() est ajoutee pour eliminer la faille XSS stockee
  identifiee dans le tableau de bord administrateur (titres de
  documents et noms d'utilisateurs injectes sans echappement dans du
  HTML brut).
"""

from datetime import datetime
from pathlib import Path
import html as _html_stdlib
import uuid

import streamlit as st

from database import executer, DOCUMENTS_DIR, PHOTOS_DIR

# ---------------------------------------------------------------------
# Limites par defaut. La limite de taille des PDF est aussi exposee
# comme parametre systeme modifiable (settings.py, cle
# "taille_max_pdf_mo") ; la constante ci-dessous n'est qu'une valeur
# de repli si ce parametre est introuvable.
# ---------------------------------------------------------------------
TAILLE_MAX_PDF_MO_DEFAUT = 25
TAILLE_MAX_PHOTO_MO = 5
EXTENSIONS_PHOTO_VALIDES = (".jpg", ".jpeg", ".png")

# ---------------------------------------------------------------------
# Icones professionnelles (widgets natifs Streamlit uniquement)
# ---------------------------------------------------------------------
# Streamlit ne supporte pas nativement la bibliotheque lucide-react
# (reservee aux interfaces React/HTML) dans les parametres icon= de
# ses propres widgets (st.button, st.download_button, st.expander).
# Pour ces emplacements precis, l'equivalent natif et tout aussi
# sobre est l'ensemble des "Material Symbols" (icon=":material/nom:").
# Pour tout affichage personnalise (sidebar, barre superieure), voir
# icons.py qui fournit un jeu d'icones Lucide-style en SVG inline.
ICONES = {
    "Home": "home",
    "FileText": "description",
    "Users": "group",
    "Search": "search",
    "Download": "download",
    "Settings": "settings",
    "BarChart": "bar_chart",
    "Trash": "delete",
    "Edit": "edit",
    "Bell": "notifications",
}


def icone(nom: str) -> str:
    """Retourne la chaine d'icone Material Symbols utilisable par Streamlit."""
    return f":material/{ICONES.get(nom, 'circle')}:"


def echapper_html(texte: str | None) -> str:
    """
    Echappe les caracteres HTML sensibles (<, >, &, guillemets) d'une
    chaine avant toute insertion dans un bloc rendu avec
    unsafe_allow_html=True.

    A appeler systematiquement sur toute donnee fournie ou modifiable
    par un utilisateur (titre de document, description, nom, contenu
    de commentaire ou de message...) avant affichage dans une carte
    HTML personnalisee. Sans cet echappement, un titre de document
    contenant une balise <script> ou un attribut HTML malveillant
    s'executerait dans le navigateur de tout administrateur consultant
    le tableau de bord : c'est une injection de script (XSS stocke).
    """
    if texte is None:
        return ""
    return _html_stdlib.escape(str(texte), quote=True)


def adresse_ip_client() -> str:
    """
    Retourne l'adresse IP du client si elle est exposee par
    l'environnement d'execution, sinon une valeur par defaut.
    Streamlit ne donne pas un acces direct et fiable a l'IP du
    navigateur ; en environnement de production, cette information
    doit etre recuperee depuis le serveur web ou le reverse proxy
    place devant l'application (en-tete X-Forwarded-For).
    """
    try:
        ctx = st.context
        headers = getattr(ctx, "headers", {}) or {}
        return headers.get("X-Forwarded-For", "non_disponible")
    except Exception:
        return "non_disponible"


def journaliser(action: str, resultat: str, user_id: int | None = None,
                 matricule: str | None = None, details: str | None = None) -> None:
    """
    Enregistre une ligne dans le journal systeme (table logs).
    A appeler pour toute action sensible : connexion, ajout, suppression,
    modification, validation de document, paiement, changement de
    parametre.
    """
    executer(
        """
        INSERT INTO logs (date_heure, user_id, matricule, action, adresse_ip, resultat, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            matricule,
            action,
            adresse_ip_client(),
            resultat,
            details,
        ),
    )


def fichier_est_pdf_valide(fichier_televerse, taille_max_mo: int = TAILLE_MAX_PDF_MO_DEFAUT) -> tuple[bool, str]:
    """
    Verifie qu'un fichier televerse est reellement un PDF et respecte
    la taille maximale autorisee. Retourne (valide, message_erreur).

    Trois controles, du plus simple au plus fiable :
    1. extension ".pdf" (filtre uniquement le cas innocent) ;
    2. taille en megaoctets ;
    3. signature binaire reelle du fichier (les 5 premiers octets
       doivent etre "%PDF-"). Ce dernier controle est celui qui
       empeche un fichier executable simplement renomme en ".pdf"
       d'etre accepte : un renommage d'extension ne change pas le
       contenu binaire du fichier.

    Cette fonction doit etre appelee par archive_manager.ajouter_document
    avant tout appel a enregistrer_pdf.
    """
    if fichier_televerse is None:
        return False, "Aucun fichier fourni."
    if not fichier_televerse.name.lower().endswith(".pdf"):
        return False, "Seuls les fichiers au format PDF sont acceptes."

    taille_mo = fichier_televerse.size / (1024 * 1024)
    if taille_mo > taille_max_mo:
        return False, f"Le fichier depasse la taille maximale autorisee ({taille_max_mo} Mo)."

    entete = fichier_televerse.getvalue()[:5]
    fichier_televerse.seek(0)
    if not entete.startswith(b"%PDF-"):
        return False, "Le contenu du fichier ne correspond pas a un PDF valide."

    return True, ""


def enregistrer_pdf(fichier_televerse) -> tuple[str, int]:
    """
    Enregistre un fichier PDF televerse sur le disque, sous un nom
    unique afin d'eviter toute collision ou ecrasement accidentel.
    Retourne le chemin relatif du fichier et sa taille en kilo-octets.

    A n'appeler qu'apres validation par fichier_est_pdf_valide : cette
    fonction ne revalide rien, elle se contente d'ecrire le fichier.
    """
    nom_unique = f"{uuid.uuid4().hex}.pdf"
    chemin_complet = Path(DOCUMENTS_DIR) / nom_unique
    with open(chemin_complet, "wb") as f:
        f.write(fichier_televerse.getbuffer())
    taille_ko = chemin_complet.stat().st_size // 1024
    return str(chemin_complet), taille_ko


def supprimer_fichier(chemin_fichier: str) -> None:
    """Supprime un fichier du disque si celui-ci existe (PDF ou photo)."""
    chemin = Path(chemin_fichier)
    if chemin.exists():
        chemin.unlink()


def fichier_est_photo_valide(fichier_televerse) -> tuple[bool, str]:
    """
    Verifie qu'un fichier televerse comme photo de profil est une
    image JPEG ou PNG valide (extension, taille, puis signature
    binaire reelle), selon le meme principe que fichier_est_pdf_valide.
    """
    if fichier_televerse is None:
        return False, "Aucun fichier fourni."
    nom = fichier_televerse.name.lower()
    if not nom.endswith(EXTENSIONS_PHOTO_VALIDES):
        return False, "Formats acceptes : JPG, JPEG ou PNG."

    taille_mo = fichier_televerse.size / (1024 * 1024)
    if taille_mo > TAILLE_MAX_PHOTO_MO:
        return False, f"La photo depasse la taille maximale autorisee ({TAILLE_MAX_PHOTO_MO} Mo)."

    entete = fichier_televerse.getvalue()[:8]
    fichier_televerse.seek(0)
    est_jpeg = entete.startswith(b"\xff\xd8\xff")
    est_png = entete.startswith(b"\x89PNG\r\n\x1a\n")
    if not (est_jpeg or est_png):
        return False, "Le contenu du fichier ne correspond pas a une image valide."

    return True, ""


def enregistrer_photo(fichier_televerse) -> str:
    """
    Enregistre une photo de profil sur le disque sous un nom unique.
    A n'appeler qu'apres validation par fichier_est_photo_valide.
    """
    extension = Path(fichier_televerse.name).suffix.lower()
    nom_unique = f"{uuid.uuid4().hex}{extension}"
    chemin_complet = Path(PHOTOS_DIR) / nom_unique
    with open(chemin_complet, "wb") as f:
        f.write(fichier_televerse.getbuffer())
    return str(chemin_complet)


def formater_date(valeur_iso: str | None, avec_heure: bool = True) -> str:
    """Convertit une date ISO stockee en base vers un format lisible."""
    if not valeur_iso:
        return "Jamais"
    try:
        dt = datetime.strptime(valeur_iso, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return valeur_iso
    return dt.strftime("%d/%m/%Y %H:%M") if avec_heure else dt.strftime("%d/%m/%Y")


def charger_css(chemin_fichier: str) -> None:
    """Injecte une feuille de style CSS externe dans la page Streamlit."""
    with open(chemin_fichier, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
