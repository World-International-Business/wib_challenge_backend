import logging
import time
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('wib_challenge')


class ErrorLoggingMiddleware(MiddlewareMixin):
    """Middleware pour logger les erreurs et les requêtes"""

    def process_request(self, request):
        request.start_time = time.time()
        request.request_id = str(uuid.uuid4())[:8]

        user = 'Anonymous'
        if hasattr(request, 'user') and hasattr(request.user, 'email'):
            user = request.user.email

        logger.info(f"[{request.request_id}] {request.method} {request.path} - User: {user}")
        return None

    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(
                f"[{getattr(request, 'request_id', 'unknown')}] Response {response.status_code} - Duration: {duration:.2f}s")

        return response

    def process_exception(self, request, exception):
        request_id = getattr(request, 'request_id', 'unknown')
        user = 'Anonymous'
        if hasattr(request, 'user') and hasattr(request.user, 'email'):
            user = request.user.email

        logger.error(
            f"[{request_id}] Exception in {request.method} {request.path} - "
            f"User: {user} - Error: {str(exception)}",
            exc_info=True,
            extra={
                'request_id': request_id,
                'user': user,
                'method': request.method,
                'path': request.path,
                'exception_type': type(exception).__name__,
            }
        )

        if not settings.DEBUG:
            return JsonResponse({
                'error': 'Une erreur interne s\'est produite',
                'request_id': request_id
            }, status=500)

        return None


class SecurityLoggingMiddleware(MiddlewareMixin):
    """Middleware pour logger les événements de sécurité"""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.security_logger = logging.getLogger('django.security')

    def __call__(self, request):
        # Log suspicious activities
        self._log_suspicious_requests(request)

        response = self.get_response(request)

        # Log failed authentication attempts
        if response.status_code == 401:
            self.security_logger.warning(
                f"Authentication failed for {request.path} from {self._get_client_ip(request)}"
            )

        return response

    def _log_suspicious_requests(self, request):
        suspicious_patterns = [
            'wp-admin', 'phpmyadmin', '.php', '.asp', '.jsp',
            'eval(', 'script>', 'javascript:', 'vbscript:', 'onload='
        ]

        request_body = ''
        try:
            request_body = request.body.decode('utf-8', errors='ignore').lower()
        except:
            pass

        for pattern in suspicious_patterns:
            if pattern in request.path.lower() or pattern in request_body:
                self.security_logger.warning(
                    f"Suspicious request detected: {request.method} {request.path} from {self._get_client_ip(request)}"
                )
                break

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
