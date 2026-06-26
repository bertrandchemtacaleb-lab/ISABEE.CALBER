"""
admin.py
--------
Role : rendre les pages reservees a l'administration :
- tableau de bord (indicateurs cles, graphiques Plotly, listes recentes) ;
- gestion des comptes utilisateurs (creation, modification, suspension) ;
- gestion des documents et circuit de validation ;
- gestion des paiements (validation manuelle, presentiel) ;
- gestion des annonces administratives ;
- gestion des commentaires (moderation) ;
- gestion des notifications (diffusion ciblee) ;
- consultation filtrable du journal systeme.

Ce module orchestre les autres modules metier (statistics.py,
users.py, archive_manager.py, payments.py, communication.py,
settings.py) et ne contient lui-meme aucune requete SQL directe.

Correctifs de securite apportes en V2 (voir audit) :
- toute donnee fournie par un utilisateur (titre de document, nom et
  prenom, contenu de commentaire...) est desormais systematiquement
  passee par utils.echapper_html avant insertion dans un bloc
  unsafe_allow_html. En V1, le titre d'un document etait injecte sans
  echappement dans le tableau de bord : un titre contenant une balise
  <script> s'executait dans le navigateur de tout administrateur
  consultant la page (XSS stocke).
"""

import streamlit as st
import plotly.express as px
import pandas as pd

import statistics as stats
import users as gestion_utilisateurs
import archive_manager
import payments
import communication
from database import recuperer_tous
from models import (
    LIBELLES_ROLE, LIBELLES_TYPE_DOCUMENT, LIBELLES_TYPE_ACCES,
    ROLES_VALIDES, CYCLES_VALIDES, filieres_disponibles_pour_cycle,
    niveaux_disponibles_pour_cycle,
)
from utils import formater_date, icone, echapper_html
from auth import exiger_role, utilisateur_courant


# =====================================================================
# Tableau de bord
# =====================================================================

def page_tableau_de_bord() -> None:
    exiger_role("administrateur")
    st.subheader("Tableau de bord")

    indicateurs = stats.indicateurs_generaux()
    donnees_cartes_1 = [
        ("Documents (total)", indicateurs["documents_valides"] + indicateurs["documents_en_attente"]),
        ("Etudiants", indicateurs["etudiants"]),
        ("Enseignants", indicateurs["enseignants"]),
        ("Contributeurs", indicateurs["contributeurs"]),
    ]
    donnees_cartes_2 = [
        ("Telechargements", indicateurs["telechargements"]),
        ("Ressources payantes", payments.nombre_ressources_payantes()),
        ("Paiements valides", payments.nombre_paiements_valides()),
        ("En attente de validation", indicateurs["documents_en_attente"]),
    ]

    for ligne_cartes in (donnees_cartes_1, donnees_cartes_2):
        colonnes = st.columns(4)
        for colonne, (libelle, valeur) in zip(colonnes, ligne_cartes):
            with colonne:
                st.markdown(
                    f"""
                    <div class="carte carte-indicateur">
                        <div class="valeur">{valeur}</div>
                        <div class="libelle">{echapper_html(libelle)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()
    colonne_gauche, colonne_droite = st.columns(2)

    with colonne_gauche:
        st.caption("Telechargements par mois")
        serie = stats.telechargements_par_mois(12)
        if serie:
            df = pd.DataFrame(serie)
            figure = px.line(df, x="mois", y="total", markers=True)
            figure.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300)
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("Aucun telechargement enregistre pour le moment.")

    with colonne_droite:
        st.caption("Repartition des documents par type")
        repartition = stats.documents_par_type()
        if repartition:
            df = pd.DataFrame(repartition)
            df["libelle"] = df["type_document"].map(LIBELLES_TYPE_DOCUMENT)
            figure = px.pie(df, names="libelle", values="total", hole=0.45)
            figure.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300)
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("Aucun document publie pour le moment.")

    colonne_acces, colonne_inscriptions = st.columns(2)
    with colonne_acces:
        st.caption("Repartition gratuit / payant")
        repartition_acces = stats.documents_par_acces()
        if repartition_acces:
            df = pd.DataFrame(repartition_acces)
            df["libelle"] = df["type_acces"].map(LIBELLES_TYPE_ACCES)
            figure = px.pie(df, names="libelle", values="total", hole=0.45)
            figure.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("Aucune donnee disponible.")

    with colonne_inscriptions:
        st.caption("Nouvelles inscriptions par mois")
        serie_inscriptions = stats.nouvelles_inscriptions_par_mois(12)
        if serie_inscriptions:
            df = pd.DataFrame(serie_inscriptions)
            figure = px.bar(df, x="mois", y="total")
            figure.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("Aucune donnee disponible.")

    st.caption("Documents publies par filiere")
    repartition_filiere = stats.documents_par_filiere()
    if repartition_filiere:
        df = pd.DataFrame(repartition_filiere)
        figure = px.bar(df, x="filiere", y="total")
        figure.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320)
        st.plotly_chart(figure, use_container_width=True)

    st.divider()
    colonne_documents, colonne_utilisateurs = st.columns(2)

    with colonne_documents:
        st.caption("Documents recemment ajoutes")
        for document in archive_manager.documents_recents(6):
            st.markdown(
                f"""
                <div class="carte carte-document">
                    <strong>{echapper_html(document.titre)}</strong><br>
                    <span class="texte-secondaire">
                        {echapper_html(document.libelle_type)} - {echapper_html(document.filiere)} -
                        {echapper_html(document.niveau)} - {formater_date(document.date_ajout, avec_heure=False)}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with colonne_utilisateurs:
        st.caption("Dernieres connexions")
        for utilisateur in gestion_utilisateurs.utilisateurs_recemment_connectes(6):
            st.markdown(
                f"""
                <div class="carte carte-document">
                    <strong>{echapper_html(utilisateur.nom_complet)}</strong><br>
                    <span class="texte-secondaire">
                        {echapper_html(LIBELLES_ROLE.get(utilisateur.role, utilisateur.role))} -
                        derniere connexion : {formater_date(utilisateur.derniere_connexion)}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    colonne_commentaires, colonne_annonces = st.columns(2)

    with colonne_commentaires:
        st.caption("Derniers commentaires")
        commentaires = communication.commentaires_recents(5)
        if not commentaires:
            st.info("Aucun commentaire publie pour le moment.")
        for c in commentaires:
            st.markdown(
                f"""
                <div class="carte carte-document">
                    <strong>{echapper_html(c['prenom_auteur'])} {echapper_html(c['nom_auteur'])}</strong>
                    <span class="texte-secondaire"> sur {echapper_html(c['titre_document'])}</span><br>
                    <span class="texte-secondaire">{echapper_html(c['contenu'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with colonne_annonces:
        st.caption("Dernieres annonces")
        annonces = communication.toutes_les_annonces(5)
        if not annonces:
            st.info("Aucune annonce publiee pour le moment.")
        for a in annonces:
            cible = "Tous" if a.est_publique else LIBELLES_ROLE.get(a.role_cible, a.role_cible)
            st.markdown(
                f"""
                <div class="carte carte-document">
                    <strong>{echapper_html(a.titre)}</strong>
                    <span class="texte-secondaire"> - destinataires : {echapper_html(cible)}</span><br>
                    <span class="texte-secondaire">{formater_date(a.date_publication, avec_heure=False)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =====================================================================
# Gestion des documents (CRUD complet, independant de la file de
# validation) et gestion des validations (file d'attente)
# =====================================================================

def page_gestion_documents() -> None:
    exiger_role("administrateur")
    st.subheader("Gestion des documents")

    colonne_recherche, colonne_statut = st.columns([3, 1])
    with colonne_recherche:
        terme = st.text_input("Rechercher un document", placeholder="Titre ou description")
    with colonne_statut:
        statut_filtre = st.selectbox("Statut", ["Tous", "valide", "en_attente", "rejete"])

    page_courante = st.session_state.get("page_gestion_documents", 0)
    taille_page = 10

    tous_resultats = archive_manager.rechercher_documents(terme=terme, uniquement_valides=False, limite=None)
    if statut_filtre != "Tous":
        tous_resultats = [d for d in tous_resultats if d.statut == statut_filtre]

    total = len(tous_resultats)
    documents = tous_resultats[page_courante * taille_page: (page_courante + 1) * taille_page]
    st.caption(f"{total} document(s) au total")

    for document in documents:
        with st.container(border=True):
            colonne_info, colonne_acces, colonne_action = st.columns([3, 1, 1])
            with colonne_info:
                st.markdown(f"**{document.titre}**")
                st.caption(
                    f"{document.libelle_type} - {document.cycle} - {document.filiere} - "
                    f"{document.niveau} - {document.annee_academique} - statut : {document.statut}"
                )
            with colonne_acces:
                if document.est_payant:
                    st.write(f"Payant - {document.prix} FCFA")
                else:
                    st.write("Gratuit")
            with colonne_action:
                if st.button("Supprimer", key=f"suppr_doc_{document.id}", icon=icone("Trash")):
                    archive_manager.supprimer_document(document.id, utilisateur_courant().id)
                    st.rerun()

    colonne_prec, colonne_suiv = st.columns(2)
    with colonne_prec:
        if page_courante > 0 and st.button("Page precedente"):
            st.session_state["page_gestion_documents"] = page_courante - 1
            st.rerun()
    with colonne_suiv:
        if (page_courante + 1) * taille_page < total and st.button("Page suivante"):
            st.session_state["page_gestion_documents"] = page_courante + 1
            st.rerun()


def page_moderation_documents() -> None:
    exiger_role("administrateur", "enseignant")
    st.subheader("Gestion des validations")

    en_attente = archive_manager.documents_en_attente()
    if not en_attente:
        st.info("Aucun document en attente de validation.")
        return

    for document in en_attente:
        with st.container(border=True):
            st.markdown(f"**{document.titre}**")
            badge_acces = f"Payant - {document.prix} FCFA" if document.est_payant else "Gratuit"
            st.caption(
                f"{document.libelle_type} - {document.cycle} - {document.filiere} - "
                f"{document.niveau} - {document.annee_academique} - {badge_acces}"
            )
            if document.description:
                st.write(document.description)

            colonne_validation, colonne_rejet, colonne_motif = st.columns([1, 1, 2])
            with colonne_validation:
                if st.button("Valider", key=f"valider_{document.id}", icon=icone("FileText")):
                    archive_manager.valider_document(document.id, utilisateur_courant().id)
                    st.rerun()
            with colonne_rejet:
                motif = st.session_state.get(f"motif_{document.id}", "")
                if st.button("Rejeter", key=f"rejeter_{document.id}", icon=icone("Trash")):
                    archive_manager.rejeter_document(
                        document.id, utilisateur_courant().id, motif or "Non motive"
                    )
                    st.rerun()
            with colonne_motif:
                st.text_input(
                    "Motif de rejet (optionnel)",
                    key=f"motif_{document.id}",
                    label_visibility="collapsed",
                    placeholder="Motif de rejet (optionnel)",
                )


# =====================================================================
# Gestion des comptes utilisateurs
# =====================================================================

def page_gestion_utilisateurs() -> None:
    exiger_role("administrateur")
    st.subheader("Gestion des comptes")

    with st.expander("Creer un compte", icon=icone("Edit")):
        colonne_1, colonne_2 = st.columns(2)
        with colonne_1:
            cycle_compte = st.selectbox("Cycle", ["-"] + list(CYCLES_VALIDES), key="cycle_creation_compte")
            filieres_possibles = filieres_disponibles_pour_cycle(cycle_compte) if cycle_compte != "-" else ()
            filiere_compte = (
                st.selectbox("Filiere", filieres_possibles, key="filiere_creation_compte") if filieres_possibles
                else st.text_input("Filiere (saisie libre)", key="filiere_creation_compte_libre")
            )
        with colonne_2:
            niveaux_possibles = niveaux_disponibles_pour_cycle(cycle_compte) if cycle_compte != "-" else ()
            niveau_compte = (
                st.selectbox("Niveau", niveaux_possibles, key="niveau_creation_compte") if niveaux_possibles else "-"
            )
        st.caption(
            "Le cycle, la filiere et le niveau sont selectionnes en dehors du formulaire ci-dessous "
            "afin que la liste des filieres se mette a jour immediatement selon le cycle choisi."
        )

        with st.form("formulaire_creation_compte", clear_on_submit=True):
            colonne_1, colonne_2 = st.columns(2)
            with colonne_1:
                matricule = st.text_input("Matricule")
                nom = st.text_input("Nom")
                email = st.text_input("Adresse e-mail")
            with colonne_2:
                prenom = st.text_input("Prenom")
                role = st.selectbox("Role", ROLES_VALIDES, format_func=lambda r: LIBELLES_ROLE.get(r, r))
            mot_de_passe_initial = st.text_input(
                "Mot de passe initial", type="password",
                help="Au moins 8 caracteres, avec au moins une lettre et un chiffre.",
            )

            valide = st.form_submit_button("Creer le compte")
            if valide:
                if not all([matricule, nom, prenom, email, mot_de_passe_initial]):
                    st.error("Tous les champs obligatoires doivent etre renseignes.")
                else:
                    succes, message = gestion_utilisateurs.creer_utilisateur(
                        matricule=matricule, nom=nom, prenom=prenom, email=email,
                        filiere=filiere_compte or "-", niveau=niveau_compte or "-", role=role,
                        mot_de_passe=mot_de_passe_initial, cree_par_id=utilisateur_courant().id,
                    )
                    (st.success if succes else st.error)(message)

    terme = st.text_input("Rechercher un utilisateur", placeholder="Nom, prenom, matricule ou e-mail")
    liste = gestion_utilisateurs.rechercher_utilisateurs(terme) if terme else gestion_utilisateurs.lister_utilisateurs()

    for utilisateur in liste:
        with st.container(border=True):
            colonne_info, colonne_role, colonne_statut, colonne_action = st.columns([3, 2, 1, 2])
            with colonne_info:
                st.markdown(f"**{echapper_html(utilisateur.nom_complet)}**", unsafe_allow_html=True)
                st.caption(f"{utilisateur.matricule} - {utilisateur.email}")
            with colonne_role:
                st.write(LIBELLES_ROLE.get(utilisateur.role, utilisateur.role))
                st.caption(f"{utilisateur.filiere or '-'} - {utilisateur.niveau or '-'}")
            with colonne_statut:
                etiquette = "valide" if utilisateur.statut == "actif" else "rejete"
                st.markdown(
                    f'<span class="etiquette-statut etiquette-{etiquette}">{echapper_html(utilisateur.statut)}</span>',
                    unsafe_allow_html=True,
                )
            with colonne_action:
                sous_colonne_1, sous_colonne_2 = st.columns(2)
                with sous_colonne_1:
                    if utilisateur.statut == "actif":
                        if st.button("Suspendre", key=f"suspendre_{utilisateur.id}"):
                            gestion_utilisateurs.suspendre_utilisateur(utilisateur.id)
                            st.rerun()
                    else:
                        if st.button("Reactiver", key=f"reactiver_{utilisateur.id}"):
                            gestion_utilisateurs.reactiver_utilisateur(utilisateur.id)
                            st.rerun()
                with sous_colonne_2:
                    with st.popover("Reinit. mdp"):
                        nouveau_mdp = st.text_input(
                            "Nouveau mot de passe", type="password", key=f"nouveau_mdp_{utilisateur.id}"
                        )
                        if st.button("Confirmer", key=f"confirmer_mdp_{utilisateur.id}"):
                            succes, message = gestion_utilisateurs.reinitialiser_mot_de_passe(
                                utilisateur.id, nouveau_mdp
                            )
                            (st.success if succes else st.error)(message)


# =====================================================================
# Gestion des paiements
# =====================================================================

def page_gestion_paiements() -> None:
    exiger_role("administrateur")
    st.subheader("Gestion des paiements")
    st.caption("Paiement exclusivement en presentiel. Validez uniquement apres encaissement constate.")

    en_attente = payments.paiements_en_attente_detailles()
    if not en_attente:
        st.info("Aucun paiement en attente de validation.")
    for p in en_attente:
        with st.container(border=True):
            colonne_info, colonne_reference, colonne_action = st.columns([3, 2, 2])
            with colonne_info:
                st.markdown(f"**{echapper_html(p['titre_document'])}**", unsafe_allow_html=True)
                st.caption(
                    f"{p['prenom_utilisateur']} {p['nom_utilisateur']} ({p['matricule_utilisateur']}) - "
                    f"{p['montant']} FCFA - demande le {formater_date(p['date_demande'])}"
                )
            with colonne_reference:
                reference = st.text_input(
                    "Reference de caisse (optionnel)", key=f"reference_{p['id']}",
                    label_visibility="collapsed", placeholder="Reference de caisse (optionnel)",
                )
            with colonne_action:
                sous_colonne_1, sous_colonne_2 = st.columns(2)
                with sous_colonne_1:
                    if st.button("Valider", key=f"valider_paiement_{p['id']}", icon=icone("FileText")):
                        payments.valider_paiement(p["id"], utilisateur_courant().id, reference)
                        communication.creer_notification(
                            p["user_id"],
                            f"Votre paiement pour \"{p['titre_document']}\" a ete valide. "
                            f"Le document est desormais accessible.",
                            "paiement",
                        )
                        st.rerun()
                with sous_colonne_2:
                    if st.button("Refuser", key=f"refuser_paiement_{p['id']}", icon=icone("Trash")):
                        payments.refuser_paiement(p["id"], utilisateur_courant().id)
                        communication.creer_notification(
                            p["user_id"],
                            f"Votre paiement pour \"{p['titre_document']}\" a ete refuse. "
                            f"Veuillez vous presenter au service competent.",
                            "paiement",
                        )
                        st.rerun()

    st.divider()
    st.caption(f"Total des paiements valides a ce jour : {payments.nombre_paiements_valides()}")


# =====================================================================
# Gestion des annonces
# =====================================================================

def page_gestion_annonces() -> None:
    exiger_role("administrateur")
    st.subheader("Gestion des annonces")

    with st.form("formulaire_annonce", clear_on_submit=True):
        titre = st.text_input("Titre de l'annonce")
        contenu = st.text_area("Contenu", height=100)
        colonne_1, colonne_2 = st.columns(2)
        with colonne_1:
            cible = st.selectbox(
                "Destinataires", ["Tous"] + list(ROLES_VALIDES),
                format_func=lambda r: "Tous" if r == "Tous" else LIBELLES_ROLE.get(r, r),
            )
        with colonne_2:
            date_expiration = st.date_input("Date d'expiration (optionnel)", value=None)

        valide = st.form_submit_button("Publier l'annonce")
        if valide:
            if not titre or not contenu:
                st.error("Le titre et le contenu sont obligatoires.")
            else:
                role_cible = None if cible == "Tous" else cible
                date_expiration_str = str(date_expiration) if date_expiration else None
                succes, message = communication.publier_annonce(
                    titre, contenu, utilisateur_courant().id, role_cible, date_expiration_str
                )
                (st.success if succes else st.error)(message)

    st.divider()
    for a in communication.toutes_les_annonces(50):
        with st.container(border=True):
            colonne_info, colonne_action = st.columns([4, 1])
            with colonne_info:
                cible_affichee = "Tous" if a.est_publique else LIBELLES_ROLE.get(a.role_cible, a.role_cible)
                st.markdown(f"**{echapper_html(a.titre)}**", unsafe_allow_html=True)
                st.caption(
                    f"Destinataires : {cible_affichee} - publiee le {formater_date(a.date_publication, avec_heure=False)}"
                )
                st.write(a.contenu)
            with colonne_action:
                if st.button("Supprimer", key=f"suppr_annonce_{a.id}", icon=icone("Trash")):
                    communication.supprimer_annonce(a.id, utilisateur_courant().id)
                    st.rerun()


# =====================================================================
# Gestion des commentaires
# =====================================================================

def page_gestion_commentaires() -> None:
    exiger_role("administrateur")
    st.subheader("Gestion des commentaires")

    onglet_attente, onglet_publies = st.tabs(["En attente de moderation", "Publies"])

    with onglet_attente:
        en_attente = communication.commentaires_en_attente_moderation()
        if not en_attente:
            st.info("Aucun commentaire en attente de moderation.")
        for c in en_attente:
            with st.container(border=True):
                st.markdown(
                    f"**{echapper_html(c['prenom_auteur'])} {echapper_html(c['nom_auteur'])}** "
                    f"sur *{echapper_html(c['titre_document'])}*",
                    unsafe_allow_html=True,
                )
                st.write(c["contenu"])
                colonne_1, colonne_2 = st.columns(2)
                with colonne_1:
                    if st.button("Valider", key=f"valider_com_{c['id']}", icon=icone("FileText")):
                        communication.valider_commentaire(c["id"], utilisateur_courant().id)
                        st.rerun()
                with colonne_2:
                    if st.button("Supprimer", key=f"suppr_com_attente_{c['id']}", icon=icone("Trash")):
                        communication.supprimer_commentaire(c["id"], utilisateur_courant().id)
                        st.rerun()

    with onglet_publies:
        publies = communication.tous_les_commentaires_publies(100)
        if not publies:
            st.info("Aucun commentaire publie.")
        for c in publies:
            with st.container(border=True):
                st.markdown(
                    f"**{echapper_html(c['prenom_auteur'])} {echapper_html(c['nom_auteur'])}** "
                    f"sur *{echapper_html(c['titre_document'])}*",
                    unsafe_allow_html=True,
                )
                st.write(c["contenu"])
                if st.button("Masquer", key=f"masquer_com_{c['id']}", icon=icone("Trash")):
                    communication.masquer_commentaire(c["id"], utilisateur_courant().id)
                    st.rerun()


# =====================================================================
# Gestion des notifications
# =====================================================================

def page_gestion_notifications() -> None:
    exiger_role("administrateur")
    st.subheader("Gestion des notifications")
    st.caption("Diffusez une notification a tous les utilisateurs actifs d'un role donne.")

    with st.form("formulaire_notification", clear_on_submit=True):
        role_cible = st.selectbox("Role destinataire", ROLES_VALIDES, format_func=lambda r: LIBELLES_ROLE.get(r, r))
        contenu = st.text_area("Contenu de la notification", height=80)
        valide = st.form_submit_button("Envoyer")
        if valide:
            if not contenu:
                st.error("Le contenu de la notification est obligatoire.")
            else:
                nombre = communication.envoyer_notification_a_role(role_cible, contenu, "systeme")
                st.success(f"Notification envoyee a {nombre} utilisateur(s).")

    st.divider()
    st.caption("Notifications recentes (toutes destinataires confondus)")
    for n in communication.notifications_recentes(20):
        st.markdown(
            f"""
            <div class="carte carte-document">
                <strong>{echapper_html(n['prenom_destinataire'])} {echapper_html(n['nom_destinataire'])}</strong>
                <span class="texte-secondaire"> - {formater_date(n['date_creation'])}</span><br>
                <span class="texte-secondaire">{echapper_html(n['contenu'])}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =====================================================================
# Journal systeme (filtrable)
# =====================================================================

def page_journal_systeme() -> None:
    exiger_role("administrateur")
    st.subheader("Journal systeme")

    colonne_1, colonne_2, colonne_3 = st.columns(3)
    with colonne_1:
        filtre_utilisateur = st.text_input("Filtrer par matricule")
    with colonne_2:
        filtre_action = st.text_input("Filtrer par action")
    with colonne_3:
        filtre_resultat = st.selectbox("Resultat", ["Tous", "succes", "echec"])

    conditions = []
    parametres: list = []
    if filtre_utilisateur:
        conditions.append("matricule LIKE ?")
        parametres.append(f"%{filtre_utilisateur}%")
    if filtre_action:
        conditions.append("action LIKE ?")
        parametres.append(f"%{filtre_action}%")
    if filtre_resultat != "Tous":
        conditions.append("resultat = ?")
        parametres.append(filtre_resultat)

    clause_where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    lignes = recuperer_tous(
        f"SELECT * FROM logs {clause_where} ORDER BY date_heure DESC LIMIT 500", tuple(parametres)
    )
    if not lignes:
        st.info("Aucune entree ne correspond a ces filtres.")
        return

    df = pd.DataFrame([dict(l) for l in lignes])
    df = df.rename(columns={
        "date_heure": "Date", "matricule": "Utilisateur", "action": "Action",
        "adresse_ip": "Adresse IP", "resultat": "Resultat", "details": "Details",
    })
    colonnes_affichees = ["Date", "Utilisateur", "Action", "Adresse IP", "Resultat", "Details"]
    st.dataframe(df[colonnes_affichees], use_container_width=True, hide_index=True)

    st.download_button(
        "Exporter en CSV", data=df[colonnes_affichees].to_csv(index=False).encode("utf-8"),
        file_name="journal_systeme.csv", mime="text/csv", icon=icone("Download"),
    )
