from rest_framework.routers import DefaultRouter


class AppRouter(DefaultRouter):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('use_regex_path', False)
        super().__init__(*args, **kwargs)
        self._default_value_pattern = 'int'
