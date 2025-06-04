from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, timedelta
import os
import re
import uuid
import json
import html
from bs4 import BeautifulSoup

print("🚀 JurisFix Platform - Démarrage...")
load_dotenv()

# 🔧 Configuration Flask et Extensions
app = Flask(__name__, static_folder="static", static_url_path="/static", template_folder="templates")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///jurifix.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Extensions
CORS(app, supports_credentials=True)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'

# OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 📊 Modèles de base de données améliorés
class User(UserMixin, db.Model):
    """Modèle utilisateur avec gestion des rôles pour V2/V3"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    service = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(50), default='collaborateur')  # FUTURE: 'client', 'banque', 'admin'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relations
    documents = db.relationship('Document', backref='author', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()

class Document(db.Model):
    """Modèle document avec gestion des statuts et métadonnées"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    corrected_content = db.Column(db.Text, nullable=True)
    agent_used = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(20), default='draft')  # draft, processing, completed, archived
    
    # Métadonnées
    word_count = db.Column(db.Integer, default=0)
    corrections_count = db.Column(db.Integer, default=0)
    processing_time = db.Column(db.Float, default=0.0)  # en secondes
    
    # FUTURE: Champs pour partage et collaboration
    shared_with = db.Column(db.Text, nullable=True)  # JSON des user_ids
    visibility = db.Column(db.String(20), default='private')  # private, service, public
    
    # Structure HTML préservée
    html_structure = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'agent_used': self.agent_used,
            'status': self.status,
            'created_at': self.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': self.updated_at.strftime('%d/%m/%Y %H:%M'),
            'word_count': self.word_count,
            'corrections_count': self.corrections_count
        }

class CorrectionHistory(db.Model):
    """Historique des corrections pour traçabilité"""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.String(36), db.ForeignKey('document.id'), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    corrected_text = db.Column(db.Text, nullable=False)
    corrections_made = db.Column(db.Text, nullable=True)  # JSON des corrections
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # FUTURE: Ajout de métadonnées pour l'audit
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(200), nullable=True)

# 🔐 Gestion de l'authentification
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def require_role(role):
    """Décorateur pour vérifier les rôles (préparation V2/V3)"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role and current_user.role != 'admin':
                return jsonify({'error': 'Accès non autorisé'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 🌐 Routes d'authentification
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        password = data.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            user.update_last_login()
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'redirect': url_for('dashboard'),
                    'user': {
                        'name': user.name,
                        'email': user.email,
                        'role': user.role
                    }
                })
            return redirect(url_for('dashboard'))
        
        error_msg = 'Email ou mot de passe incorrect'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 401
        return render_template('login.html', error=error_msg)
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Inscription (désactivable en production)"""
    # FUTURE: Ajouter validation email, captcha, etc.
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        # Vérification des données
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        service = data.get('service', 'Médiation bancaire')
        
        if not all([email, password, name]):
            return jsonify({'error': 'Tous les champs sont requis'}), 400
        
        # Vérification unicité email
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Cet email est déjà utilisé'}), 400
        
        # Création utilisateur
        user = User(
            email=email,
            name=name,
            service=service,
            role='collaborateur'  # Par défaut
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Auto-login après inscription
        login_user(user)
        
        if request.is_json:
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

# 🏠 Routes principales
@app.route('/')
def index():
    """Page d'accueil - Redirige vers login ou dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard personnel du collaborateur avec gestion d'erreurs robuste"""
    try:
        # Statistiques utilisateur
        total_docs = Document.query.filter_by(user_id=current_user.id).count()
        
        # Documents ce mois-ci
        now = datetime.now()
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        docs_this_month = Document.query.filter(
            Document.user_id == current_user.id,
            Document.created_at >= first_day_of_month
        ).count()

        # Documents récents avec toutes leurs données
        recent_docs = Document.query.filter_by(user_id=current_user.id)\
                                   .order_by(Document.updated_at.desc())\
                                   .limit(10).all()

        # Calcul sécurisé des corrections
        corrections_count = 0
        for doc in recent_docs:
            if doc.corrections_count:
                corrections_count += doc.corrections_count

        # Temps économisé (estimation : 0.1h par correction)
        time_saved_hours = round(corrections_count * 0.1, 1) if corrections_count > 0 else 0

        # Construction du dictionnaire stats
        stats = {
            'total_documents': total_docs,
            'documents_this_month': docs_this_month,
            'total_corrections': corrections_count,
            'time_saved': time_saved_hours,
            'recent_documents': []
        }

        # Conversion sécurisée des documents
        for doc in recent_docs:
            doc_dict = {
                'id': doc.id,
                'title': doc.title or 'Sans titre',
                'agent_used': doc.agent_used or 'jurifix',
                'status': doc.status or 'draft',
                'created_at': doc.created_at.strftime('%d/%m/%Y %H:%M') if doc.created_at else 'N/A',
                'updated_at': doc.updated_at.strftime('%d/%m/%Y %H:%M') if doc.updated_at else 'N/A',
                'word_count': doc.word_count or 0,
                'corrections_count': doc.corrections_count or 0
            }
            stats['recent_documents'].append(doc_dict)

        # Debug : afficher les données dans la console
        app.logger.info(f"Dashboard chargé pour l'utilisateur: {current_user.email}")
        app.logger.info(f"Stats: {stats}")

        return render_template('dashboard.html', user=current_user, stats=stats)

    except Exception as e:
        # Log de l'erreur
        app.logger.error(f"Erreur dans dashboard: {str(e)}")
        app.logger.error(f"Type d'erreur: {type(e).__name__}")
        
        # Données minimales en cas d'erreur
        stats = {
            'total_documents': 0,
            'documents_this_month': 0,
            'total_corrections': 0,
            'time_saved': 0,
            'recent_documents': []
        }
        
        # Afficher quand même le dashboard avec données vides
        return render_template('dashboard.html', user=current_user, stats=stats)

@app.route('/editor')
@app.route('/editor/<agent_name>')
@login_required
def editor(agent_name='jurifix'):
    """Éditeur avec agent IA"""
    if agent_name not in AGENTS:
        agent_name = 'jurifix'
    
    # Utiliser le nouveau template editor.html
    return render_template('editor.html', 
                         agent=AGENTS[agent_name], 
                         user=current_user,
                         current_date=datetime.now().strftime('%d/%m/%Y'))

# 📄 Routes pour les nouvelles pages
@app.route('/profile')
@login_required
def profile():
    """Page de profil utilisateur"""
    return render_template('profile.html', user=current_user)

@app.route('/documents')
@login_required
def documents():
    """Page de gestion des documents"""
    return render_template('documents.html', user=current_user)

@app.route('/stats')
@login_required
def stats():
    """Page des statistiques"""
    return render_template('stats.html', user=current_user)

# 🤖 Configuration des agents IA
class AIAgent:
    def __init__(self, name, description, prompt_template, model="gpt-4", access_level="collaborateur"):
        self.name = name
        self.description = description
        self.prompt_template = prompt_template
        self.model = model
        self.access_level = access_level  # FUTURE: Gestion des accès par rôle

AGENTS = {
    "jurifix": AIAgent(
        name="JuriFix - Correction Orthographique Précise",
        description="Corrige uniquement l'orthographe et la grammaire sans modifier le style ou les formulations juridiques",
        prompt_template="""Tu es un correcteur orthographique expert spécialisé en textes juridiques.

RÈGLES ABSOLUES À RESPECTER :
1. Corrige UNIQUEMENT l'orthographe, la grammaire et la ponctuation
2. Ne change JAMAIS les formulations, le style ou le vocabulaire juridique
3. Préserve ABSOLUMENT la structure et la longueur des phrases
4. Ne reformule RIEN, ne résume RIEN, ne raccourcis RIEN
5. Garde exactement le même niveau de langage et le même ton
6. Conserve tous les termes juridiques techniques tels quels
7. Retourne UNIQUEMENT le texte corrigé, sans aucun commentaire avant ou après
8. Préserve EXACTEMENT le nombre de mots et la structure des phrases

Texte à corriger : \"\"\"{}\"\"\"

Retourne UNIQUEMENT le texte corrigé :""",
        model="gpt-4",
        access_level="collaborateur"
    ),
    # FUTURE: Ajouter d'autres agents
    # "anonymizer": AIAgent(..., access_level="collaborateur"),
    # "summarizer": AIAgent(..., access_level="senior"),
    # "legal_analyzer": AIAgent(..., access_level="expert")
}

# 📝 API - Traitement des documents


@app.route('/api/process-text', methods=['POST'])
@login_required
def process_text():
    """Traite un texte avec l'agent sélectionné"""
    data = request.get_json()
    texte = data.get("texte", "")
    agent_name = data.get("agent", "jurifix")
    document_id = data.get("document_id", None)
    
    # Nettoyer le HTML reçu de l'éditeur
    if '<p>' in texte or '<div>' in texte:
        soup = BeautifulSoup(texte, 'html.parser')
        texte_brut = soup.get_text(separator='\n')
    else:
        texte_brut = texte
    
    if not texte_brut.strip():
        return jsonify({"error": "Texte vide"}), 400
    
    if agent_name not in AGENTS:
        return jsonify({"error": "Agent non reconnu"}), 400
    
    agent = AGENTS[agent_name]
    start_time = datetime.utcnow()
    
    try:
        # Anonymisation RGPD
        texte_anonyme = anonymiser_texte(texte_brut)
        
        # Appel à l'IA
        prompt = agent.prompt_template.format(texte_anonyme)
        
        messages = [
            {
                "role": "system",
                "content": "Tu es un correcteur orthographique expert. Tu corriges UNIQUEMENT l'orthographe et la grammaire. Retourne le texte corrigé sans guillemets, sans commentaires, sans préambule."
            },
            {"role": "user", "content": prompt}
        ]
        
        completion = client.chat.completions.create(
            model=agent.model,
            messages=messages,
            temperature=0.0,
            max_tokens=len(texte_anonyme.split()) * 3
        )
        
        texte_corrige = completion.choices[0].message.content.strip()
        
        # Nettoyer les guillemets indésirables
        if texte_corrige.startswith('"') and texte_corrige.endswith('"'):
            texte_corrige = texte_corrige[1:-1]
        if texte_corrige.startswith("'") and texte_corrige.endswith("'"):
            texte_corrige = texte_corrige[1:-1]
        
        # Préserver la structure HTML si présente
        if '<p>' in texte or '<div>' in texte:
            # Reconstituer le HTML avec le texte corrigé
            paragraphes_corriges = texte_corrige.split('\n')
            html_corrige = ''.join([f'<p>{p}</p>' for p in paragraphes_corriges if p.strip()])
            texte_corrige = html_corrige
        
        # Calcul des statistiques
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        word_count = len(texte_brut.split())
        
        # Compter les corrections (simplification)
        corrections_count = 0
        if texte_brut != texte_corrige:
            corrections_count = max(1, abs(len(texte_brut.split()) - len(texte_corrige.split())))
        
        # Sauvegarder en base si document_id fourni
        if document_id:
            document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
            if document:
                document.content = texte
                document.corrected_content = texte_corrige
                document.status = 'completed'
                document.word_count = word_count
                document.corrections_count = corrections_count
                document.processing_time = processing_time
                document.updated_at = datetime.utcnow()
                db.session.commit()
        
        response_data = {
            "resultat": texte_corrige,
            "agent_used": agent_name,
            "stats": {
                "processing_time": round(processing_time, 2),
                "word_count": word_count,
                "corrections_count": corrections_count
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"❌ Erreur traitement: {e}")
        return jsonify({"error": f"Erreur lors du traitement: {str(e)}"}), 500

# Ajoute cette nouvelle route pour sauvegarder les documents
@app.route('/api/documents/save', methods=['POST'])
@login_required  
def save_document():
    """Sauvegarde ou met à jour un document"""
    data = request.get_json()
    
    document_id = data.get('id')
    title = data.get('title', f'Document du {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    content = data.get('content', '')
    corrected_content = data.get('corrected_content', '')
    agent_used = data.get('agent', 'jurifix')
    
    try:
        if document_id:
            # Mise à jour
            document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
            if not document:
                return jsonify({"error": "Document non trouvé"}), 404
                
            document.title = title
            document.content = content
            document.corrected_content = corrected_content
            document.updated_at = datetime.utcnow()
        else:
            # Nouveau document
            document = Document(
                title=title,
                content=content,
                corrected_content=corrected_content,
                agent_used=agent_used,
                user_id=current_user.id,
                status='draft'
            )
            db.session.add(document)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "document_id": document.id,
            "message": "Document sauvegardé"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route('/api/documents', methods=['GET', 'POST'])
@login_required
def handle_documents():
    """Gestion des documents de l'utilisateur"""
    if request.method == 'POST':
        data = request.get_json()
        
        document = Document(
            title=data.get('title', f'Document du {datetime.now().strftime("%d/%m/%Y")}'),
            content=data.get('content', ''),
            agent_used=data.get('agent', 'jurifix'),
            user_id=current_user.id,
            status='draft'
        )
        
        db.session.add(document)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "document_id": document.id,
            "message": "Document créé avec succès"
        })
    
    # GET - Liste des documents de l'utilisateur
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    documents = Document.query.filter_by(user_id=current_user.id)\
                             .order_by(Document.updated_at.desc())\
                             .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "documents": [doc.to_dict() for doc in documents.items],
        "total": documents.total,
        "pages": documents.pages,
        "current_page": page
    })

@app.route('/api/documents/<document_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_document(document_id):
    """Gestion d'un document spécifique"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'GET':
        return jsonify({
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "corrected_content": document.corrected_content,
            "agent_used": document.agent_used,
            "status": document.status,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "stats": {
                "word_count": document.word_count,
                "corrections_count": document.corrections_count,
                "processing_time": document.processing_time
            }
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        document.title = data.get('title', document.title)
        document.content = data.get('content', document.content)
        document.status = data.get('status', document.status)
        document.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({"success": True, "message": "Document mis à jour"})
    
    elif request.method == 'DELETE':
        db.session.delete(document)
        db.session.commit()
        return jsonify({"success": True, "message": "Document supprimé"})

# 📊 API - Statistiques utilisateur
@app.route('/api/stats')
@login_required
def user_stats():
    """Statistiques détaillées de l'utilisateur"""
    # FUTURE: Ajouter des statistiques plus poussées avec graphiques
    
    total_docs = Document.query.filter_by(user_id=current_user.id).count()
    total_words = db.session.query(db.func.sum(Document.word_count))\
                           .filter_by(user_id=current_user.id).scalar() or 0
    
    # Documents par mois (6 derniers mois)
    monthly_stats = []
    for i in range(6):
        month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        
        count = Document.query.filter(
            Document.user_id == current_user.id,
            Document.created_at >= month_start,
            Document.created_at < month_end
        ).count()
        
        monthly_stats.append({
            'month': month_start.strftime('%B %Y'),
            'count': count
        })
    
    return jsonify({
        'total_documents': total_docs,
        'total_words_processed': total_words,
        'monthly_stats': list(reversed(monthly_stats)),
        'favorite_agent': 'jurifix'  # FUTURE: Calculer le vrai favori
    })

# 🔐 Fonction d'anonymisation RGPD
def anonymiser_texte(texte):
    """Anonymise les données personnelles sensibles"""
    # Noms et prénoms
    texte = re.sub(r"\b(Monsieur|Mr|M\.|Madame|Mme|Mlle)\s+([A-Z][a-zéèêëàâäôöûüç]+(?:\s+[A-Z][a-zéèêëàâäôöûüç]+)?)", 
                   r"\1 [nom]", texte, flags=re.IGNORECASE)
    
    # Email
    texte = re.sub(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b", "[email]", texte)
    
    # Téléphone
    texte = re.sub(r"\b0[1-9][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}\b", "[téléphone]", texte)
    
    # IBAN
    texte = re.sub(r"\b[A-Z]{2}\d{2}[\s]?[\w\s]{4,30}\b", "[IBAN]", texte)
    
    return texte

# 🛠️ Routes utilitaires
@app.route('/api/agents')
@login_required
def get_agents():
    """Liste des agents disponibles pour l'utilisateur"""
    # FUTURE: Filtrer selon les permissions
    available_agents = {}
    for name, agent in AGENTS.items():
        # if has_access_to_agent(current_user, agent):
        available_agents[name] = {
            "name": agent.name,
            "description": agent.description,
            "model": agent.model
        }
    
    return jsonify(available_agents)

@app.route('/api/profile', methods=['GET', 'PUT'])
@login_required
def profile_api():
    """Renvoie ou met à jour les données du profil en JSON"""
    if request.method == 'GET':
        return jsonify({
            'id': current_user.id,
            'email': current_user.email,
            'name': current_user.name,
            'service': current_user.service,
            'role': current_user.role,
            'created_at': current_user.created_at.isoformat(),
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None
        })

    elif request.method == 'PUT':
        data = request.get_json()
        
        # Mise à jour des infos autorisées
        if 'name' in data:
            current_user.name = data['name']
        if 'service' in data:
            current_user.service = data['service']
        
        # FUTURE: Permettre changement de mot de passe
        # if 'password' in data and 'old_password' in data:
        #     if current_user.check_password(data['old_password']):
        #         current_user.set_password(data['password'])
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Profil mis à jour'})

# 🔍 Routes de test et santé
@app.route('/health')
def health_check():
    """Vérification de santé de l'application"""
    try:
        # Test DB
        User.query.first()
        db_status = 'OK'
    except:
        db_status = 'ERROR'
    
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'services': {
            'database': db_status,
            'openai': 'OK' if client.api_key else 'ERROR'
        }
    })

# 🚀 Points d'extension pour V2/V3
# FUTURE: Routes espace client
# @app.route('/client/dashboard')
# @require_role('client')
# def client_dashboard():
#     """Dashboard pour les clients (particuliers)"""
#     pass

# FUTURE: Routes espace banque
# @app.route('/bank/dashboard')
# @require_role('banque')
# def bank_dashboard():
#     """Dashboard pour les représentants bancaires"""
#     pass

# FUTURE: Routes administration
# @app.route('/admin/dashboard')
# @require_role('admin')
# def admin_dashboard():
#     """Dashboard administration globale"""
#     pass

# FUTURE: API publique pour intégrations
# @app.route('/api/v1/process', methods=['POST'])
# @require_api_key
# def api_process():
#     """API publique pour traitement automatisé"""
#     pass

# 🛠️ Gestion des erreurs
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint non trouvé'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erreur serveur'}), 500
    return render_template('500.html'), 500

# Remplacez la fonction create_tables() dans app.py par cette version améliorée

def create_tables():
    """Création des tables DB avec gestion d'erreurs améliorée"""
    with app.app_context():
        try:
            # Suppression et recréation des tables (ATTENTION: perte de données!)
            # Décommentez uniquement si vous voulez réinitialiser complètement
            # db.drop_all()
            
            # Création de toutes les tables
            db.create_all()
            print("✅ Tables créées avec succès")
            
            # Vérification de l'existence d'utilisateurs
            if User.query.count() == 0:
                # Création d'un utilisateur de test
                test_user = User(
                    email='test@jurisfix.fr',
                    name='Utilisateur Test',
                    service='Service Test - Médiation bancaire',
                    role='collaborateur'
                )
                test_user.set_password('password123')
                test_user.is_active = True
                test_user.created_at = datetime.utcnow()
                
                db.session.add(test_user)
                
                # Création d'un admin pour les tests (optionnel)
                admin_user = User(
                    email='admin@jurisfix.fr',
                    name='Administrateur JurisFix',
                    service='Administration',
                    role='admin'
                )
                admin_user.set_password('admin123')
                admin_user.is_active = True
                admin_user.created_at = datetime.utcnow()
                
                db.session.add(admin_user)
                
                # Création d'utilisateurs de démonstration
                demo_users = [
                    {
                        'email': 'marie.dupont@jurisfix.fr',
                        'name': 'Marie Dupont',
                        'service': 'Médiation bancaire - Particuliers',
                        'role': 'collaborateur'
                    },
                    {
                        'email': 'jean.martin@jurisfix.fr',
                        'name': 'Jean Martin',
                        'service': 'Médiation bancaire - Entreprises',
                        'role': 'collaborateur'
                    }
                ]
                
                for user_data in demo_users:
                    user = User(**user_data)
                    user.set_password('demo123')
                    user.is_active = True
                    user.created_at = datetime.utcnow()
                    db.session.add(user)
                
                db.session.commit()
                
                print("✅ Utilisateurs de test créés:")
                print("   📧 test@jurisfix.fr / password123 (collaborateur)")
                print("   📧 admin@jurisfix.fr / admin123 (admin)")
                print("   📧 marie.dupont@jurisfix.fr / demo123")
                print("   📧 jean.martin@jurisfix.fr / demo123")
                
                # Création de documents de démonstration
                create_demo_documents()
                
            else:
                print(f"ℹ️  {User.query.count()} utilisateur(s) déjà présent(s)")
            
            print("✅ Base de données initialisée avec succès")
            
        except Exception as e:
            print(f"❌ Erreur lors de la création des tables: {e}")
            raise

def create_demo_documents():
    """Crée des documents de démonstration pour les tests"""
    try:
        # Récupérer l'utilisateur test
        test_user = User.query.filter_by(email='test@jurisfix.fr').first()
        
        if test_user:
            demo_docs = [
                {
                    'title': 'Lettre de médiation - Frais bancaires',
                    'content': """Madame, Monsieur,

Suite à votre réclamation du 15 janvier 2024 concernant les frais bancaires prélevés sur votre compte, nous avons procédé à une analyse détaillée de votre situation.

Après vérification, nous constatons que les frais contestés correspondent bien aux conditions générales de votre contrat. Néanmoins, compte tenu de votre situation et de votre ancienneté en tant que client, nous proposons un geste commercial.

Cordialement,
Le service médiation""",
                    'agent_used': 'jurifix',
                    'status': 'completed',
                    'word_count': 67,
                    'corrections_count': 3
                },
                {
                    'title': 'Réponse client - Contestation crédit',
                    'content': """Objet : Votre demande de médiation n°2024-0542

Madame Dupont,

Nous accusons réception de votre demande de médiation concernant votre crédit immobilier. Le dossier a été transmis à notre service juridique pour analyse approfondie.

Vous recevrez une réponse détaillée sous 15 jours ouvrés.

Bien cordialement,
Service Médiation Bancaire""",
                    'agent_used': 'jurifix',
                    'status': 'draft',
                    'word_count': 54,
                    'corrections_count': 0
                }
            ]
            
            for doc_data in demo_docs:
                doc = Document(
                    title=doc_data['title'],
                    content=doc_data['content'],
                    agent_used=doc_data['agent_used'],
                    user_id=test_user.id,
                    status=doc_data['status'],
                    word_count=doc_data['word_count'],
                    corrections_count=doc_data['corrections_count']
                )
                db.session.add(doc)
            
            db.session.commit()
            print("✅ Documents de démonstration créés")
            
    except Exception as e:
        print(f"⚠️  Impossible de créer les documents de démo: {e}")

def verify_database_integrity():
    """Vérifie l'intégrité de la base de données"""
    with app.app_context():
        try:
            # Test de lecture
            user_count = User.query.count()
            doc_count = Document.query.count()
            
            print(f"\n📊 État de la base de données:")
            print(f"   👥 Utilisateurs: {user_count}")
            print(f"   📄 Documents: {doc_count}")
            
            # Test d'écriture
            test_user = User.query.filter_by(email='test@jurisfix.fr').first()
            if test_user:
                test_user.last_login = datetime.utcnow()
                db.session.commit()
                print("   ✅ Test d'écriture réussi")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur d'intégrité: {e}")
            return False

# 🏃 Lancement de l'application
if __name__ == '__main__':
    print("✅ JurisFix Platform V1 - Service de médiation bancaire")
    print("📍 URL: http://localhost:5002")
    print("👤 Login test: test@jurisfix.fr / password123")
    
    create_tables()
    
    # Mode développement
    app.run(debug=True, port=5002, host='0.0.0.0')
    
    # FUTURE: En production, utiliser Gunicorn
    # gunicorn -w 4 -b 0.0.0.0:5002 app:app