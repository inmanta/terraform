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
import datetime
import inspect
import json
import logging
import time
from typing import Callable, Optional, TypeVar
from uuid import UUID

from helpers.resource import Resource
from pytest_inmanta.plugin import Project
from tornado.platform.asyncio import AnyThreadEventLoopPolicy

from inmanta.agent.handler import HandlerContext
from inmanta.const import (
    TRANSIENT_STATES,
    UNDEPLOYABLE_STATES,
    Change,
    ResourceAction,
    ResourceState,
    VersionState,
)
from inmanta.data import model
from inmanta.protocol.common import Result
from inmanta.protocol.endpoints import Client
from inmanta.resources import Id

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
    while time.time() - start < timeout:
        if await fun_wrapper():
            return
        await asyncio.sleep(1)
    raise TimeoutError("Bounded wait failed")


async def get_param(
    environment: str, client: Client, param_id: str, resource_id: str
) -> Optional[str]:
    result = await client.get_param(
        tid=environment,
        id=param_id,
        resource_id=resource_id,
    )
    if result.code == 200:
        return result.result["parameter"]["value"]

    if result.code == 404:
        return None

    if result.code == 503:
        # In our specific case, we might get a 503 if the parameter is not set yet
        # https://github.com/inmanta/inmanta-core/blob/5bfe60683f7e21657794eaf222f43e4c53540bb5/src/inmanta/server/agentmanager.py#L799
        return None

    assert False, f"Unexpected response from server: {result.code}, {result.message}"


async def deploy_model(
    project: Project,
    model: str,
    client: Client,
    environment: str,
    full_deploy: bool = False,
    timeout: int = 15,
) -> VersionState:
    await compile_and_export(project, model)
    deployment_result = await deploy(project, client, environment, full_deploy, timeout)
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
    timeout: int = 15,
) -> Result:
    """
    Asynchronously deploy model and wait for its deployment to complete
    ! Requires the server fixture in the test calling it
    """
    result = await get_version_or_fail(project, client, environment)
    if result.result["model"]["total"] == 0:
        # Nothing to deploy
        LOGGER.warning(f"Nothing to deploy: {json.dumps(result.result, indent=2)}")
        return result

    # Checking when did the last deployment finish
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    LOGGER.info("Will start a new deployment now: %s", str(now))

    def deploy():
        project.deploy_latest_version(full_deploy=full_deploy)

    # Triggering deploy
    await off_main_thread(deploy)

    # Get all the resources that should be deployed and build a set containing
    # all the resources we should be waiting for
    result = await get_version_or_fail(project, client, environment)
    resources = {
        res["resource_id"]: Resource(id=Id.parse_id(res["resource_id"]))
        for res in result.result["resources"]
    }

    async def is_deployment_finished():
        result = await get_version_or_fail(project, client, environment)
        # Finished if all resources last deploy is after the last deployment registered
        # and no resource is in deploying state
        for res in result.result["resources"]:
            resource_id: str = res["resource_id"]

            if resource_id not in resources:
                # We don't care about this resource
                continue

            if res["status"] in TRANSIENT_STATES:
                # Something is still going on
                continue

            if res["status"] in UNDEPLOYABLE_STATES:
                # This resource will not get deployed
                # We can remove it from the watching set
                resources.pop(resource_id)
                continue

            # Get all the deployments done after the new deploy was made
            resource = resources[resource_id]
            last_deploy = await resource.get_last_action(
                client=client,
                environment=environment,
                action_filter=is_repair if full_deploy else is_deployment,
                after=now,
            )
            if last_deploy is None:
                # We don't have a deploy matching the filter
                continue

            # If we reach this state, the resource reached the state we care about
            # We can remove it from the watching set
            resources.pop(resource_id)

        return not resources

    try:
        # Waiting for deployment to finish
        await retry_limited(is_deployment_finished, timeout=timeout)

        return await get_version_or_fail(project, client, environment)
    except TimeoutError as e:
        result = await get_version_or_fail(project, client, environment)

        LOGGER.warning(
            "Timeout reached when waiting for resources to deploy: %s",
            json.dumps(result.result, indent=2),
        )
        raise e


def is_failed_deployment(action: model.ResourceAction) -> bool:
    return (
        action.action == ResourceAction.deploy and action.status == ResourceState.failed
    )


def is_repair(action: model.ResourceAction) -> bool:
    if not is_deployment(action):
        return False

    for message in action.messages:
        # The action is not a repair
        if message["msg"] == "Setting deployed due to known good status":
            return False

    return True


def is_deployment(action: model.ResourceAction) -> bool:
    return (
        action.action == ResourceAction.deploy
        and action.status == ResourceState.deployed
    )


def is_deployment_with_change(action: model.ResourceAction) -> bool:
    return is_deployment(action) and action.change != Change.nochange
