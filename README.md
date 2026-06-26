# SOURCE ISABEE — Version 2

Plateforme institutionnelle de gestion des ressources pédagogiques de
l'ISABEE : bibliothèque de documents par filière/cycle/niveau,
monétisation des ressources payantes (paiement en présentiel), espace
communautaire (messagerie, annonces, commentaires, notifications) et
administration complète.

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

Aucun compte n'existe à l'installation : le premier lancement affiche
un écran de configuration initiale pour créer le compte administrateur.

## Arborescence

```
app.py              point d'entree, routage, pages communes
admin.py             pages reservees a l'administration
auth.py              authentification, session, mots de passe
database.py          acces SQLite, migration automatique V1 -> V2
models.py            structures de donnees, filieres/cycles/niveaux ISABEE
schema.sql           schema de la base (cree a neuf)
users.py             gestion des comptes, profil personnel
archive_manager.py   cycle de vie des documents
payments.py          paiements en presentiel
communication.py     messagerie, annonces, notifications, commentaires
statistics.py        indicateurs et series pour le tableau de bord
settings.py          parametres systeme (admin)
utils.py             fonctions transverses (securite, fichiers, dates)
icons.py             icones vectorielles locales (style Lucide)
assets/style.css      theme clair (Menutech)
assets/style-sombre.css theme sombre (complement)
assets/logo.png       logo CBT Technology
```

## Filières ISABEE

Les 16 filières officielles (`models.FILIERES_ISABEE`) s'appliquent
aux cycles Licence et Ingénieur. Le cycle Master (Master I / Master II)
ne suit pas ce découpage : aucune liste officielle de mentions n'a
encore été communiquée, le champ filière reste donc en saisie libre
pour ce cycle. À mettre à jour dans `models.py` dès que cette liste
sera disponible.

## Sécurité — ce qui est couvert et ce qui ne l'est pas

Couvert : mots de passe hachés (SHA-256 salé, étiré), politique de
mot de passe minimale, anti-brute-force persistant côté serveur
(indépendant du navigateur), expiration de session par inactivité,
validation réelle des fichiers PDF par signature binaire (pas
seulement l'extension), échappement HTML systématique des données
utilisateur avant tout rendu HTML personnalisé, journal système.

Non couvert, à la charge d'un déploiement de production : HTTPS (à
gérer par le reverse proxy), sauvegarde et restauration de la base
SQLite, supervision/alerting, et migration vers un algorithme de
hachage dédié aux mots de passe (Argon2id ou bcrypt) si la plateforme
est un jour exposée directement sur Internet sans contrôle d'accès
réseau en amont.

## Limites connues de cette V2

- Pas de tests automatisés ni de CI/CD.
- Pas de système de migration de schéma versionné (la migration V1 -> V2
  est gérée à la main dans `database._migrer_schema_v1_vers_v2`,
  fonctionne mais devra être étendue manuellement pour toute V3).
- Les icônes ne sont pas littéralement importées de `lucide-react`
  (incompatible avec un backend Python) : `icons.py` fournit un jeu
  de SVG locaux dans le même esprit visuel.
- Le thème sombre et la langue sont stockés et appliqués (CSS, pour
  le thème), mais la traduction complète de tous les libellés de
  l'interface n'est pas encore réalisée.
- Master n'a pas de liste de filières officielle (voir plus haut).

## Compte de test

Aucun compte de démonstration n'est pré-rempli. Créez le premier
compte administrateur via l'écran de configuration initiale, puis
utilisez Gestion des comptes pour créer les comptes enseignants,
étudiants et contributeurs.
