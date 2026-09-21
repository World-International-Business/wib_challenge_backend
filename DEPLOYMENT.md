# Guide de Déploiement Automatique - WIB Challenge Backend

## 🚀 Déploiement Automatique avec GitHub Actions

### Prérequis
- Repository GitHub avec le code
- Serveur de production avec SSH
- Base de données PostgreSQL

### Configuration GitHub Actions

1. **Ajouter les secrets GitHub** (Settings → Secrets and variables → Actions):
   - `DATABASE_URL` : URL de connexion PostgreSQL
   - `SECRET_KEY` : Clé secrète Django
   - `SERVER_HOST` : Adresse IP ou domaine du serveur
   - `SERVER_USER` : Utilisateur SSH du serveur
   - `SSH_PRIVATE_KEY` : Clé privée SSH pour la connexion

2. **Workflow automatique** :
   - Se déclenche automatiquement lors d'un push sur `main`
   - Peut aussi être déclenché manuellement
   - Exécute les migrations
   - Peuple les données éducatives
   - Redémarre les services

## 🐳 Déploiement avec Docker

### Configuration locale
```bash
# Copier le fichier d'exemple
cp .env.example .env

# Configurer les variables d'environnement
nano .env
```

### Variables nécessaires dans .env
```bash
DEBUG=False
SECRET_KEY=votre_clé_secrète_ici
DATABASE_URL=postgresql://user:password@localhost:5432/wib_challenge
ALLOWED_HOSTS=votre-domaine.com,www.votre-domaine.com

# Configuration email (optionnel)
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app
SMTP_FROM=noreply@wib-challenge.com
```

### Lancer avec Docker Compose
```bash
# Construire et démarrer
docker-compose up -d

# Voir les logs
docker-compose logs -f web

# Arrêter
docker-compose down
```

## 📋 Processus de Déploiement Automatique

### 1. Développement → Git
```bash
git add .
git commit -m "Description des changements"
git push origin main
```

### 2. GitHub Actions s'exécute automatiquement :
- ✅ Checkout du code
- ✅ Installation des dépendances
- ✅ Exécution des migrations
- ✅ Peuplement des données éducatives
- ✅ Déploiement sur le serveur
- ✅ Redémarrage des services

### 3. Serveur de production :
- ✅ Pull du code
- ✅ Installation des dépendances
- ✅ Migrations de base de données
- ✅ Peuplement des données
- ✅ Redémarrage de Gunicorn
- ✅ Rechargement de Nginx

## 🔧 Configuration du Serveur

### Installation des dépendances
```bash
# Python et pip
sudo apt update
sudo apt install python3 python3-pip python3-venv

# PostgreSQL
sudo apt install postgresql postgresql-contrib

# Nginx
sudo apt install nginx

# Gunicorn
pip install gunicorn
```

### Configuration Gunicorn
```bash
# Créer le service systemd
sudo nano /etc/systemd/system/gunicorn.service
```

Contenu du service :
```ini
[Unit]
Description=gunicorn daemon for WIB Challenge
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/wib_challenge_backend
ExecStart=/path/to/venv/bin/gunicorn wib_challenge.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Activer le service :
```bash
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
```

### Configuration Nginx
```bash
sudo nano /etc/nginx/sites-available/wib_challenge
```

Configuration :
```nginx
server {
    listen 80;
    server_name votre-domaine.com;

    location /static/ {
        alias /path/to/wib_challenge_backend/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Activer le site :
```bash
sudo ln -s /etc/nginx/sites-available/wib_challenge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🗄️ Base de Données

### PostgreSQL Configuration
```sql
-- Créer la base de données
CREATE DATABASE wib_challenge;

-- Créer l'utilisateur
CREATE USER wib_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE wib_challenge TO wib_user;
```

### Migration automatique
Les migrations sont exécutées automatiquement lors du déploiement via :
- L'entrypoint.sh (Docker)
- Le workflow GitHub Actions (serveur)

## 📧 Configuration Email

### Gmail (recommandé pour le développement)
1. Activer l'authentification à 2 facteurs
2. Générer un mot de passe d'application
3. Configurer dans .env :
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app
```

### Autres fournisseurs
- SendGrid
- Mailgun
- AWS SES
- SMTP personnalisé

## 🔍 Vérification du Déploiement

### Vérifier les services
```bash
# Vérifier Gunicorn
sudo systemctl status gunicorn

# Vérifier Nginx
sudo systemctl status nginx

# Vérifier les logs
sudo journalctl -u gunicorn -f
```

### Vérifier l'application
```bash
# Test local
curl http://localhost:8000/admin/

# Test distant
curl https://votre-domaine.com/admin/
```

## 🚨 Dépannage

### Erreurs courantes
1. **Migration échoue** : Vérifier la connexion à la base de données
2. **Données non peuplées** : Vérifier les logs dans seed_education_data.py
3. **Email non envoyé** : Vérifier la configuration SMTP et les logs
4. **Static files 404** : Exécuter `python manage.py collectstatic`

### Logs
```bash
# Docker logs
docker-compose logs -f web

# Application logs
tail -f /var/log/gunicorn/error.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

## 📞 Support

Pour toute question sur le déploiement :
- Vérifier les logs détaillés
- Consulter la documentation Django
- Vérifier la configuration des secrets GitHub

---

**Note** : Le système de peuplement automatique (`seed_education_data.py`) est conçu pour être idempotent - il peut être exécuté plusieurs fois sans créer de doublons.