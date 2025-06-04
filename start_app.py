#!/usr/bin/env python3
"""
Script de démarrage simplifié pour JurisFix Platform
"""

if __name__ == '__main__':
    print("🚀 JurisFix Platform - Service de médiation bancaire")
    print("📍 URL: http://localhost:5002")
    print("👤 Login test: test@jurisfix.fr / password123")
    print()
    
    try:
        from app import app, create_tables
        
        # Initialiser la base de données
        create_tables()
        
        print("✅ Application prête!")
        print("🔗 Ouvrez votre navigateur sur: http://localhost:5002")
        print("⚡ Mode debug activé - Appuyez Ctrl+C pour arrêter")
        print()
        
        # Démarrer l'application
        app.run(debug=True, port=5002, host='127.0.0.1')
        
    except KeyboardInterrupt:
        print("\n👋 Application arrêtée proprement")
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
        import traceback
        traceback.print_exc()