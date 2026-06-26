"""
icons.py
--------
Role : fournir un jeu d'icones vectorielles sobres, sans emoji, dans
l'esprit visuel de Lucide (trait fin de 1.8px, coins arrondis, aucun
remplissage), pour la sidebar et la barre superieure personnalisees de
l'application.

Pourquoi ces icones ne sont pas litteralement importees de la
bibliotheque "lucide-react" : Streamlit est un framework Python execute
cote serveur ; il ne peut pas importer une bibliotheque JavaScript/React
telle que lucide-react, et cet environnement ne dispose d'aucun acces
reseau pour recuperer un equivalent via un paquet tiers. Les traces
ci-dessous sont dessinees a la main, dans le meme langage visuel
(SVG, trait constant, sans remplissage, capuchons et jonctions
arrondis), afin de respecter l'esprit de la consigne sans dependance
externe.

Liste couverte (strictement celle du cahier des charges, aucune
icone supplementaire n'est ajoutee) :
Home, FileText, Users, Search, Download, Settings, Bell, Trash, Edit,
BarChart.

Pour les widgets natifs Streamlit qui imposent leur propre systeme
d'icone (st.button, st.download_button, st.expander, st.form_submit_
button), ces emplacements ne peuvent pas recevoir de SVG personnalise :
voir utils.icone(), qui s'appuie sur les Material Symbols integres a
Streamlit pour ces cas precis uniquement.
"""

_GABARIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{taille}" height="{taille}" '
    'viewBox="0 0 24 24" fill="none" stroke="{couleur}" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
    'focusable="false">{contenu}</svg>'
)

_TRACES = {
    "home": (
        '<path d="M3 11.5 12 4l9 7.5"/>'
        '<path d="M5.5 10v9.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V10"/>'
        '<path d="M9.5 20.5V14h5v6.5"/>'
    ),
    "file-text": (
        '<path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/>'
        '<path d="M14 3v4h4"/>'
        '<path d="M9 12.5h6"/>'
        '<path d="M9 16h6"/>'
    ),
    "users": (
        '<circle cx="9" cy="8" r="3.2"/>'
        '<path d="M3.5 19.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/>'
        '<path d="M16 8.2a2.7 2.7 0 1 1 1.3 5.1"/>'
        '<path d="M15.5 14.7c2.5.3 4.5 2.2 4.5 4.8"/>'
    ),
    "search": (
        '<circle cx="10.5" cy="10.5" r="6.5"/>'
        '<path d="M20 20l-4.8-4.8"/>'
    ),
    "download": (
        '<path d="M12 3.5v11"/>'
        '<path d="M7.5 10.5 12 15l4.5-4.5"/>'
        '<path d="M4.5 17.5v2a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1v-2"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 2.5v3"/><path d="M12 18.5v3"/>'
        '<path d="M4.5 6.5l2.3 1.6"/><path d="M17.2 15.9l2.3 1.6"/>'
        '<path d="M19.5 6.5l-2.3 1.6"/><path d="M6.8 15.9l-2.3 1.6"/>'
        '<path d="M2.5 12h3"/><path d="M18.5 12h3"/>'
    ),
    "bell": (
        '<path d="M6 9.5a6 6 0 1 1 12 0c0 3 1 4.5 2 5.5H4c1-1 2-2.5 2-5.5Z"/>'
        '<path d="M10 19a2 2 0 0 0 4 0"/>'
    ),
    "trash": (
        '<path d="M5 7h14"/>'
        '<path d="M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2"/>'
        '<path d="M7 7l1 13a1 1 0 0 0 1 .9h6a1 1 0 0 0 1-.9l1-13"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
    ),
    "edit": (
        '<path d="M14.5 5.5 18.5 9.5"/>'
        '<path d="M4 20l.8-3.8L15.2 5.8a1.5 1.5 0 0 1 2.1 0l1 1a1.5 1.5 0 0 1 0 2.1L7.8 19.3 4 20Z"/>'
    ),
    "bar-chart": (
        '<path d="M5 20V11"/><path d="M12 20V4"/><path d="M19 20v-7"/>'
        '<path d="M3.5 20.5h17"/>'
    ),
}

NOMS_DISPONIBLES = tuple(_TRACES.keys())


def svg(nom: str, taille: int = 20, couleur: str = "currentColor") -> str:
    """
    Retourne le balisage SVG inline d'une icone, destine a etre insere
    dans du HTML via st.markdown(..., unsafe_allow_html=True).

    Retourne une icone de repli (cercle vide) si le nom demande
    n'existe pas, plutot que de lever une exception qui casserait
    l'affichage de toute une page pour une simple faute de frappe sur
    un nom d'icone.
    """
    contenu = _TRACES.get(nom, '<circle cx="12" cy="12" r="9"/>')
    return _GABARIT.format(taille=taille, couleur=couleur, contenu=contenu)
