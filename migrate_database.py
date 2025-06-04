#!/usr/bin/env python3
"""
Script de migration avancé pour JurisFix
Gère l'ajout de colonnes manquantes sans perte de données
"""

import os
import sys
from datetime import datetime
from app import app, db
from flask_migrate import init, migrate, upgrade
from sqlalchemy import inspect, text

def check_database_schema():
    """Vérifie l'état actuel du schéma de base de données"""
    with app.app_context():
        inspector = inspect(db.engine)
        
        print("🔍 Analyse du schéma de base de données...")
        
        # Vérifier si la table user existe
        if 'user' not in inspector.get_table_names():
            print("❌ Table 'user' introuvable - Base de données vide")
            return False
        
        # Vérifier les colonnes de la table user
        columns = inspector.get_columns('user')
        column_names = [col['name'] for col in columns]
        
        print(f"📊 Colonnes actuelles dans 'user': {', '.join(column_names)}")
        
        # Colonnes requises
        required_columns = [
            'id', 'email', 'password_hash', 'name', 'service', 
            'role', 'is_active', 'created_at', 'last_login'
        ]
        
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            print(f"⚠️  Colonnes manquantes: {', '.join(missing_columns)}")
            return missing_columns
        
        print("✅ Schéma de base de données complet")
        return True

def manual_migration(missing_columns):
    """Migration manuelle pour ajouter les colonnes manquantes"""
    with app.app_context():
        print("\n🔧 Migration manuelle en cours...")
        
        # Mapping des colonnes avec leurs types SQL
        column_definitions = {
            'password_hash': 'VARCHAR(200)',
            'name': 'VARCHAR(100)',
            'service': 'VARCHAR(100)',
            'role': "VARCHAR(50) DEFAULT 'collaborateur'",
            'is_active': 'BOOLEAN DEFAULT 1',
            'created_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
            'last_login': 'DATETIME'
        }
        
        try:
            for column in missing_columns:
                if column in column_definitions:
                    sql = f"ALTER TABLE user ADD COLUMN {column} {column_definitions[column]}"
                    print(f"➕ Ajout de la colonne '{column}'...")
                    db.session.execute(text(sql))
            
            db.session.commit()
            print("✅ Migration manuelle réussie!")
            
            # Mise à jour des données existantes si nécessaire
            update_existing_users()
            
        except Exception as e:
            print(f"❌ Erreur lors de la migration: {e}")
            db.session.rollback()
            return False
        
        return True

def update_existing_users():
    """Met à jour les utilisateurs existants avec les valeurs par défaut"""
    from app import User
    
    print("\n📝 Mise à jour des utilisateurs existants...")
    
    users = User.query.all()
    for user in users:
        # Valeurs par défaut pour les champs manquants
        if not hasattr(user, 'password_hash') or not user.password_hash:
            print(f"⚠️  Utilisateur {user.email} sans mot de passe - Définition d'un mot de passe temporaire")
            user.set_password('temp_password_change_me')
        
        if not hasattr(user, 'name') or not user.name:
            user.name = user.email.split('@')[0].title()
        
        if not hasattr(user, 'service') or not user.service:
            user.service = 'Service de médiation'
        
        if not hasattr(user, 'role') or not user.role:
            user.role = 'collaborateur'
        
        if not hasattr(user, 'is_active'):
            user.is_active = True
        
        if not hasattr(user, 'created_at') or not user.created_at:
            user.created_at = datetime.utcnow()
    
    db.session.commit()
    print("✅ Utilisateurs mis à jour")

def init_flask_migrate():
    """Initialise Flask-Migrate pour les futures migrations"""
    print("\n🚀 Initialisation de Flask-Migrate...")
    
    if not os.path.exists('migrations'):
        os.system('flask db init')
        print("✅ Flask-Migrate initialisé")
    else:
        print("ℹ️  Flask-Migrate déjà initialisé")
    
    # Créer une migration initiale
    os.system('flask db migrate -m "Initial migration with complete schema"')
    os.system('flask db upgrade')
    
    print("✅ Migration initiale créée et appliquée")

def main():
    """Fonction principale"""
    print("🔄 JurisFix - Migration de base de données\n")
    
    # Vérifier l'état du schéma
    result = check_database_schema()
    
    if result is False:
        # Base de données vide - créer les tables
        print("\n📦 Création de la base de données depuis zéro...")
        from app import create_tables
        create_tables()
        init_flask_migrate()
        
    elif isinstance(result, list):
        # Colonnes manquantes - migration manuelle
        if manual_migration(result):
            init_flask_migrate()
        else:
            print("\n❌ Migration échouée - Recommandation: réinitialisez la base de données")
            sys.exit(1)
    
    else:
        # Schéma complet
        print("\n✅ Base de données déjà à jour!")
        if not os.path.exists('migrations'):
            init_flask_migrate()
    
    print("\n🎉 Migration terminée avec succès!")
    print("👤 Connectez-vous avec: test@jurisfix.fr / password123")

if __name__ == "__main__":
    main()