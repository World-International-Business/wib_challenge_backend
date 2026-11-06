# Guide de DÃ©ploiement Automatique - WIB Challenge Backend

## ðŸš€ DÃ©ploiement Automatique avec GitHub Actions

### PrÃ©requis
- Repository GitHub avec le code
- Serveur de production avec SSH
- Base de donnÃ©es PostgreSQL

### Configuration GitHub Actions

1. **Ajouter les secrets GitHub** (Settings â†’ Secrets and variables â†’ Actions):
   - `DATABASE_URL` : URL de connexion PostgreSQL
   - `SECRET_KEY` : ClÃ© secrÃ¨te Django
   - `SERVER_HOST` : Adresse IP ou domaine du serveur
   - `SERVER_USER` : Utilisateur SSH du serveur
   - `SSH_PRIVATE_KEY` : ClÃ© privÃ©e SSH pour la connexion

2. **Workflow automatique** :
   - Se dÃ©clenche automatiquement lors d'un push sur `old_master`
   - Peut aussi Ãªtre dÃ©clenchÃ© manuellement
   - ExÃ©cute les migrations
   - Peuple les donnÃ©es Ã©ducatives
   - RedÃ©marre les services

## ðŸ³ DÃ©ploiement avec Docker

### Configuration locale
```bash
# Copier le fichier d'exemple
cp .env.example .env

# Configurer les variables d'environnement obligatoires
nano .env
```

### Variables nÃ©cessaires dans `.env`
```bash
DEBUG=False
SECRET_KEY=votre_clÃ©_secrÃ¨te_ici
POSTGRES_DB=wib_challenge
POSTGRES_USER=wib_user
POSTGRES_PASSWORD=un_mot_de_passe_fort
ALLOWED_HOSTS=votre-domaine.com,www.votre-domaine.com
PUBLIC_SITE_URL=https://votre-domaine.com
CSRF_TRUSTED_ORIGINS=https://votre-domaine.com

# Configuration email (optionnel)
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app
SMTP_FROM=noreply@wib-challenge.com
```

`SECRET_KEY`, `POSTGRES_PASSWORD`, `ALLOWED_HOSTS` et `PUBLIC_SITE_URL` sont
obligatoires. Ils n'ont volontairement pas de valeur par dÃ©faut en production.

### Lancer avec Docker Compose
```bash
# Construire et dÃ©marrer (le proxy HTTPS doit Ãªtre configurÃ© sÃ©parÃ©ment)
docker compose up -d --build

# Voir les logs
docker compose logs -f web

# ArrÃªter
docker compose down
```

Le service `web` Ã©coute sur le port 8000 dans le rÃ©seau Compose et dÃ©marre
Gunicorn aprÃ¨s les migrations et `collectstatic`. Un reverse proxy (Traefik,
Dokploy ou Nginx externe) doit router le trafic vers ce service et servir
`/static/` et `/media/` selon la configuration de l'hÃ©bergeur.

## ðŸ“‹ Processus de DÃ©ploiement Automatique

### 1. DÃ©veloppement â†’ Git
```bash
git add .
git commit -m "Description des changements"
git push origin old_master
```

### 2. GitHub Actions s'exÃ©cute automatiquement :
- âœ… Checkout du code
- âœ… Installation des dÃ©pendances
- âœ… ExÃ©cution des migrations
- âœ… Peuplement des donnÃ©es Ã©ducatives
- âœ… DÃ©ploiement sur le serveur
- âœ… RedÃ©marrage des services

### 3. Serveur de production :
- âœ… Pull du code
- âœ… Installation des dÃ©pendances
- âœ… Migrations de base de donnÃ©es
- âœ… Peuplement des donnÃ©es
- âœ… RedÃ©marrage de Gunicorn
- âœ… Rechargement de Nginx

## ðŸ”§ Configuration du Serveur

### Installation des dÃ©pendances
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
# CrÃ©er le service systemd
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

## ðŸ—„ï¸ Base de DonnÃ©es

### PostgreSQL Configuration
```sql
-- CrÃ©er la base de donnÃ©es
CREATE DATABASE wib_challenge;

-- CrÃ©er l'utilisateur
CREATE USER wib_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE wib_challenge TO wib_user;
```

### Migration automatique
Les migrations sont exÃ©cutÃ©es automatiquement lors du dÃ©ploiement via :
- L'entrypoint.sh (Docker)
- Le workflow GitHub Actions (serveur)

## ðŸ“§ Configuration Email

### Gmail (recommandÃ© pour le dÃ©veloppement)
1. Activer l'authentification Ã  2 facteurs
2. GÃ©nÃ©rer un mot de passe d'application
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
- SMTP personnalisÃ©

## ðŸ” VÃ©rification du DÃ©ploiement

### VÃ©rifier les services
```bash
# VÃ©rifier Gunicorn
sudo systemctl status gunicorn

# VÃ©rifier Nginx
sudo systemctl status nginx

# VÃ©rifier les logs
sudo journalctl -u gunicorn -f
```

### VÃ©rifier l'application
```bash
# Test local
curl http://localhost:8000/admin/

# Test distant
curl https://votre-domaine.com/admin/
```

## ðŸš¨ DÃ©pannage

### Erreurs courantes
1. **Migration Ã©choue** : VÃ©rifier la connexion Ã  la base de donnÃ©es
2. **DonnÃ©es non peuplÃ©es** : VÃ©rifier les logs dans seed_education_data.py
3. **Email non envoyÃ©** : VÃ©rifier la configuration SMTP et les logs
4. **Static files 404** : ExÃ©cuter `python manage.py collectstatic`

### Logs
```bash
# Docker logs
docker-compose logs -f web

# Application logs
tail -f /var/log/gunicorn/error.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

## ðŸ“ž Support

Pour toute question sur le dÃ©ploiement :
- VÃ©rifier les logs dÃ©taillÃ©s
- Consulter la documentation Django
- VÃ©rifier la configuration des secrets GitHub

---

**Note** : Le systÃ¨me de peuplement automatique (`seed_education_data.py`) est conÃ§u pour Ãªtre idempotent - il peut Ãªtre exÃ©cutÃ© plusieurs fois sans crÃ©er de doublons.
