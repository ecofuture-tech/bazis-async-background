# Copyright 2026 EcoFuture Technology Services LLC and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from django.conf import settings as _settings

import bazis.core.configure  # noqa: F401


# Ensure pytest uses the same DB name unless TEST.NAME is explicitly set via env.
_default_db = _settings.DATABASES.get("default", {})
_default_db.setdefault("TEST", {})
_default_db["TEST"].setdefault("NAME", _default_db.get("NAME"))
