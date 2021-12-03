"""
    Copyright 2021 Inmanta

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Contact: code@inmanta.com
"""
import asyncio
import inspect
import json
import logging
import time
from typing import Callable, TypeVar
from uuid import UUID

from pytest_inmanta.plugin import Project
from tornado.platform.asyncio import AnyThreadEventLoopPolicy

from inmanta.agent.handler import HandlerContext
from inmanta.const import Change, ResourceAction, ResourceState, VersionState
from inmanta.data import model
from inmanta.protocol.common import Result
from inmanta.protocol.endpoints import Client

LOGGER = logging.getLogger(__name__)


T = TypeVar("T")


def patch_policy():
    # work around for https://github.com/pytest-dev/pytest-asyncio/issues/168
    oldloop = asyncio.get_event_loop_policy()
    if not isinstance(oldloop, AnyThreadEventLoopPolicy):
        newloop = AnyThreadEventLoopPolicy()
        # transfer existing eventloop to the new policy
        newloop.set_event_loop(oldloop.get_event_loop())
        asyncio.set_event_loop_policy(newloop)


async def off_main_thread(func: Callable[[], T]) -> T:
    patch_policy()
    return await asyncio.get_event_loop().run_in_executor(None, func)


async def retry_limited(fun, timeout, *args, **kwargs):
    async def fun_wrapper():
        if inspect.iscoroutinefunction(fun):
            return await fun(*args, **kwargs)
        else:
            return fun(*args, **kwargs)

    start = time.time()
    while time.time() - start < timeout and not (await fun_wrapper()):
        await asyncio.sleep(1)
    if not (await fun_wrapper()):
        raise TimeoutError("Bounded wait failed")


async def deploy_model(
    project: Project,
    model: str,
    client: Client,
    environment: str,
    full_deploy: bool = False,
) -> VersionState:
    await compile_and_export(project, model)
    deployment_result = await deploy(project, client, environment, full_deploy)
    LOGGER.debug(json.dumps(deployment_result.result, indent=2))
    return deployment_result.result["model"]["result"]


async def compile_and_export(project: Project, model: str) -> HandlerContext:
    """
    Asynchronously compile and export a model
    ! Requires the server fixture in the test calling it
    """

    def compile() -> HandlerContext:
        return project.compile(model, export=True)

    # Compiling
    return await off_main_thread(compile)


async def get_version_or_fail(
    project: Project, client: Client, environment: UUID
) -> Result:
    result: Result = await client.get_version(environment, project.version)
    if result.code != 200:
        raise RuntimeError(
            f"Unexpected response code when getting version, received {result.code} "
            f"(expected 200): {json.dumps(result.result, indent=2)}"
        )

    return result


async def deploy(
    project: Project,
    client: Client,
    environment: UUID,
    full_deploy: bool = False,
    timeout: int = 120,
) -> Result:
    """
    Asynchronously deploy model and wait for its deployment to complete
    ! Requires the server fixture in the test calling it
    """
    result = await get_version_or_fail(project, client, environment)
    if result.result["model"]["total"] == 0:
        # Nothing to deploy
        LOGGER.warning(f"Nothing to deploy: {json.dumps(result.result, indent=2)}")
        return

    # Checking when did the last deployment finish
    last_deployment_date = sorted(
        [res["last_deploy"] or "" for res in result.result["resources"]]
    )[-1]
    LOGGER.info(f"Last deployment date: {last_deployment_date}")

    def deploy():
        project.deploy_latest_version(full_deploy=full_deploy)

    # Triggering deploy
    await off_main_thread(deploy)

    async def is_deployment_finished():
        result = await get_version_or_fail(project, client, environment)
        # Finished if all resources last deploy is after the last deployment registered
        # and no resource is in deploying state
        for res in result.result["resources"]:
            if (res["last_deploy"] or "") <= last_deployment_date or res[
                "status"
            ] == ResourceState.deploying:
                return False

        return True

    try:
        # Waiting for deployment to finish
        await retry_limited(is_deployment_finished, timeout=timeout)

        return await get_version_or_fail(project, client, environment)
    except TimeoutError as e:
        result = await get_version_or_fail(project, client, environment)

        LOGGER.warning(
            f"Timeout reached when waiting for resource to deploy: {json.dumps(result.result, indent=2)}"
        )
        raise e


def is_deployment(action: model.ResourceAction) -> bool:
    return (
        action.action == ResourceAction.deploy
        and action.status == ResourceState.deployed
    )


def is_deployment_with_change(action: model.ResourceAction) -> bool:
    return is_deployment(action) and action.change != Change.nochange
