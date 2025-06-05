# JurisFix - Plateforme de Médiation Bancaire

Application Flask pour centraliser les outils d'IA juridique du service de médiation bancaire.

## 🚀 Démarrage rapide

### 1. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 2. Configuration de l'environnement

Créez un fichier `.env` à la racine :

```env
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=sqlite:///jurifix.db
```

### 3. Initialisation de la base de données

#### Option A : Réinitialisation complète (développement)

```bash
# Rendre le script exécutable
chmod +x reset_database.sh

# Exécuter la réinitialisation
./reset_database.sh
```

#### Option B : Migration intelligente (production)

```bash
# Exécuter le script de migration
python migrate_database.py
```

### 4. Lancement de l'application

```bash
python app.py
```

L'application sera accessible sur : http://localhost:5002

## 👤 Comptes de test

| Email | Mot de passe | Rôle |
|-------|-------------|------|
| test@jurisfix.fr | password123 | Collaborateur |
| admin@jurisfix.fr | admin123 | Administrateur |
| marie.dupont@jurisfix.fr | demo123 | Collaborateur |
| jean.martin@jurisfix.fr | demo123 | Collaborateur |

## 🔧 Gestion de la base de données

### Vérifier l'état de la base

```python
from app import app, verify_database_integrity

with app.app_context():
    verify_database_integrity()
```

### Créer une migration Flask-Migrate

```bash
# Première fois uniquement
flask db init

# Créer une nouvelle migration
flask db migrate -m "Description du changement"

# Appliquer les migrations
flask db upgrade
```

### Réinitialiser complètement

```bash
# Supprimer la base et les migrations
rm -f jurifix.db
rm -rf migrations/

# Recréer depuis zéro
python -c "from app import create_tables; create_tables()"
```

## 📁 Structure du projet

```
jurifix/
├── app.py                 # Application principale
├── reset_database.sh      # Script de réinitialisation
├── migrate_database.py    # Script de migration avancé
├── requirements.txt       # Dépendances Python
├── .env                   # Variables d'environnement (à créer)
├── jurifix.db            # Base de données SQLite
├── templates/            # Templates HTML
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   └── index.html
└── static/               # Fichiers statiques
    ├── css/
    └── js/
```

## 🛡️ Sécurité

- Les mots de passe sont hashés avec Werkzeug
- Sessions sécurisées avec Flask-Login
- Protection CSRF activée
- Anonymisation RGPD des données sensibles

## 🔄 Bonnes pratiques pour la synchronisation DB

1. **Toujours** utiliser Flask-Migrate pour les changements de schéma en production
2. **Jamais** modifier directement la base SQLite
3. **Sauvegarder** la base avant toute migration importante
4. **Tester** les migrations sur une copie de la base avant production
5. **Versionner** les fichiers de migration dans Git

## 📝 Commandes utiles

```bash
# Créer un backup de la base
cp jurifix.db jurifix_backup_$(date +%Y%m%d).db

# Inspecter la base SQLite
sqlite3 jurifix.db ".schema"

# Lister les utilisateurs
sqlite3 jurifix.db "SELECT email, name, role FROM user;"

# Réinitialiser un mot de passe (depuis Python)
python -c "
from app import app, db, User
with app.app_context():
    user = User.query.filter_by(email='test@jurisfix.fr').first()
    user.set_password('nouveau_mot_de_passe')
    db.session.commit()
"
```

## 🚧 Évolution V2/V3

### Fonctionnalités prévues

- [ ] Espace client pour les particuliers
- [ ] Interface banque pour les représentants
- [ ] API publique pour intégrations
- [ ] Tableau de bord administrateur
- [ ] Système de templates de documents
- [ ] Historique complet des corrections
- [ ] Export PDF des documents
- [ ] Statistiques avancées

### Points d'extension

Le code contient déjà des points d'extension commentés avec `# FUTURE:` pour faciliter l'ajout de nouvelles fonctionnalités.

## 📞 Support

Pour toute question technique : rsultan@fbf.fr
