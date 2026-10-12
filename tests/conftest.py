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

import pytest

# the tests marked `run_with_consumer` need a Kafka broker and a running consumer
# (`python manage.py kafka_consumer_single` in `sample`, see CLAUDE.md)
from bazis.contrib.async_background.testing import pytest_collection_modifyitems  # noqa: F401


@pytest.fixture(scope='function')
def sample_app():
    from sample.main import app

    return app
