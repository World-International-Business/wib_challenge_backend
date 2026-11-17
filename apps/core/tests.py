from django.test import SimpleTestCase, override_settings

ALLOWED_ORIGIN = 'https://recrutement.worldwide-international.business'
DENIED_ORIGIN = 'https://evil.example.com'

AUTH_ENDPOINTS = [
    '/api/auth/login/',
    '/api/auth/register/',
    '/api/auth/google/',
    '/api/auth/google/callback/',
]


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN],
    CORS_ALLOWED_ORIGIN_REGEXES=[],
)
class CorsPreflightTests(SimpleTestCase):
    """Vérifie que les preflight OPTIONS répondent sans auth ni redirection."""

    def _preflight(self, path, origin):
        return self.client.options(
            path,
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type',
        )

    def test_preflight_allowed_origin(self):
        for path in AUTH_ENDPOINTS:
            with self.subTest(path=path):
                response = self._preflight(path, ALLOWED_ORIGIN)
                self.assertLess(response.status_code, 300)
                self.assertEqual(
                    response['Access-Control-Allow-Origin'],
                    ALLOWED_ORIGIN,
                )
                self.assertIn('POST', response['Access-Control-Allow-Methods'])
                self.assertIn(
                    'content-type',
                    response['Access-Control-Allow-Headers'].lower(),
                )

    def test_preflight_denied_origin(self):
        for path in AUTH_ENDPOINTS:
            with self.subTest(path=path):
                response = self._preflight(path, DENIED_ORIGIN)
                self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_actual_response_carries_cors_header(self):
        response = self.client.post(
            '/api/auth/login/',
            data='{}',
            content_type='application/json',
            HTTP_ORIGIN=ALLOWED_ORIGIN,
        )
        self.assertEqual(
            response['Access-Control-Allow-Origin'],
            ALLOWED_ORIGIN,
        )

    def test_error_response_carries_cors_header(self):
        response = self.client.get(
            '/api/auth/login/',
            HTTP_ORIGIN=ALLOWED_ORIGIN,
        )
        self.assertEqual(
            response['Access-Control-Allow-Origin'],
            ALLOWED_ORIGIN,
        )
