"""
communication.py
-----------------
Role : regrouper l'ensemble de l'espace communautaire de la
plateforme :
- messagerie interne privee entre deux utilisateurs ;
- annonces administratives (informations publiques, diffusees a tous
  ou a un role precis) ;
- notifications individuelles (validation de document, paiement
  valide, nouvelle annonce...) ;
- commentaires et avis publics sur un document, soumis a moderation
  si le parametre systeme moderation_commentaires est active.

Ce module ne realise aucun affichage : il est consomme par app.py.
"""

from database import executer, recuperer_un, recuperer_tous
from models import Message, Annonce, Notification
from settings import obtenir_parametre
from utils import journaliser

# ---------------------------------------------------------------------
# Messagerie interne
# ---------------------------------------------------------------------

def envoyer_message(expediteur_id: int, destinataire_id: int, contenu: str) -> tuple[bool, str]:
    if not contenu or not contenu.strip():
        return False, "Le message ne peut pas etre vide."
    if expediteur_id == destinataire_id:
        return False, "Vous ne pouvez pas vous envoyer un message a vous-meme."
    executer(
        "INSERT INTO messages (expediteur_id, destinataire_id, contenu) VALUES (?, ?, ?)",
        (expediteur_id, destinataire_id, contenu.strip()),
    )
    journaliser("Envoi message", "succes", user_id=expediteur_id, details=f"vers {destinataire_id}")
    return True, "Message envoye."


def conversation(user_id_a: int, user_id_b: int, limite: int = 100) -> list[Message]:
    """Messages echanges entre deux utilisateurs, ordre chronologique croissant."""
    lignes = recuperer_tous(
        """
        SELECT * FROM messages
        WHERE (expediteur_id = ? AND destinataire_id = ?)
           OR (expediteur_id = ? AND destinataire_id = ?)
        ORDER BY date_envoi DESC
        LIMIT ?
        """,
        (user_id_a, user_id_b, user_id_b, user_id_a, limite),
    )
    messages = [Message.depuis_ligne(l) for l in lignes]
    return list(reversed(messages))


def correspondants(user_id: int) -> list[dict]:
    """
    Liste les utilisateurs avec qui user_id a echange au moins un
    message, avec le nombre de messages non lus en provenance de
    chacun, triee par date du dernier message.
    """
    lignes = recuperer_tous(
        """
        SELECT u.id, u.nom, u.prenom, u.matricule,
               MAX(m.date_envoi) AS dernier_message,
               SUM(CASE WHEN m.destinataire_id = :moi AND m.lu = 0 THEN 1 ELSE 0 END) AS non_lus
        FROM messages m
        JOIN users u ON u.id = (CASE WHEN m.expediteur_id = :moi THEN m.destinataire_id ELSE m.expediteur_id END)
        WHERE m.expediteur_id = :moi OR m.destinataire_id = :moi
        GROUP BY u.id
        ORDER BY dernier_message DESC
        """,
        {"moi": user_id},
    )
    return [dict(l) for l in lignes]


def marquer_conversation_lue(destinataire_id: int, expediteur_id: int) -> None:
    executer(
        "UPDATE messages SET lu = 1 WHERE destinataire_id = ? AND expediteur_id = ? AND lu = 0",
        (destinataire_id, expediteur_id),
    )


def nombre_messages_non_lus(user_id: int) -> int:
    ligne = recuperer_un(
        "SELECT COUNT(*) AS total FROM messages WHERE destinataire_id = ? AND lu = 0", (user_id,)
    )
    return ligne["total"] if ligne else 0


# ---------------------------------------------------------------------
# Annonces administratives
# ---------------------------------------------------------------------

def publier_annonce(titre: str, contenu: str, publie_par: int,
                     role_cible: str | None = None, date_expiration: str | None = None) -> tuple[bool, str]:
    if not titre or not contenu:
        return False, "Le titre et le contenu de l'annonce sont obligatoires."
    executer(
        """
        INSERT INTO announcements (titre, contenu, role_cible, publie_par, date_expiration)
        VALUES (?, ?, ?, ?, ?)
        """,
        (titre.strip(), contenu.strip(), role_cible, publie_par, date_expiration),
    )
    journaliser("Publication annonce", "succes", user_id=publie_par, details=titre)
    return True, "Annonce publiee."


def supprimer_annonce(annonce_id: int, supprime_par: int) -> None:
    executer("DELETE FROM announcements WHERE id = ?", (annonce_id,))
    journaliser("Suppression annonce", "succes", user_id=supprime_par, details=str(annonce_id))


def annonces_pour_role(role: str | None, limite: int = 20) -> list[Annonce]:
    """
    Annonces actives et pertinentes pour un role donne : celles sans
    role cible (publiques, visibles de tous) et celles ciblant
    specifiquement ce role, en excluant les annonces expirees.
    """
    lignes = recuperer_tous(
        """
        SELECT * FROM announcements
        WHERE (role_cible IS NULL OR role_cible = ?)
          AND (date_expiration IS NULL OR date_expiration >= datetime('now'))
        ORDER BY date_publication DESC
        LIMIT ?
        """,
        (role, limite),
    )
    return [Annonce.depuis_ligne(l) for l in lignes]


def toutes_les_annonces(limite: int = 100) -> list[Annonce]:
    """Toutes les annonces, y compris expirees, pour la gestion administrateur."""
    lignes = recuperer_tous("SELECT * FROM announcements ORDER BY date_publication DESC LIMIT ?", (limite,))
    return [Annonce.depuis_ligne(l) for l in lignes]


# ---------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------

def creer_notification(user_id: int, contenu: str, type_notification: str = "info",
                        document_id: int | None = None) -> None:
    executer(
        """
        INSERT INTO notifications (user_id, contenu, type_notification, document_id)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, contenu, type_notification, document_id),
    )


def envoyer_notification_a_role(role: str, contenu: str, type_notification: str = "info") -> int:
    """
    Diffuse la meme notification a tous les utilisateurs actifs d'un
    role donne (action administrateur, "gestion des notifications").
    Retourne le nombre de destinataires touches.
    """
    destinataires = recuperer_tous("SELECT id FROM users WHERE role = ? AND statut = 'actif'", (role,))
    for ligne in destinataires:
        creer_notification(ligne["id"], contenu, type_notification)
    return len(destinataires)


def notifications_utilisateur(user_id: int, limite: int = 30) -> list[Notification]:
    lignes = recuperer_tous(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY date_creation DESC LIMIT ?",
        (user_id, limite),
    )
    return [Notification.depuis_ligne(l) for l in lignes]


def nombre_notifications_non_lues(user_id: int) -> int:
    ligne = recuperer_un(
        "SELECT COUNT(*) AS total FROM notifications WHERE user_id = ? AND lu = 0", (user_id,)
    )
    return ligne["total"] if ligne else 0


def marquer_notification_lue(notification_id: int) -> None:
    executer("UPDATE notifications SET lu = 1 WHERE id = ?", (notification_id,))


def marquer_toutes_notifications_lues(user_id: int) -> None:
    executer("UPDATE notifications SET lu = 1 WHERE user_id = ? AND lu = 0", (user_id,))


def notifications_recentes(limite: int = 20) -> list[dict]:
    """Dernieres notifications creees, tous destinataires confondus, pour la supervision admin."""
    lignes = recuperer_tous(
        """
        SELECT n.*, u.nom AS nom_destinataire, u.prenom AS prenom_destinataire
        FROM notifications n
        JOIN users u ON u.id = n.user_id
        ORDER BY n.date_creation DESC
        LIMIT ?
        """,
        (limite,),
    )
    return [dict(l) for l in lignes]


# ---------------------------------------------------------------------
# Commentaires et avis publics
# ---------------------------------------------------------------------

def ajouter_commentaire(document_id: int, user_id: int, contenu: str) -> tuple[bool, str]:
    """
    Ajoute un commentaire sur un document. Si le parametre systeme
    moderation_commentaires est actif (valeur par defaut), le
    commentaire est cree masque et n'apparait qu'apres validation par
    un administrateur ; sinon, il est visible immediatement.
    """
    if not contenu or not contenu.strip():
        return False, "Le commentaire ne peut pas etre vide."

    moderation_active = obtenir_parametre("moderation_commentaires", "oui") == "oui"
    statut_initial = "masque" if moderation_active else "visible"
    executer(
        "INSERT INTO comments (document_id, user_id, contenu, statut) VALUES (?, ?, ?, ?)",
        (document_id, user_id, contenu.strip(), statut_initial),
    )
    journaliser("Ajout commentaire", "succes", user_id=user_id, details=str(document_id))

    if moderation_active:
        return True, "Votre commentaire a ete soumis et sera visible apres moderation."
    return True, "Commentaire publie."


def commentaires_document(document_id: int, uniquement_visibles: bool = True) -> list[dict]:
    """Commentaires d'un document, avec l'identite de leur auteur jointe pour l'affichage."""
    condition_statut = "AND c.statut = 'visible'" if uniquement_visibles else ""
    lignes = recuperer_tous(
        f"""
        SELECT c.*, u.nom AS nom_auteur, u.prenom AS prenom_auteur
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.document_id = ? {condition_statut}
        ORDER BY c.date_creation DESC
        """,
        (document_id,),
    )
    return [dict(l) for l in lignes]


def commentaires_en_attente_moderation() -> list[dict]:
    """Commentaires masques en attente de moderation, avec document et auteur joints."""
    lignes = recuperer_tous(
        """
        SELECT c.*, u.nom AS nom_auteur, u.prenom AS prenom_auteur, s.titre AS titre_document
        FROM comments c
        JOIN users u ON u.id = c.user_id
        JOIN subjects s ON s.id = c.document_id
        WHERE c.statut = 'masque'
        ORDER BY c.date_creation
        """
    )
    return [dict(l) for l in lignes]


def commentaires_recents(limite: int = 10) -> list[dict]:
    """Derniers commentaires visibles, toutes pages confondues, pour le tableau de bord."""
    lignes = recuperer_tous(
        """
        SELECT c.*, u.nom AS nom_auteur, u.prenom AS prenom_auteur, s.titre AS titre_document
        FROM comments c
        JOIN users u ON u.id = c.user_id
        JOIN subjects s ON s.id = c.document_id
        WHERE c.statut = 'visible'
        ORDER BY c.date_creation DESC
        LIMIT ?
        """,
        (limite,),
    )
    return [dict(l) for l in lignes]


def tous_les_commentaires_publies(limite: int = 100) -> list[dict]:
    """Tous les commentaires publies (visibles), pour la gestion administrateur."""
    lignes = recuperer_tous(
        """
        SELECT c.*, u.nom AS nom_auteur, u.prenom AS prenom_auteur, s.titre AS titre_document
        FROM comments c
        JOIN users u ON u.id = c.user_id
        JOIN subjects s ON s.id = c.document_id
        WHERE c.statut = 'visible'
        ORDER BY c.date_creation DESC
        LIMIT ?
        """,
        (limite,),
    )
    return [dict(l) for l in lignes]


def valider_commentaire(commentaire_id: int, valide_par: int) -> None:
    executer("UPDATE comments SET statut = 'visible' WHERE id = ?", (commentaire_id,))
    journaliser("Validation commentaire", "succes", user_id=valide_par, details=str(commentaire_id))


def masquer_commentaire(commentaire_id: int, masque_par: int) -> None:
    executer("UPDATE comments SET statut = 'masque' WHERE id = ?", (commentaire_id,))
    journaliser("Masquage commentaire", "succes", user_id=masque_par, details=str(commentaire_id))


def supprimer_commentaire(commentaire_id: int, supprime_par: int) -> None:
    executer("DELETE FROM comments WHERE id = ?", (commentaire_id,))
    journaliser("Suppression commentaire", "succes", user_id=supprime_par, details=str(commentaire_id))
