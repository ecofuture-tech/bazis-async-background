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

import json

from django.utils.translation import gettext_lazy as _

from fastapi import HTTPException, Request

from bazis.contrib.async_background.utils import (
    ChannelNameError,
    get_redis_async,
    resolve_channel_name_async,
)
from bazis.core.errors import JsonApi401Exception, JsonApi403Exception
from bazis.core.routing import BazisRouter


router = BazisRouter(tags=[_("Async requests")])


@router.get("/async_background_response/{task_id}/", response_model=dict)
async def get_async_background_response(request: Request, task_id: str, full_response: bool = False) -> dict:
    """Returns the result of a background task by its identifier."""
    try:
        channel_name = await resolve_channel_name_async(request)
    except ChannelNameError as err:
        raise JsonApi401Exception from err

    redis_data_raw = await get_redis_async().get(task_id)
    if not redis_data_raw:
        raise HTTPException(status_code=404, detail=_("Unknown task ID"))
    try:
        redis_data = json.loads(redis_data_raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        raise HTTPException(status_code=500, detail=_("Invalid task data format in Redis")) from err

    if channel_name != redis_data["channel_name"]:
        raise JsonApi403Exception

    if full_response:
        return redis_data

    response = redis_data.get("response")
    return response if response is not None else {"status": "not ready"}

