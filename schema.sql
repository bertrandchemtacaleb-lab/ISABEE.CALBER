-- =====================================================================
-- SOURCE ISABEE - Schema de base de donnees - VERSION 2
-- SGBD : SQLite 3
--
-- Changements V1 -> V2 :
--   - users        : ajout photo, theme, langue (profil et preferences)
--   - subjects      : ajout type_acces, prix, mode_paiement ; cycle et
--                      filiere desormais contraints par CHECK
--   - payments      : nouvelle table (monetisation, paiement presentiel)
--   - messages      : nouvelle table (messagerie interne)
--   - announcements : nouvelle table (annonces administratives)
--   - notifications : nouvelle table (notifications utilisateur)
--
-- Important : ce fichier definit le schema d'une base CREEE A NEUF.
-- Pour une base V1 deja en production, ces CREATE TABLE IF NOT EXISTS
-- ne modifient pas les tables existantes. La migration d'une base
-- existante est traitee a part dans database.py (fonction
-- migrer_schema_v1_vers_v2), qui ajoute les colonnes manquantes avec
-- ALTER TABLE sans perte de donnees.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Table : users
-- Comptes de la plateforme (administrateur, enseignant, etudiant,
-- contributeur). Le mot de passe n'est jamais stocke en clair.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    matricule           TEXT    NOT NULL UNIQUE,
    nom                 TEXT    NOT NULL,
    prenom              TEXT    NOT NULL,
    email               TEXT    NOT NULL UNIQUE,
    filiere             TEXT,
    niveau              TEXT,
    role                TEXT    NOT NULL CHECK (role IN ('administrateur', 'enseignant', 'etudiant', 'contributeur')),
    mot_de_passe_hash   TEXT    NOT NULL,
    sel                 TEXT    NOT NULL,
    statut              TEXT    NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif', 'suspendu')),
    photo               TEXT,
    theme               TEXT    NOT NULL DEFAULT 'clair' CHECK (theme IN ('clair', 'sombre')),
    langue              TEXT    NOT NULL DEFAULT 'fr' CHECK (langue IN ('fr', 'en')),
    date_inscription    TEXT    NOT NULL DEFAULT (datetime('now')),
    derniere_connexion  TEXT
);

-- ---------------------------------------------------------------------
-- Table : subjects
-- Documents pedagogiques : epreuves, sujets de controle continu,
-- examens, corriges, travaux pratiques et supports de cours.
--
-- type_acces / prix / mode_paiement decrivent la regle d'acces au
-- document (configuree par celui qui le depose). Le suivi du
-- paiement de CHAQUE utilisateur pour CE document est, lui, stocke
-- dans la table payments : un document payant n'a pas un statut de
-- paiement unique, chaque etudiant a le sien.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    titre               TEXT    NOT NULL,
    description         TEXT,
    type_document       TEXT    NOT NULL CHECK (type_document IN ('examen', 'controle_continu', 'corrige', 'travaux_pratiques', 'support_cours', 'autre')),
    cycle               TEXT    NOT NULL CHECK (cycle IN ('Licence', 'Ingenieur', 'Master')),
    filiere             TEXT    NOT NULL,
    niveau              TEXT    NOT NULL,
    annee_academique    TEXT    NOT NULL,
    enseignant_id       INTEGER,
    chemin_fichier      TEXT    NOT NULL,
    taille_fichier_ko   INTEGER,
    type_acces          TEXT    NOT NULL DEFAULT 'gratuit' CHECK (type_acces IN ('gratuit', 'payant')),
    prix                INTEGER NOT NULL DEFAULT 0,
    mode_paiement       TEXT    NOT NULL DEFAULT 'presentiel' CHECK (mode_paiement IN ('presentiel')),
    statut              TEXT    NOT NULL DEFAULT 'en_attente' CHECK (statut IN ('en_attente', 'valide', 'rejete')),
    ajoute_par          INTEGER NOT NULL,
    valide_par          INTEGER,
    date_ajout          TEXT    NOT NULL DEFAULT (datetime('now')),
    date_validation     TEXT,
    motif_rejet         TEXT,
    FOREIGN KEY (enseignant_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (ajoute_par)    REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (valide_par)    REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : downloads
-- Historique des telechargements, utilise pour les statistiques.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS downloads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    date_telechargement TEXT    NOT NULL DEFAULT (datetime('now')),
    adresse_ip          TEXT,
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : favorites
-- Documents marques par un utilisateur pour un acces rapide.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS favorites (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    document_id         INTEGER NOT NULL,
    date_ajout          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, document_id),
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : comments
-- Remarques et avis publics deposes sur un document, soumis a
-- moderation administrative (parametre moderation_commentaires).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    contenu             TEXT    NOT NULL,
    statut              TEXT    NOT NULL DEFAULT 'visible' CHECK (statut IN ('visible', 'masque')),
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : payments
-- Suivi des paiements de ressources payantes. Paiement exclusivement
-- en presentiel : aucune integration Mobile Money. L'administrateur
-- valide manuellement chaque paiement apres encaissement physique.
-- Une ligne par couple (document, utilisateur) : un etudiant ne paie
-- un document donne qu'une seule fois.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    montant             INTEGER NOT NULL,
    mode_paiement       TEXT    NOT NULL DEFAULT 'presentiel' CHECK (mode_paiement IN ('presentiel')),
    statut_paiement     TEXT    NOT NULL DEFAULT 'en_attente' CHECK (statut_paiement IN ('en_attente', 'valide', 'refuse')),
    reference_caisse    TEXT,
    date_demande        TEXT    NOT NULL DEFAULT (datetime('now')),
    date_validation     TEXT,
    valide_par          INTEGER,
    UNIQUE (document_id, user_id),
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (valide_par)  REFERENCES users(id)    ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : messages
-- Messagerie interne privee entre deux utilisateurs de la plateforme.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    expediteur_id       INTEGER NOT NULL,
    destinataire_id     INTEGER NOT NULL,
    contenu             TEXT    NOT NULL,
    lu                  INTEGER NOT NULL DEFAULT 0 CHECK (lu IN (0, 1)),
    date_envoi          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (expediteur_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (destinataire_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- Table : announcements
-- Annonces administratives et informations publiques, diffusees a
-- tous les utilisateurs ou a un role precis.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS announcements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    titre               TEXT    NOT NULL,
    contenu             TEXT    NOT NULL,
    role_cible          TEXT    CHECK (role_cible IS NULL OR role_cible IN ('administrateur', 'enseignant', 'etudiant', 'contributeur')),
    publie_par          INTEGER NOT NULL,
    date_publication    TEXT    NOT NULL DEFAULT (datetime('now')),
    date_expiration     TEXT,
    FOREIGN KEY (publie_par) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : notifications
-- Notifications individuelles (validation de document, paiement
-- valide, nouvelle annonce, nouveau message...).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    contenu             TEXT    NOT NULL,
    type_notification   TEXT    NOT NULL DEFAULT 'info' CHECK (type_notification IN ('info', 'validation', 'paiement', 'annonce', 'message', 'systeme')),
    lu                  INTEGER NOT NULL DEFAULT 0 CHECK (lu IN (0, 1)),
    document_id         INTEGER,
    date_creation       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)     REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES subjects(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : logs
-- Journal systeme : trace toute action sensible (connexion, ajout,
-- suppression, validation, paiement, modification de parametres...).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date_heure          TEXT    NOT NULL DEFAULT (datetime('now')),
    user_id             INTEGER,
    matricule           TEXT,
    action              TEXT    NOT NULL,
    adresse_ip          TEXT,
    resultat            TEXT    NOT NULL CHECK (resultat IN ('succes', 'echec')),
    details             TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Table : settings
-- Parametres globaux de la plateforme, modifiables par un
-- administrateur uniquement.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cle                 TEXT    NOT NULL UNIQUE,
    valeur              TEXT,
    description         TEXT,
    modifie_par         INTEGER,
    date_modification   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (modifie_par) REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Index utiles aux recherches multicriteres et aux statistiques
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_subjects_filiere      ON subjects(filiere);
CREATE INDEX IF NOT EXISTS idx_subjects_cycle         ON subjects(cycle);
CREATE INDEX IF NOT EXISTS idx_subjects_niveau        ON subjects(niveau);
CREATE INDEX IF NOT EXISTS idx_subjects_annee         ON subjects(annee_academique);
CREATE INDEX IF NOT EXISTS idx_subjects_type          ON subjects(type_document);
CREATE INDEX IF NOT EXISTS idx_subjects_statut        ON subjects(statut);
CREATE INDEX IF NOT EXISTS idx_users_role             ON users(role);
CREATE INDEX IF NOT EXISTS idx_logs_date              ON logs(date_heure);
CREATE INDEX IF NOT EXISTS idx_payments_statut        ON payments(statut_paiement);
CREATE INDEX IF NOT EXISTS idx_messages_destinataire  ON messages(destinataire_id, lu);
CREATE INDEX IF NOT EXISTS idx_notifications_user     ON notifications(user_id, lu);
CREATE INDEX IF NOT EXISTS idx_announcements_role     ON announcements(role_cible);
