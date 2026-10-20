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

from django.utils.translation import gettext_lazy as _

from fastapi import Request, Response

from bazis.contrib.async_background.schemas import TaskStatus
from bazis.contrib.async_background.utils import (
    ChannelNameError,
    get_task_data_async,
    resolve_channel_name_async,
)
from bazis.core.errors import JsonApi401Exception, JsonApi403Exception, JsonApiHttpException
from bazis.core.routing import BazisRouter


router = BazisRouter(tags=[_('Async requests')])


@router.get(
    '/async_background_response/{task_id}/',
    response_model=dict,
    responses={
        200: {
            'headers': {
                'X-Task-Status': {
                    'description': 'The stored status of the task',
                    'schema': {'type': 'string', 'enum': [status.value for status in TaskStatus]},
                }
            }
        }
    },
)
async def get_async_background_response(
    request: Request, response: Response, task_id: str, full_response: bool = False
) -> dict:
    """
    Returns the result of a background task of the client (the token of the request must
    resolve to the channel the task was created with).

    Without `full_response` the body is the stored response of the task, or the placeholder
    `{"status": "not ready"}` while there is none (also for a task completed without a
    response): the header `X-Task-Status` carries the status of the task.
    """
    try:
        channel_name = await resolve_channel_name_async(request)
    except ChannelNameError as err:
        raise JsonApi401Exception from err

    task_data = await get_task_data_async(task_id)
    if not task_data:
        raise JsonApiHttpException(404, detail=_('Unknown task ID'), code='ERR_TASK_NOT_FOUND')

    if channel_name != task_data.get('channel_name'):
        raise JsonApi403Exception

    response.headers['X-Task-Status'] = task_data['status']
    if full_response:
        return task_data

    result = task_data.get('response')
    return result if result is not None else {'status': 'not ready'}
