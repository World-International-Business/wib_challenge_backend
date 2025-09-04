from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter


class AppRouter(DefaultRouter):
    _instance = None
    include_root_view = False

    def __init__(self):
        super().__init__(use_regex_path=False, trailing_slash=True)
        self._default_value_pattern = 'int'

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AppRouter, cls).__new__(cls)
        return cls._instance


class AppNestedDefaultRouter(NestedDefaultRouter):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('use_regex_path', False)
        kwargs.setdefault('trailing_slash', True)
        super().__init__(*args, **kwargs)
        self._default_value_pattern = 'int'
