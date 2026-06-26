"""
app.py
------
Role : point d'entree unique de l'application Streamlit.

Responsabilites :
- configuration de la page et chargement de la feuille de style
  (claire, et sombre en complement selon la preference utilisateur) ;
- initialisation de la base de donnees au premier lancement ;
- creation guidee du premier compte administrateur si la base est vide ;
- affichage de l'ecran de connexion (logo et titre institutionnel
  centres, formulaire de connexion inchange) ;
- verification de l'expiration de session a chaque chargement de page ;
- routage vers les pages selon le role de l'utilisateur connecte ;
- pages communes : bibliotheque, depot de document, favoris, mes
  paiements, messagerie, annonces, notifications, parametres
  personnels.

Les pages reservees a l'administration sont deleguees a admin.py.

Nouveau en V2 (voir audit et cahier des charges) :
- sidebar compacte avec logo, dans l'esprit des tableaux de bord
  administratifs modernes ;
- renommage "Bibliotheque numerique" -> "Bibliotheque" ;
- circuit complet de monetisation (acces gratuit/payant, demande et
  suivi de paiement en presentiel) ;
- espace communautaire (messagerie, annonces, notifications,
  commentaires) ;
- page Parametres personnelle (profil, photo, preferences, securite,
  deconnexion), distincte de la Configuration systeme reservee a
  l'administration ;
- garde de session (auth.verifier_session_active), absente en V1.
"""

import streamlit as st

from database import initialiser_base, recuperer_un
import settings as parametres_systeme
import archive_manager
import payments
import communication
import users as gestion_utilisateurs
import admin
import auth
from models import (
    LIBELLES_ROLE, LIBELLES_TYPE_DOCUMENT, TYPES_DOCUMENT,
    CYCLES_VALIDES, filieres_disponibles_pour_cycle, niveaux_disponibles_pour_cycle,
    TYPES_ACCES, LIBELLES_TYPE_ACCES, PRIX_DOCUMENT_PAYANT_DEFAUT, MESSAGE_DOCUMENT_PAYANT,
    THEMES_VALIDES, LIBELLES_THEME, LANGUES_VALIDES, LIBELLES_LANGUE,
)
from utils import charger_css, icone, formater_date, adresse_ip_client, fichier_est_photo_valide, enregistrer_photo

st.set_page_config(
    page_title="SOURCE ISABEE",
    page_icon=":material/school:",
    layout="wide",
)

CHEMIN_LOGO = "assets/logo.png"


def _initialiser_application() -> None:
    initialiser_base()
    parametres_systeme.initialiser_parametres_par_defaut()
    try:
        charger_css("assets/style.css")
    except FileNotFoundError:
        pass


def _aucun_compte_existant() -> bool:
    return recuperer_un("SELECT id FROM users LIMIT 1") is None


def _afficher_en_tete_publique() -> None:
    """
    En-tete affichee uniquement sur les ecrans pre-authentification
    (configuration initiale et connexion) : logo et titre
    institutionnel centres. N'affecte aucun autre element de la page
    de connexion (le formulaire reste celui defini par
    page_connexion).
    """
    _, colonne_centre, _ = st.columns([1, 2, 1])
    with colonne_centre:
        try:
            st.image(CHEMIN_LOGO, width=96)
        except Exception:
            pass
        st.markdown(
            """
            <div class="en-tete-connexion">
                <h1>SOURCE ISABEE</h1>
                <p>Plateforme de gestion des ressources pédagogiques</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _afficher_barre_superieure() -> None:
    """Barre superieure discrete, affichee une fois connecte : logo en haut a gauche."""
    colonne_logo, colonne_titre = st.columns([1, 8])
    with colonne_logo:
        try:
            st.image(CHEMIN_LOGO, width=40)
        except Exception:
            pass
    with colonne_titre:
        st.markdown('<div class="barre-superieure-titre">SOURCE ISABEE</div>', unsafe_allow_html=True)
    st.divider()


def page_initialisation() -> None:
    """Affichee une seule fois : creation du premier compte administrateur."""
    st.subheader("Configuration initiale")
    st.write(
        "Aucun compte n'existe encore sur cette installation. "
        "Creez le premier compte administrateur pour commencer."
    )
    with st.form("formulaire_initialisation"):
        colonne_gauche, colonne_droite = st.columns(2)
        with colonne_gauche:
            matricule = st.text_input("Matricule")
            nom = st.text_input("Nom")
            email = st.text_input("Adresse e-mail")
        with colonne_droite:
            prenom = st.text_input("Prenom")
            mot_de_passe = st.text_input("Mot de passe", type="password")
            confirmation = st.text_input("Confirmer le mot de passe", type="password")

        valide = st.form_submit_button("Creer le compte administrateur")
        if valide:
            if mot_de_passe != confirmation:
                st.error("Les mots de passe ne correspondent pas.")
            elif not all([matricule, nom, prenom, email, mot_de_passe]):
                st.error("Tous les champs sont obligatoires.")
            else:
                succes, message = gestion_utilisateurs.creer_utilisateur(
                    matricule=matricule, nom=nom, prenom=prenom, email=email,
                    filiere="-", niveau="-", role="administrateur",
                    mot_de_passe=mot_de_passe,
                )
                if succes:
                    st.success("Compte administrateur cree. Vous pouvez vous connecter.")
                else:
                    st.error(message)


def page_connexion() -> None:
    st.subheader("Connexion")
    with st.form("formulaire_connexion"):
        matricule = st.text_input("Matricule")
        mot_de_passe = st.text_input("Mot de passe", type="password")
        valide = st.form_submit_button("Se connecter")
        if valide:
            succes, message = auth.authentifier(matricule.strip(), mot_de_passe)
            if succes:
                st.rerun()
            else:
                st.error(message)


# =====================================================================
# Bibliotheque (anciennement "Bibliotheque numerique")
# =====================================================================

def page_bibliotheque() -> None:
    st.subheader("Bibliotheque")
    utilisateur = auth.utilisateur_courant()

    with st.expander("Filtres de recherche", expanded=True, icon=icone("Search")):
        colonne_1, colonne_2, colonne_3 = st.columns(3)
        with colonne_1:
            cycle = st.selectbox("Cycle", ["Tous"] + list(CYCLES_VALIDES), key="bib_cycle")
        with colonne_2:
            filieres_possibles = filieres_disponibles_pour_cycle(cycle) if cycle != "Tous" else ()
            if filieres_possibles:
                filiere = st.selectbox("Filiere", ["Toutes"] + list(filieres_possibles), key="bib_filiere")
                filiere = "" if filiere == "Toutes" else filiere
            else:
                filiere = st.text_input("Filiere (mot-cle)", key="bib_filiere_libre")
        with colonne_3:
            niveaux_possibles = niveaux_disponibles_pour_cycle(cycle) if cycle != "Tous" else ()
            if niveaux_possibles:
                niveau = st.selectbox("Niveau", ["Tous"] + list(niveaux_possibles), key="bib_niveau")
                niveau = "" if niveau == "Tous" else niveau
            else:
                niveau = ""

        colonne_4, colonne_5 = st.columns(2)
        with colonne_4:
            type_document = st.selectbox(
                "Type", ["Tous"] + list(TYPES_DOCUMENT), key="bib_type",
                format_func=lambda v: "Tous" if v == "Tous" else LIBELLES_TYPE_DOCUMENT.get(v, v),
            )
        with colonne_5:
            annee = st.text_input("Annee academique", placeholder="ex. 2025-2026", key="bib_annee")
        terme = st.text_input("Mots-cles", placeholder="Titre ou description du document", key="bib_terme")

    cycle_filtre = "" if cycle == "Tous" else cycle
    type_document_filtre = "" if type_document == "Tous" else type_document

    page_courante = st.session_state.get("bib_page", 0)
    taille_page = 10
    total = archive_manager.compter_documents(
        terme=terme, cycle=cycle_filtre, filiere=filiere, niveau=niveau,
        annee=annee, type_document=type_document_filtre,
    )
    resultats = archive_manager.rechercher_documents(
        terme=terme, cycle=cycle_filtre, filiere=filiere, niveau=niveau,
        annee=annee, type_document=type_document_filtre,
        limite=taille_page, decalage=page_courante * taille_page,
    )

    st.caption(f"{total} document(s) trouve(s)")

    for document in resultats:
        with st.container(border=True):
            colonne_info, colonne_action = st.columns([4, 1])
            with colonne_info:
                st.markdown(f"**{document.titre}**")
                badge_acces = f"Payant - {document.prix} FCFA" if document.est_payant else "Gratuit"
                st.caption(
                    f"{document.libelle_type} - {document.cycle} - {document.filiere} - "
                    f"{document.niveau} - {document.annee_academique} - {badge_acces}"
                )
                if document.description:
                    st.write(document.description)

            with colonne_action:
                acces_autorise = True
                if document.est_payant:
                    statut_paie = payments.statut_paiement_utilisateur(document.id, utilisateur.id)
                    if statut_paie == "valide":
                        acces_autorise = True
                    elif statut_paie == "en_attente":
                        acces_autorise = False
                        st.info("Paiement en attente de validation.")
                    else:
                        acces_autorise = False
                        st.warning(MESSAGE_DOCUMENT_PAYANT.format(prix=document.prix))
                        if st.button("Demander le paiement", key=f"payer_{document.id}"):
                            succes, message = payments.demander_paiement(document.id, utilisateur.id)
                            (st.success if succes else st.error)(message)
                            st.rerun()

                if acces_autorise:
                    with open(document.chemin_fichier, "rb") as fichier:
                        if st.download_button(
                            "Telecharger", data=fichier, file_name=f"{document.titre}.pdf",
                            mime="application/pdf", key=f"telecharger_{document.id}",
                            icon=icone("Download"),
                        ):
                            archive_manager.enregistrer_telechargement(
                                document.id, utilisateur.id, adresse_ip_client()
                            )
                if st.button("Favori", key=f"favori_{document.id}"):
                    archive_manager.basculer_favori(document.id, utilisateur.id)
                    st.rerun()

            with st.expander("Commentaires et avis"):
                commentaires = communication.commentaires_document(document.id)
                if not commentaires:
                    st.caption("Aucun commentaire pour le moment.")
                for c in commentaires:
                    st.markdown(f"**{c['prenom_auteur']} {c['nom_auteur']}** : {c['contenu']}")
                nouveau_commentaire = st.text_area(
                    "Ajouter un commentaire", key=f"commentaire_{document.id}",
                    label_visibility="collapsed", placeholder="Votre commentaire ou avis...",
                )
                if st.button("Publier", key=f"publier_commentaire_{document.id}"):
                    succes, message = communication.ajouter_commentaire(
                        document.id, utilisateur.id, nouveau_commentaire
                    )
                    (st.success if succes else st.error)(message)
                    if succes:
                        st.rerun()

    colonne_prec, colonne_suiv = st.columns(2)
    with colonne_prec:
        if page_courante > 0 and st.button("Page precedente", key="bib_page_prec"):
            st.session_state["bib_page"] = page_courante - 1
            st.rerun()
    with colonne_suiv:
        if (page_courante + 1) * taille_page < total and st.button("Page suivante", key="bib_page_suiv"):
            st.session_state["bib_page"] = page_courante + 1
            st.rerun()


# =====================================================================
# Depot de documents
# =====================================================================

def page_depot_document() -> None:
    st.subheader("Depot de documents")
    utilisateur = auth.utilisateur_courant()

    cycle = st.selectbox("Cycle", list(CYCLES_VALIDES), key="depot_cycle")
    filieres_possibles = filieres_disponibles_pour_cycle(cycle)
    if filieres_possibles:
        filiere = st.selectbox("Filiere", filieres_possibles, key="depot_filiere")
    else:
        filiere = st.text_input(
            "Filiere (saisie libre - aucune liste officielle de mentions de Master n'est encore definie)",
            key="depot_filiere_libre",
        )
    niveaux_possibles = niveaux_disponibles_pour_cycle(cycle)
    niveau = st.selectbox("Niveau", niveaux_possibles, key="depot_niveau") if niveaux_possibles else "-"
    st.caption(
        "Le cycle, la filiere et le niveau sont choisis ici, en dehors du formulaire ci-dessous, "
        "afin que la liste des filieres se mette a jour immediatement selon le cycle selectionne "
        "(un formulaire Streamlit ne se met a jour qu'a la soumission)."
    )

    with st.form("formulaire_depot", clear_on_submit=True):
        titre = st.text_input("Titre du document")
        description = st.text_area("Description", height=80)
        colonne_1, colonne_2 = st.columns(2)
        with colonne_1:
            annee_academique = st.text_input("Annee academique", placeholder="ex. 2025-2026")
        with colonne_2:
            type_document = st.selectbox(
                "Type de document", list(TYPES_DOCUMENT),
                format_func=lambda v: LIBELLES_TYPE_DOCUMENT.get(v, v),
            )

        colonne_acces, colonne_prix = st.columns(2)
        with colonne_acces:
            type_acces = st.radio(
                "Acces", list(TYPES_ACCES), format_func=lambda v: LIBELLES_TYPE_ACCES.get(v, v), horizontal=True
            )
        with colonne_prix:
            prix_defaut = parametres_systeme.obtenir_parametre_entier(
                "prix_document_payant_defaut", PRIX_DOCUMENT_PAYANT_DEFAUT
            )
            prix = st.number_input(
                "Prix (FCFA)", min_value=0, value=prix_defaut, step=50,
                help="Ignore si l'acces est gratuit.",
            )

        fichier = st.file_uploader("Fichier PDF", type=["pdf"])

        valide = st.form_submit_button("Soumettre pour validation")
        if valide:
            if not all([titre, filiere, annee_academique, fichier]):
                st.error("Veuillez renseigner les champs obligatoires et joindre un fichier PDF.")
            else:
                taille_max = parametres_systeme.obtenir_parametre_entier("taille_max_pdf_mo", 25)
                succes, message = archive_manager.ajouter_document(
                    titre=titre, description=description, type_document=type_document,
                    cycle=cycle, filiere=filiere, niveau=niveau,
                    annee_academique=annee_academique,
                    enseignant_id=utilisateur.id if utilisateur.role == "enseignant" else None,
                    fichier_televerse=fichier, ajoute_par=utilisateur.id,
                    type_acces=type_acces, prix=int(prix), taille_max_pdf_mo=taille_max,
                )
                (st.success if succes else st.error)(message)


# =====================================================================
# Favoris et paiements personnels
# =====================================================================

def page_favoris() -> None:
    st.subheader("Mes favoris")
    utilisateur = auth.utilisateur_courant()
    documents = archive_manager.favoris_utilisateur(utilisateur.id)
    if not documents:
        st.info("Aucun document enregistre dans vos favoris.")
        return
    for document in documents:
        with st.container(border=True):
            st.markdown(f"**{document.titre}**")
            badge_acces = f"Payant - {document.prix} FCFA" if document.est_payant else "Gratuit"
            st.caption(f"{document.libelle_type} - {document.filiere} - {document.niveau} - {badge_acces}")


def page_mes_paiements() -> None:
    st.subheader("Mes paiements")
    utilisateur = auth.utilisateur_courant()
    historique = payments.paiements_utilisateur(utilisateur.id)
    if not historique:
        st.info("Aucune demande de paiement enregistree.")
        return
    for p in historique:
        document = archive_manager.obtenir_document(p.document_id)
        titre_document = document.titre if document else "Document supprime"
        with st.container(border=True):
            st.markdown(f"**{titre_document}**")
            st.caption(
                f"{p.montant} FCFA - {p.libelle_statut} - demande le {formater_date(p.date_demande)}"
            )


# =====================================================================
# Messagerie, annonces, notifications
# =====================================================================

def page_messagerie() -> None:
    st.subheader("Messagerie")
    utilisateur = auth.utilisateur_courant()

    colonne_liste, colonne_conversation = st.columns([1, 2])
    destinataire_id = None

    with colonne_liste:
        st.caption("Nouveau message")
        terme_recherche = st.text_input("Rechercher un destinataire", key="msg_recherche")
        if terme_recherche:
            resultats_recherche = [
                u for u in gestion_utilisateurs.rechercher_utilisateurs(terme_recherche) if u.id != utilisateur.id
            ]
            if resultats_recherche:
                choix = st.selectbox(
                    "Destinataire", resultats_recherche,
                    format_func=lambda u: f"{u.nom_complet} ({u.matricule})", key="msg_destinataire_recherche",
                )
                destinataire_id = choix.id if choix else None
            else:
                st.caption("Aucun utilisateur trouve.")

        st.divider()
        st.caption("Conversations")
        contacts = communication.correspondants(utilisateur.id)
        if not contacts:
            st.caption("Aucune conversation pour le moment.")
        for c in contacts:
            libelle = f"{c['prenom']} {c['nom']}"
            if c["non_lus"]:
                libelle += f" ({c['non_lus']})"
            if st.button(libelle, key=f"contact_{c['id']}", use_container_width=True):
                destinataire_id = c["id"]

    with colonne_conversation:
        if destinataire_id:
            communication.marquer_conversation_lue(utilisateur.id, destinataire_id)
            messages = communication.conversation(utilisateur.id, destinataire_id)
            for m in messages:
                auteur = "Vous" if m.expediteur_id == utilisateur.id else "Correspondant"
                st.markdown(f"**{auteur}** ({formater_date(m.date_envoi)}) : {m.contenu}")
            nouveau_message = st.text_area("Votre message", key="msg_contenu")
            if st.button("Envoyer", icon=icone("Edit"), key="msg_envoyer"):
                succes, message = communication.envoyer_message(utilisateur.id, destinataire_id, nouveau_message)
                (st.success if succes else st.error)(message)
                if succes:
                    st.rerun()
        else:
            st.info("Selectionnez une conversation existante ou recherchez un destinataire.")


def page_annonces() -> None:
    st.subheader("Annonces")
    utilisateur = auth.utilisateur_courant()
    annonces = communication.annonces_pour_role(utilisateur.role)
    if not annonces:
        st.info("Aucune annonce pour le moment.")
        return
    for a in annonces:
        with st.container(border=True):
            st.markdown(f"**{a.titre}**")
            st.caption(formater_date(a.date_publication, avec_heure=False))
            st.write(a.contenu)


def page_notifications() -> None:
    st.subheader("Notifications")
    utilisateur = auth.utilisateur_courant()
    notifs = communication.notifications_utilisateur(utilisateur.id)
    if not notifs:
        st.info("Aucune notification.")
        return
    if st.button("Tout marquer comme lu", icon=icone("Bell")):
        communication.marquer_toutes_notifications_lues(utilisateur.id)
        st.rerun()
    for n in notifs:
        with st.container(border=True):
            etat = "" if n.lu else " - nouveau"
            st.markdown(f"**{n.libelle_type}{etat}**")
            st.caption(formater_date(n.date_creation))
            st.write(n.contenu)
            if not n.lu:
                if st.button("Marquer comme lu", key=f"lu_{n.id}"):
                    communication.marquer_notification_lue(n.id)
                    st.rerun()


# =====================================================================
# Parametres personnels
# =====================================================================

def page_parametres() -> None:
    st.subheader("Parametres")
    utilisateur = auth.utilisateur_courant()

    onglet_profil, onglet_preferences, onglet_securite = st.tabs(["Profil", "Preferences", "Securite"])

    with onglet_profil:
        colonne_photo, colonne_infos = st.columns([1, 3])
        with colonne_photo:
            if utilisateur.photo:
                try:
                    st.image(utilisateur.photo, width=120)
                except Exception:
                    pass
            nouvelle_photo = st.file_uploader("Changer la photo", type=["jpg", "jpeg", "png"], key="upload_photo")
            if nouvelle_photo and st.button("Mettre a jour la photo"):
                photo_valide, erreur = fichier_est_photo_valide(nouvelle_photo)
                if not photo_valide:
                    st.error(erreur)
                else:
                    chemin = enregistrer_photo(nouvelle_photo)
                    gestion_utilisateurs.modifier_photo_profil(utilisateur.id, chemin)
                    st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                    st.success("Photo mise a jour.")
                    st.rerun()
        with colonne_infos:
            st.write(f"**Matricule :** {utilisateur.matricule}")
            st.write(f"**Filiere :** {utilisateur.filiere or '-'}")
            st.write(f"**Niveau :** {utilisateur.niveau or '-'}")
            st.write(f"**Role :** {LIBELLES_ROLE.get(utilisateur.role, utilisateur.role)}")
            st.caption("Le matricule, la filiere, le niveau et le role sont geres par l'administration.")

            nouveau_nom = st.text_input("Nom", value=utilisateur.nom, key="profil_nom")
            nouveau_prenom = st.text_input("Prenom", value=utilisateur.prenom, key="profil_prenom")
            nouvel_email = st.text_input("E-mail", value=utilisateur.email, key="profil_email")
            if st.button("Enregistrer les modifications", key="profil_enregistrer"):
                succes, message = gestion_utilisateurs.modifier_mon_profil(
                    utilisateur.id, nom=nouveau_nom, prenom=nouveau_prenom, email=nouvel_email
                )
                (st.success if succes else st.error)(message)
                if succes:
                    st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                    st.rerun()

    with onglet_preferences:
        theme_choisi = st.radio(
            "Theme", THEMES_VALIDES, index=THEMES_VALIDES.index(utilisateur.theme),
            format_func=lambda t: LIBELLES_THEME.get(t, t), horizontal=True,
        )
        langue_choisie = st.radio(
            "Langue", LANGUES_VALIDES, index=LANGUES_VALIDES.index(utilisateur.langue),
            format_func=lambda l: LIBELLES_LANGUE.get(l, l), horizontal=True,
        )
        if st.button("Enregistrer les preferences"):
            succes, message = gestion_utilisateurs.modifier_preferences(
                utilisateur.id, theme=theme_choisi, langue=langue_choisie
            )
            (st.success if succes else st.error)(message)
            if succes:
                st.session_state["utilisateur_connecte"] = gestion_utilisateurs.obtenir_utilisateur(utilisateur.id)
                st.rerun()

    with onglet_securite:
        ancien_mdp = st.text_input("Mot de passe actuel", type="password", key="ancien_mdp")
        nouveau_mdp = st.text_input(
            "Nouveau mot de passe", type="password", key="nouveau_mdp_perso",
            help="Au moins 8 caracteres, avec au moins une lettre et un chiffre.",
        )
        confirmation_mdp = st.text_input(
            "Confirmer le nouveau mot de passe", type="password", key="confirmation_mdp_perso"
        )
        if st.button("Changer le mot de passe"):
            if nouveau_mdp != confirmation_mdp:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                succes, message = gestion_utilisateurs.changer_mon_mot_de_passe(
                    utilisateur.id, ancien_mdp, nouveau_mdp
                )
                (st.success if succes else st.error)(message)

    st.divider()
    if st.button("Se deconnecter", icon=icone("Trash")):
        auth.deconnecter()
        st.rerun()


def page_configuration_systeme() -> None:
    """Parametres globaux de la plateforme (reserve a l'administration), distincts des Parametres personnels."""
    auth.exiger_role("administrateur")
    st.subheader("Configuration systeme")
    utilisateur = auth.utilisateur_courant()
    for parametre in parametres_systeme.lister_parametres():
        nouvelle_valeur = st.text_input(
            parametre["description"] or parametre["cle"],
            value=parametre["valeur"],
            key=f"parametre_{parametre['cle']}",
        )
        if nouvelle_valeur != parametre["valeur"]:
            parametres_systeme.definir_parametre(parametre["cle"], nouvelle_valeur, utilisateur.id)
            st.rerun()


# =====================================================================
# Navigation et routage
# =====================================================================

def _menu_navigation(utilisateur) -> str:
    with st.sidebar:
        try:
            st.image(CHEMIN_LOGO, width=56)
        except Exception:
            pass
        st.caption("SOURCE ISABEE")
        st.markdown(f"**{utilisateur.nom_complet}**")
        st.caption(LIBELLES_ROLE.get(utilisateur.role, utilisateur.role))

        page_active = st.session_state.get("page_active", "Bibliotheque")

        def _bouton(libelle: str, nom_icone: str) -> None:
            actif = page_active == libelle
            if st.button(
                libelle, key=f"nav_{libelle}", icon=icone(nom_icone),
                use_container_width=True, type="primary" if actif else "secondary",
            ):
                st.session_state["page_active"] = libelle
                st.rerun()

        st.divider()
        st.caption("Espace")
        _bouton("Bibliotheque", "FileText")
        if auth.a_le_role("etudiant", "enseignant", "contributeur"):
            _bouton("Mes favoris", "Home")
            _bouton("Mes paiements", "FileText")
        _bouton("Messagerie", "Users")
        _bouton("Annonces", "Bell")
        non_lus = communication.nombre_notifications_non_lues(utilisateur.id)
        if non_lus:
            st.caption(f"{non_lus} notification(s) non lue(s)")
        _bouton("Notifications", "Bell")
        _bouton("Parametres", "Settings")

        if auth.a_le_role("enseignant", "contributeur", "administrateur"):
            st.divider()
            st.caption("Pedagogie")
            _bouton("Deposer un document", "Edit")
            if auth.a_le_role("enseignant", "administrateur"):
                _bouton("Gestion des validations", "Bell")

        if auth.a_le_role("administrateur"):
            st.divider()
            st.caption("Administration")
            _bouton("Tableau de bord", "BarChart")
            _bouton("Gestion des documents", "FileText")
            _bouton("Gestion des comptes", "Users")
            _bouton("Gestion des paiements", "FileText")
            _bouton("Gestion des annonces", "Bell")
            _bouton("Gestion des commentaires", "Edit")
            _bouton("Gestion des notifications", "Bell")
            _bouton("Configuration systeme", "Settings")
            _bouton("Journal systeme", "FileText")

        st.divider()
        if st.button("Se deconnecter", icon=icone("Trash"), use_container_width=True):
            auth.deconnecter()
            st.rerun()

    return st.session_state.get("page_active", "Bibliotheque")


def main() -> None:
    _initialiser_application()

    if _aucun_compte_existant():
        _afficher_en_tete_publique()
        page_initialisation()
        return

    if not auth.est_connecte():
        _afficher_en_tete_publique()
        page_connexion()
        return

    duree_session = parametres_systeme.obtenir_parametre_entier(
        "expiration_session_minutes", auth.DUREE_MAX_INACTIVITE_MINUTES
    )
    auth.verifier_session_active(duree_max_minutes=duree_session)

    utilisateur = auth.utilisateur_courant()
    if utilisateur is None:
        # La session a expire pendant verifier_session_active, qui a deja
        # arrete le rendu de la page (st.stop()). Branche defensive
        # uniquement : ne devrait jamais s'executer en pratique.
        return

    if utilisateur.theme == "sombre":
        try:
            charger_css("assets/style-sombre.css")
        except FileNotFoundError:
            pass

    _afficher_barre_superieure()
    page_choisie = _menu_navigation(utilisateur)

    pages = {
        "Bibliotheque": page_bibliotheque,
        "Mes favoris": page_favoris,
        "Mes paiements": page_mes_paiements,
        "Messagerie": page_messagerie,
        "Annonces": page_annonces,
        "Notifications": page_notifications,
        "Parametres": page_parametres,
        "Deposer un document": page_depot_document,
        "Gestion des validations": admin.page_moderation_documents,
        "Tableau de bord": admin.page_tableau_de_bord,
        "Gestion des documents": admin.page_gestion_documents,
        "Gestion des comptes": admin.page_gestion_utilisateurs,
        "Gestion des paiements": admin.page_gestion_paiements,
        "Gestion des annonces": admin.page_gestion_annonces,
        "Gestion des commentaires": admin.page_gestion_commentaires,
        "Gestion des notifications": admin.page_gestion_notifications,
        "Configuration systeme": page_configuration_systeme,
        "Journal systeme": admin.page_journal_systeme,
    }
    page_fonction = pages.get(page_choisie, page_bibliotheque)
    page_fonction()


if __name__ == "__main__":
    main()
