"""
models.py
---------
Role : definir la structure des donnees manipulees par l'application,
independamment de la base de donnees et de l'interface.

Ces classes ne contiennent aucune logique d'acces aux donnees (ce role
revient a database.py, users.py, archive_manager.py, etc.) et aucune
logique d'affichage (ce role revient a app.py et admin.py). Elles
servent uniquement a representer un enregistrement de maniere typee et
lisible, et a centraliser les regles de validation simples qui leur
sont propres.

Nouveau en V2 : structure des cycles/filieres/niveaux de l'ISABEE,
champs de monetisation des documents, et dataclasses Paiement,
Message, Annonce, Notification.
"""

from dataclasses import dataclass
from datetime import datetime
import re

# ---------------------------------------------------------------------
# Roles et comptes
# ---------------------------------------------------------------------
ROLES_VALIDES = ("administrateur", "enseignant", "etudiant", "contributeur")

LIBELLES_ROLE = {
    "administrateur": "Administrateur",
    "enseignant": "Enseignant",
    "etudiant": "Etudiant",
    "contributeur": "Contributeur",
}

THEMES_VALIDES = ("clair", "sombre")
LIBELLES_THEME = {"clair": "Theme clair", "sombre": "Theme sombre"}

LANGUES_VALIDES = ("fr", "en")
LIBELLES_LANGUE = {"fr": "Francais", "en": "English"}

# ---------------------------------------------------------------------
# Cycles, niveaux et filieres officielles de l'ISABEE
#
# Les 16 filieres ci-dessous sont communes aux deux cursus de premier
# acces : Licence en Sciences de l'Ingenieur et cycle d'Ingenieur.
# Le cycle Master (Master I / Master II) ne suit pas ce decoupage par
# filiere : aucune liste officielle de mentions de Master n'a ete
# fournie a ce jour. En attendant, le champ filiere reste en saisie
# libre pour ce cycle uniquement (voir filieres_disponibles_pour_cycle).
# ---------------------------------------------------------------------
CYCLES_VALIDES = ("Licence", "Ingenieur", "Master")

NIVEAUX_PAR_CYCLE = {
    "Licence": ("Niveau 1", "Niveau 2", "Niveau 3"),
    "Ingenieur": ("Ing 1", "Ing 2", "Ing 3", "Ing 4", "Ing 5"),
    "Master": ("Master I", "Master II"),
}

FILIERES_ISABEE = (
    "Production vegetale",
    "Production animale",
    "Protection des cultures",
    "Operations forestieres",
    "Amenagement forestier",
    "Gestion de la faune, des aires protegees et ecotourisme",
    "Sylviculture et plantations forestieres",
    "Sciences du bois",
    "Techniques specialisees en transformation du bois",
    "Genie de l'environnement",
    "Systemes agro-sylvo-pastoraux et bioenergies",
    "Bioenergies et environnement",
    "Genie energetique",
    "Agroeconomie",
    "Politique et gouvernance forestiere",
    "Etudes d'impact environnemental et social",
)

# Cycles pour lesquels la liste FILIERES_ISABEE s'applique strictement.
CYCLES_AVEC_FILIERES_FIXES = ("Licence", "Ingenieur")


def filieres_disponibles_pour_cycle(cycle: str) -> tuple[str, ...]:
    """
    Retourne la liste des filieres valides pour un cycle donne.
    Pour Licence et Ingenieur : les 16 filieres officielles de l'ISABEE.
    Pour Master : tuple vide (saisie libre tant qu'aucune liste
    officielle de mentions n'a ete communiquee).
    """
    if cycle in CYCLES_AVEC_FILIERES_FIXES:
        return FILIERES_ISABEE
    return ()


def niveaux_disponibles_pour_cycle(cycle: str) -> tuple[str, ...]:
    return NIVEAUX_PAR_CYCLE.get(cycle, ())


# ---------------------------------------------------------------------
# Documents pedagogiques
# ---------------------------------------------------------------------
TYPES_DOCUMENT = ("examen", "controle_continu", "corrige", "travaux_pratiques", "support_cours", "autre")
STATUTS_DOCUMENT = ("en_attente", "valide", "rejete")

LIBELLES_TYPE_DOCUMENT = {
    "examen": "Examen",
    "controle_continu": "Controle continu",
    "corrige": "Corrige",
    "travaux_pratiques": "Travaux pratiques",
    "support_cours": "Support de cours",
    "autre": "Autre",
}

# ---------------------------------------------------------------------
# Monetisation
#
# Paiement exclusivement en presentiel : aucune integration Mobile
# Money. Le prix par defaut (300 FCFA) est une valeur de depart
# modifiable par document ; il n'est pas code en dur dans la logique
# metier afin de permettre une evolution tarifaire future sans
# modification du code.
# ---------------------------------------------------------------------
TYPES_ACCES = ("gratuit", "payant")
LIBELLES_TYPE_ACCES = {"gratuit": "Gratuit", "payant": "Payant"}

PRIX_DOCUMENT_PAYANT_DEFAUT = 300
MODES_PAIEMENT_VALIDES = ("presentiel",)
LIBELLE_MODE_PAIEMENT = {"presentiel": "Paiement en presentiel"}

STATUTS_PAIEMENT = ("en_attente", "valide", "refuse")
LIBELLES_STATUT_PAIEMENT = {
    "en_attente": "En attente de validation",
    "valide": "Paiement valide",
    "refuse": "Paiement refuse",
}

MESSAGE_DOCUMENT_PAYANT = (
    "Document disponible apres paiement en presentiel. "
    "Rendez-vous au service competent pour regler {prix} FCFA, "
    "puis attendez la validation de votre paiement par un administrateur."
)

# ---------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------
TYPES_NOTIFICATION = ("info", "validation", "paiement", "annonce", "message", "systeme")
LIBELLES_TYPE_NOTIFICATION = {
    "info": "Information",
    "validation": "Validation de document",
    "paiement": "Paiement",
    "annonce": "Annonce",
    "message": "Message",
    "systeme": "Systeme",
}


@dataclass
class Utilisateur:
    id: int | None
    matricule: str
    nom: str
    prenom: str
    email: str
    filiere: str
    niveau: str
    role: str
    statut: str = "actif"
    photo: str | None = None
    theme: str = "clair"
    langue: str = "fr"
    date_inscription: str | None = None
    derniere_connexion: str | None = None

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}"

    @staticmethod
    def email_valide(email: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

    @classmethod
    def depuis_ligne(cls, ligne) -> "Utilisateur":
        """Construit un Utilisateur a partir d'une ligne sqlite3.Row."""
        cles = ligne.keys()
        return cls(
            id=ligne["id"],
            matricule=ligne["matricule"],
            nom=ligne["nom"],
            prenom=ligne["prenom"],
            email=ligne["email"],
            filiere=ligne["filiere"],
            niveau=ligne["niveau"],
            role=ligne["role"],
            statut=ligne["statut"],
            photo=ligne["photo"] if "photo" in cles else None,
            theme=ligne["theme"] if "theme" in cles else "clair",
            langue=ligne["langue"] if "langue" in cles else "fr",
            date_inscription=ligne["date_inscription"],
            derniere_connexion=ligne["derniere_connexion"],
        )


@dataclass
class Document:
    id: int | None
    titre: str
    description: str
    type_document: str
    cycle: str
    filiere: str
    niveau: str
    annee_academique: str
    enseignant_id: int | None
    chemin_fichier: str
    taille_fichier_ko: int | None
    type_acces: str = "gratuit"
    prix: int = 0
    mode_paiement: str = "presentiel"
    statut: str = "en_attente"
    ajoute_par: int | None = None
    valide_par: int | None = None
    date_ajout: str | None = None
    date_validation: str | None = None
    motif_rejet: str | None = None

    @property
    def libelle_type(self) -> str:
        return LIBELLES_TYPE_DOCUMENT.get(self.type_document, self.type_document)

    @property
    def est_payant(self) -> bool:
        return self.type_acces == "payant"

    @classmethod
    def depuis_ligne(cls, ligne) -> "Document":
        cles = ligne.keys()
        return cls(
            id=ligne["id"],
            titre=ligne["titre"],
            description=ligne["description"],
            type_document=ligne["type_document"],
            cycle=ligne["cycle"],
            filiere=ligne["filiere"],
            niveau=ligne["niveau"],
            annee_academique=ligne["annee_academique"],
            enseignant_id=ligne["enseignant_id"],
            chemin_fichier=ligne["chemin_fichier"],
            taille_fichier_ko=ligne["taille_fichier_ko"],
            type_acces=ligne["type_acces"] if "type_acces" in cles else "gratuit",
            prix=ligne["prix"] if "prix" in cles else 0,
            mode_paiement=ligne["mode_paiement"] if "mode_paiement" in cles else "presentiel",
            statut=ligne["statut"],
            ajoute_par=ligne["ajoute_par"],
            valide_par=ligne["valide_par"],
            date_ajout=ligne["date_ajout"],
            date_validation=ligne["date_validation"],
            motif_rejet=ligne["motif_rejet"],
        )


@dataclass
class Paiement:
    id: int | None
    document_id: int
    user_id: int
    montant: int
    mode_paiement: str
    statut_paiement: str
    reference_caisse: str | None
    date_demande: str | None
    date_validation: str | None
    valide_par: int | None

    @property
    def libelle_statut(self) -> str:
        return LIBELLES_STATUT_PAIEMENT.get(self.statut_paiement, self.statut_paiement)

    @classmethod
    def depuis_ligne(cls, ligne) -> "Paiement":
        return cls(
            id=ligne["id"],
            document_id=ligne["document_id"],
            user_id=ligne["user_id"],
            montant=ligne["montant"],
            mode_paiement=ligne["mode_paiement"],
            statut_paiement=ligne["statut_paiement"],
            reference_caisse=ligne["reference_caisse"],
            date_demande=ligne["date_demande"],
            date_validation=ligne["date_validation"],
            valide_par=ligne["valide_par"],
        )


@dataclass
class Message:
    id: int | None
    expediteur_id: int
    destinataire_id: int
    contenu: str
    lu: bool
    date_envoi: str | None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Message":
        return cls(
            id=ligne["id"],
            expediteur_id=ligne["expediteur_id"],
            destinataire_id=ligne["destinataire_id"],
            contenu=ligne["contenu"],
            lu=bool(ligne["lu"]),
            date_envoi=ligne["date_envoi"],
        )


@dataclass
class Annonce:
    id: int | None
    titre: str
    contenu: str
    role_cible: str | None
    publie_par: int
    date_publication: str | None
    date_expiration: str | None

    @property
    def est_publique(self) -> bool:
        return self.role_cible is None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Annonce":
        return cls(
            id=ligne["id"],
            titre=ligne["titre"],
            contenu=ligne["contenu"],
            role_cible=ligne["role_cible"],
            publie_par=ligne["publie_par"],
            date_publication=ligne["date_publication"],
            date_expiration=ligne["date_expiration"],
        )


@dataclass
class Notification:
    id: int | None
    user_id: int
    contenu: str
    type_notification: str
    lu: bool
    document_id: int | None
    date_creation: str | None

    @property
    def libelle_type(self) -> str:
        return LIBELLES_TYPE_NOTIFICATION.get(self.type_notification, self.type_notification)

    @classmethod
    def depuis_ligne(cls, ligne) -> "Notification":
        return cls(
            id=ligne["id"],
            user_id=ligne["user_id"],
            contenu=ligne["contenu"],
            type_notification=ligne["type_notification"],
            lu=bool(ligne["lu"]),
            document_id=ligne["document_id"],
            date_creation=ligne["date_creation"],
        )


@dataclass
class Commentaire:
    id: int | None
    document_id: int
    user_id: int
    contenu: str
    statut: str
    date_creation: str | None

    @classmethod
    def depuis_ligne(cls, ligne) -> "Commentaire":
        return cls(
            id=ligne["id"],
            document_id=ligne["document_id"],
            user_id=ligne["user_id"],
            contenu=ligne["contenu"],
            statut=ligne["statut"],
            date_creation=ligne["date_creation"],
        )


@dataclass
class EntreeJournal:
    id: int | None
    date_heure: str
    user_id: int | None
    matricule: str | None
    action: str
    adresse_ip: str | None
    resultat: str
    details: str | None = None
