#!/bin/bash

# Script de réinitialisation de la base de données JurisFix

echo "🔄 Réinitialisation de la base de données JurisFix..."

# 1. Sauvegarde de l'ancienne base (au cas où)
if [ -f "jurifix.db" ]; then
    timestamp=$(date +%Y%m%d_%H%M%S)
    echo "📦 Sauvegarde de l'ancienne base : jurifix_backup_$timestamp.db"
    cp jurifix.db "jurifix_backup_$timestamp.db"
    
    # 2. Suppression de l'ancienne base
    echo "🗑️  Suppression de l'ancienne base..."
    rm jurifix.db
fi

# 3. Suppression du dossier migrations si existant
if [ -d "migrations" ]; then
    echo "🗑️  Suppression du dossier migrations..."
    rm -rf migrations
fi

# 4. Création de la nouvelle base via Python
echo "✨ Création de la nouvelle base de données..."
python3 -c "
from app import app, db, create_tables
with app.app_context():
    create_tables()
    print('✅ Base de données créée avec succès!')
"

echo "🎉 Réinitialisation terminée!"
echo "👤 Utilisateur de test : test@jurisfix.fr / password123"
echo "🚀 Lancez l'application avec : python app.py"