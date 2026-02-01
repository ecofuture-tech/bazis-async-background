from django.utils.translation import gettext_lazy as _

from bazis.core.utils.apps import BaseConfig


class AsyncBackgroundConfig(BaseConfig):
    name = "bazis.contrib.async_background"
    verbose_name = _("AsyncBackground")
    default = True
