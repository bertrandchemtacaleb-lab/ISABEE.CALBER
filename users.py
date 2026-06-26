"""
users.py
--------
Role : centraliser toutes les operations de gestion des comptes
utilisateurs (creation, modification, suspension, recherche), ainsi
que les operations de profil personnel en self-service (un
utilisateur modifiant ses propres informations, sans privilege
d'administration).

Ce module est utilise par admin.py pour la gestion des comptes, et par
app.py pour la page Parametres personnelle. Il ne contient aucun code
d'affichage Streamlit : il retourne des objets Utilisateur, des
tuples (succes, message) ou des listes, que les modules de
presentation se chargent d'afficher.

Nouveau en V2 :
- mot_de_passe_est_robuste() est desormais applique a toute creation
  ou reinitialisation de mot de passe (aucune contrainte n'existait
  en V1, pas meme une longueur minimale) ;
- modifier_mon_profil(), modifier_preferences(), modifier_photo_profil()
  et changer_mon_mot_de_passe() permettent a un utilisateur de gerer
  lui-meme ses informations personnelles, independamment des champs
  reserves a l'administration (role, statut, filiere, niveau).
"""

from database import executer, recuperer_un, recuperer_tous
from models import Utilisateur, ROLES_VALIDES, THEMES_VALIDES, LANGUES_VALIDES
from auth import generer_sel, hacher_mot_de_passe, mot_de_passe_correct, mot_de_passe_est_robuste
from utils import journaliser, supprimer_fichier


def creer_utilisateur(matricule: str, nom: str, prenom: str, email: str,
                       filiere: str, niveau: str, role: str,
                       mot_de_passe: str, cree_par_id: int | None = None) -> tuple[bool, str]:
    """Cree un nouveau compte utilisateur. Retourne (succes, message)."""
    if role not in ROLES_VALIDES:
        return False, "Role invalide."
    if not Utilisateur.email_valide(email):
        return False, "Adresse e-mail invalide."
    if recuperer_un("SELECT id FROM users WHERE matricule = ?", (matricule,)):
        return False, "Ce matricule est deja utilise."
    if recuperer_un("SELECT id FROM users WHERE email = ?", (email,)):
        return False, "Cette adresse e-mail est deja utilisee."

    robuste, message_mdp = mot_de_passe_est_robuste(mot_de_passe)
    if not robuste:
        return False, message_mdp

    sel = generer_sel()
    hachage = hacher_mot_de_passe(mot_de_passe, sel)
    executer(
        """
        INSERT INTO users (matricule, nom, prenom, email, filiere, niveau, role,
                            mot_de_passe_hash, sel, statut)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'actif')
        """,
        (matricule, nom, prenom, email, filiere, niveau, role, hachage, sel),
    )
    journaliser("Creation utilisateur", "succes", user_id=cree_par_id,
                details=f"Compte cree pour {matricule} ({role}).")
    return True, "Compte cree avec succes."


def modifier_utilisateur(utilisateur_id: int, **champs) -> tuple[bool, str]:
    """
    Met a jour un ou plusieurs champs d'un utilisateur, reserve a
    l'administration (identite, role, statut, cursus). Pour les
    preferences personnelles (theme, langue, photo), voir
    modifier_preferences() et modifier_photo_profil().
    Exemple : modifier_utilisateur(12, filiere="Genie energetique", niveau="Ing 3")
    """
    champs_autorises = {"nom", "prenom", "email", "filiere", "niveau", "role", "statut"}
    a_mettre_a_jour = {k: v for k, v in champs.items() if k in champs_autorises}
    if not a_mettre_a_jour:
        return False, "Aucun champ valide a mettre a jour."

    assignations = ", ".join(f"{champ} = ?" for champ in a_mettre_a_jour)
    valeurs = list(a_mettre_a_jour.values()) + [utilisateur_id]
    executer(f"UPDATE users SET {assignations} WHERE id = ?", tuple(valeurs))
    journaliser("Modification utilisateur", "succes", user_id=utilisateur_id,
                details=str(a_mettre_a_jour))
    return True, "Utilisateur mis a jour."


def reinitialiser_mot_de_passe(utilisateur_id: int, nouveau_mot_de_passe: str) -> tuple[bool, str]:
    """Reinitialise le mot de passe d'un utilisateur (action administrateur)."""
    robuste, message_mdp = mot_de_passe_est_robuste(nouveau_mot_de_passe)
    if not robuste:
        return False, message_mdp
    sel = generer_sel()
    hachage = hacher_mot_de_passe(nouveau_mot_de_passe, sel)
    executer("UPDATE users SET mot_de_passe_hash = ?, sel = ? WHERE id = ?",
              (hachage, sel, utilisateur_id))
    journaliser("Reinitialisation mot de passe", "succes", user_id=utilisateur_id)
    return True, "Mot de passe reinitialise."


def changer_mon_mot_de_passe(utilisateur_id: int, ancien_mot_de_passe: str,
                              nouveau_mot_de_passe: str) -> tuple[bool, str]:
    """
    Permet a un utilisateur de changer lui-meme son mot de passe, a
    condition de fournir l'ancien. Contrairement a
    reinitialiser_mot_de_passe (reserve a l'administration), cette
    fonction est destinee a la page Parametres personnelle.
    """
    ligne = recuperer_un("SELECT * FROM users WHERE id = ?", (utilisateur_id,))
    if ligne is None:
        return False, "Utilisateur introuvable."
    if not mot_de_passe_correct(ancien_mot_de_passe, ligne["sel"], ligne["mot_de_passe_hash"]):
        journaliser("Changement mot de passe", "echec", user_id=utilisateur_id,
                    details="Ancien mot de passe incorrect.")
        return False, "Le mot de passe actuel saisi est incorrect."
    return reinitialiser_mot_de_passe(utilisateur_id, nouveau_mot_de_passe)


def modifier_mon_profil(utilisateur_id: int, nom: str | None = None, prenom: str | None = None,
                         email: str | None = None) -> tuple[bool, str]:
    """
    Permet a un utilisateur de modifier lui-meme son nom, prenom et/ou
    e-mail. Le role, le statut, le matricule et les informations de
    cursus (filiere, niveau) restent reserves a l'administration et ne
    sont pas modifiables par cette fonction.
    """
    champs: dict = {}
    if nom:
        champs["nom"] = nom
    if prenom:
        champs["prenom"] = prenom
    if email:
        if not Utilisateur.email_valide(email):
            return False, "Adresse e-mail invalide."
        existant = recuperer_un("SELECT id FROM users WHERE email = ? AND id != ?", (email, utilisateur_id))
        if existant:
            return False, "Cette adresse e-mail est deja utilisee par un autre compte."
        champs["email"] = email

    if not champs:
        return False, "Aucune information a mettre a jour."

    assignations = ", ".join(f"{c} = ?" for c in champs)
    valeurs = list(champs.values()) + [utilisateur_id]
    executer(f"UPDATE users SET {assignations} WHERE id = ?", tuple(valeurs))
    journaliser("Modification profil", "succes", user_id=utilisateur_id,
                details=str(list(champs.keys())))
    return True, "Profil mis a jour."


def modifier_preferences(utilisateur_id: int, theme: str | None = None,
                          langue: str | None = None) -> tuple[bool, str]:
    """Met a jour les preferences d'affichage personnelles (theme clair/sombre, langue)."""
    if theme is not None and theme not in THEMES_VALIDES:
        return False, "Theme invalide."
    if langue is not None and langue not in LANGUES_VALIDES:
        return False, "Langue invalide."

    champs: dict = {}
    if theme is not None:
        champs["theme"] = theme
    if langue is not None:
        champs["langue"] = langue
    if not champs:
        return False, "Aucune preference a mettre a jour."

    assignations = ", ".join(f"{c} = ?" for c in champs)
    valeurs = list(champs.values()) + [utilisateur_id]
    executer(f"UPDATE users SET {assignations} WHERE id = ?", tuple(valeurs))
    journaliser("Modification preferences", "succes", user_id=utilisateur_id, details=str(champs))
    return True, "Preferences mises a jour."


def modifier_photo_profil(utilisateur_id: int, chemin_photo: str) -> tuple[bool, str]:
    """
    Met a jour la photo de profil et supprime l'ancienne du disque si
    elle existe, afin d'eviter l'accumulation de fichiers orphelins au
    fil des changements de photo.
    """
    ancien = obtenir_utilisateur(utilisateur_id)
    executer("UPDATE users SET photo = ? WHERE id = ?", (chemin_photo, utilisateur_id))
    if ancien and ancien.photo:
        supprimer_fichier(ancien.photo)
    journaliser("Modification photo de profil", "succes", user_id=utilisateur_id)
    return True, "Photo de profil mise a jour."


def suspendre_utilisateur(utilisateur_id: int) -> None:
    executer("UPDATE users SET statut = 'suspendu' WHERE id = ?", (utilisateur_id,))
    journaliser("Suspension de compte", "succes", user_id=utilisateur_id)


def reactiver_utilisateur(utilisateur_id: int) -> None:
    executer("UPDATE users SET statut = 'actif' WHERE id = ?", (utilisateur_id,))
    journaliser("Reactivation de compte", "succes", user_id=utilisateur_id)


def obtenir_utilisateur(utilisateur_id: int) -> Utilisateur | None:
    ligne = recuperer_un("SELECT * FROM users WHERE id = ?", (utilisateur_id,))
    return Utilisateur.depuis_ligne(ligne) if ligne else None


def lister_utilisateurs(role: str | None = None) -> list[Utilisateur]:
    """Liste les utilisateurs, avec filtre optionnel par role."""
    if role:
        lignes = recuperer_tous("SELECT * FROM users WHERE role = ? ORDER BY nom", (role,))
    else:
        lignes = recuperer_tous("SELECT * FROM users ORDER BY nom")
    return [Utilisateur.depuis_ligne(l) for l in lignes]


def rechercher_utilisateurs(terme: str) -> list[Utilisateur]:
    """Recherche par nom, prenom, matricule ou e-mail."""
    motif = f"%{terme}%"
    lignes = recuperer_tous(
        """
        SELECT * FROM users
        WHERE nom LIKE ? OR prenom LIKE ? OR matricule LIKE ? OR email LIKE ?
        ORDER BY nom
        """,
        (motif, motif, motif, motif),
    )
    return [Utilisateur.depuis_ligne(l) for l in lignes]


def utilisateurs_recemment_connectes(limite: int = 10) -> list[Utilisateur]:
    lignes = recuperer_tous(
        """
        SELECT * FROM users
        WHERE derniere_connexion IS NOT NULL
        ORDER BY derniere_connexion DESC
        LIMIT ?
        """,
        (limite,),
    )
    return [Utilisateur.depuis_ligne(l) for l in lignes]
