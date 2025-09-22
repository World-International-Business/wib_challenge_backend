import os
import json
from typing import Any, Dict
import redis
import logging
from redis.exceptions import ReadOnlyError

# Même configuration que le consumer FastAPI
STREAM_KEY = os.getenv("STREAM_KEY")
STREAM_FIELD = os.getenv("STREAM_FIELD")  # champ utilisé pour stocker le JSON
REDIS_URL = os.getenv("REDIS_URL")
# URL d'écriture prioritaire (primaire). Utilise l'URL fournie par défaut si non configurée.
REDIS_WRITE_URL = os.getenv("REDIS_WRITE_URL")

# Compatibilité avec le producteur alternatif fourni par l'utilisateur
# Si ACTIVÉ, on duplique l'envoi sur un stream/field alternatif
STREAM_COMPAT_ENABLED = os.getenv("STREAM_COMPAT_ENABLED").lower() in {"1", "true", "yes"}
STREAM_COMPAT_KEY = os.getenv("STREAM_COMPAT_KEY")
STREAM_COMPAT_FIELD = os.getenv("STREAM_COMPAT_FIELD")

# Fallback host/port/password si REDIS_URL n'est pas défini
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

logger = logging.getLogger(__name__)

# Option pour faire remonter les erreurs au lieu de les masquer (utile en dev/tests)
RAISE_ON_ERROR = os.getenv("REDIS_RAISE_ON_ERROR").lower() in {"1", "true", "yes"}
# Option pour suivre automatiquement le master si l'URL cible est un replica
FOLLOW_MASTER = os.getenv("REDIS_FOLLOW_MASTER").lower() in {"1", "true", "yes"}


def get_redis_client() -> "redis.Redis[str]":
    """Retourne un client Redis configuré à partir de REDIS_URL.
    Utilise decode_responses=True pour manipuler des str.
    """
    # Priorité à l'URL d'écriture si fournie (assurée par défaut ci-dessus)
    client = None
    if REDIS_WRITE_URL:
        client = redis.from_url(REDIS_WRITE_URL, decode_responses=True)
    elif REDIS_URL:
        client = redis.from_url(REDIS_URL, decode_responses=True)
    else:
        # Fallback connexion explicite host/port/password (inspiration du code testé par l'utilisateur)
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)

    if FOLLOW_MASTER:
        try:
            info = client.info(section="replication")
            role = info.get("role")
            if role and role.lower() in {"slave", "replica"}:
                master_host = info.get("master_host") or info.get("masterhost")
                master_port = info.get("master_port") or info.get("masterport")
                if master_host and master_port:
                    # On réutilise le même mot de passe que REDIS_WRITE_URL/REDIS_URL/fallback
                    password = None
                    try:
                        # Extraire le password de l'URL si disponible
                        from urllib.parse import urlparse
                        parsed = urlparse(REDIS_WRITE_URL or REDIS_URL or "")
                        if parsed.password:
                            password = parsed.password
                    except Exception:
                        pass
                    # Reconnexion directe au master détecté
                    logger.info("FOLLOW_MASTER: cible initiale=%s role=%s -> connexion au master %s:%s",
                                (REDIS_WRITE_URL or REDIS_URL or f"{REDIS_HOST}:{REDIS_PORT}"), role, master_host, master_port)
                    return redis.Redis(host=master_host, port=int(master_port), password=password or REDIS_PASSWORD, decode_responses=True)
                else:
                    logger.warning("FOLLOW_MASTER: instance en replica mais master_host/port introuvable dans INFO; écriture peut échouer (ReadOnly)")
            else:
                logger.info("FOLLOW_MASTER: instance cible rôle=%s (pas de bascule)", role)
        except Exception:
            # En cas d'échec d'inspection, on conserve le client initial
            if RAISE_ON_ERROR:
                raise
    # Log de la cible finale (URL ou host:port)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(REDIS_WRITE_URL or REDIS_URL or "")
        if parsed.scheme:
            logger.info("Client Redis initialisé sur %s", (REDIS_WRITE_URL or REDIS_URL))
        else:
            logger.info("Client Redis initialisé sur %s:%s", REDIS_HOST, REDIS_PORT)
    except Exception:
        pass
    return client


def publish_json(stream_key: str, data: Dict[str, Any]) -> bool:
    """Publie un message JSON dans un stream Redis avec le champ configuré.

    Retourne True si la publication a réussi, False sinon (sauf si RAISE_ON_ERROR=True, alors l'exception est relancée).
    """
    try:
        client = get_redis_client()
        payload = json.dumps(data, ensure_ascii=False)
        msg_id = client.xadd(stream_key, {STREAM_FIELD: payload}, id="*")
        logger.info("Message publié sur Redis", extra={
            "stream": stream_key,
            "message_id": msg_id,
        })

        # Option de compatibilité: dupliquer l'envoi vers un autre stream/field
        if STREAM_COMPAT_ENABLED:
            compat_id = client.xadd(STREAM_COMPAT_KEY, {STREAM_COMPAT_FIELD: payload}, id="*")
            logger.info("Message dupliqué sur Redis (compat)", extra={
                "stream": STREAM_COMPAT_KEY,
                "message_id": compat_id,
            })
        return True
    except ReadOnlyError:
        logger.exception("La base Redis est en lecture seule (replica). Connectez-vous au primaire pour XADD.")
        if RAISE_ON_ERROR:
            raise
        return False
    except Exception:
        # On log l'exception; l'appelant peut choisir d'ignorer l'erreur
        logger.exception("Échec de la publication du message sur Redis (stream=%s)", stream_key)
        if RAISE_ON_ERROR:
            # En dev/test, permettre d'échouer bruyamment pour diagnostiquer
            raise
        return False


def _main() -> None:
    """Point d'entrée de test pour exécuter ce fichier directement.
    - Configure le logging
    - Vérifie la connectivité Redis (PING)
    - Envoie un message de test sur le stream configuré
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logger.info(
        "Config Redis: write_url=%s url=%s host=%s port=%s stream=%s field=%s compat_enabled=%s",
        REDIS_WRITE_URL, REDIS_URL, REDIS_HOST, REDIS_PORT, STREAM_KEY, STREAM_FIELD, STREAM_COMPAT_ENABLED,
    )

    try:
        client = get_redis_client()
        pong = client.ping()
        logger.info("PING Redis -> %s", pong)
        try:
            rinfo = client.info(section="replication")
            logger.info("ROLE=%s master_host=%s master_port=%s", rinfo.get("role"), rinfo.get("master_host"), rinfo.get("master_port"))
        except Exception:
            logger.debug("Impossible de récupérer INFO replication")
    except Exception:
        logger.exception("Impossible de se connecter à Redis. Vérifiez REDIS_URL/REDIS_HOST/PORT/PASSWORD.")
        if RAISE_ON_ERROR:
            raise
        return

    # Payload de test
    test_payload: Dict[str, Any] = {
  "id": 199,
  "profession": "test",
  "user": "test",
  "technologies": [
    {
      "id": 0,
      "name": "test",
      "level": 0
    }
  ],
  "createdAt": "2025-09-19T09:13:17.764Z",
  "updatedAt": "2025-09-19T09:13:17.764Z",
  "location": "test",
  "shortBio": "test",
  "biography": "test",
  "disability": True,
  "openToWork": True,
  "yearsExperience": 0,
  "otherYearsExperience": 0,
  "highestDegree": 0,
  "interestedBy": "test"
}

    try:
        ok = publish_json(STREAM_KEY, test_payload)
        if ok:
            logger.info("Test: publication effectuée sur stream='%s'", STREAM_KEY)
        else:
            logger.error("Test: la publication a échoué sur stream='%s' (voir logs ci-dessus)", STREAM_KEY)
    except Exception:
        logger.exception("Test: échec d'envoi sur le stream '%s'", STREAM_KEY)
        if RAISE_ON_ERROR:
            raise


if __name__ == "__main__":
    _main()
