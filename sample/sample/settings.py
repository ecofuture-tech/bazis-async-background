from django.conf import settings as _settings

import bazis.core.configure  # noqa: F401


# Ensure pytest uses the same DB name unless TEST.NAME is explicitly set via env.
_default_db = _settings.DATABASES.get("default", {})
_default_db.setdefault("TEST", {})
_default_db["TEST"].setdefault("NAME", _default_db.get("NAME"))
