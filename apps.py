from django.apps import AppConfig

class WarrantyConfig(AppConfig):
    name = "warranty"
    verbose_name = "Warranty"

    def ready(self):
        from . import create_plugin_class
        create_plugin_class()
