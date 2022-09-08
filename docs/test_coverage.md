# Test coverage

We try to cover in the test cases of this module as much of the different features of terraform it interacts with, and under a variety of different conditions.  Given that all different situations are not as easy to reproduce with all providers, the tests are spread across different providers.  This document tries to summarize the different scenarios we are testing, and were the corresponding test can be found.

## Test scenarios

Here is a table of the different normal situations we want to test, and a link to the test case which asserts we handle this situation correctly.

| *Pre* | | | | | *Post* | | | *Test* |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Exists** | **State known** | **Terraform id provided** | **Resource purged** | | **Action** | **State** |  |  |
| | | | | | | | |
| Yes | Yes | Yes | No | | No change/Updated | Updated | | [#2 No change (1)](../tests/providers/docker/test_docker_network.py#L38) |
| Yes | Yes | Yes | Yes | | Purged | Deleted | | [#2 Delete (1)](../tests/providers/docker/test_docker_network.py#L38) |
| Yes | Yes | No | No | | No change/Updated | Updated | | [#1 No change (2)](../tests/providers/local/test_local_file.py#L115) [#1 Update](../tests/providers/local/test_local_file.py#L115) |
| Yes | Yes | No | Yes | | Purged | Deleted | | [#1 Delete](../tests/providers/local/test_local_file.py#L115) |
| Yes | No | Yes | No | | No change/Updated | Created | | [#2 Import (1)](../tests/providers/docker/test_docker_network.py#L38) |
| Yes | No | Yes | Yes | | Purged | Deleted | | [#2 Delete (1)](../tests/providers/docker/test_docker_network.py#L38) |
| Yes | No | No | No | | Created | Created | | [#1 Re-create](../tests/providers/local/test_local_file.py#L115) |
| Yes | No | No | Yes | | No change | Deleted | | [#1 No change (4)](../tests/providers/local/test_local_file.py#L115) |
| No | Yes | Yes | No | | Created | Updated | | [#3 Repair (1)](../tests/providers/docker/test_docker_network.py#L178) |
| No | Yes | Yes | Yes | | No change | Deleted | | [#3 No change (1)](../tests/providers/docker/test_docker_network.py#L178) |
| No | Yes | No | No | | Created | Updated | | [#1 Repair](../tests/providers/local/test_local_file.py#L115) |
| No | Yes | No | Yes | | No change | Deleted | | [#1 No change (3)](../tests/providers/local/test_local_file.py#L115) |
| No | No | Yes | No | | Created | Created | | [#3 Repair (2)](../tests/providers/docker/test_docker_network.py#L178) |
| No | No | Yes | Yes | | Purged | Deleted | | [#3 No change (2)](../tests/providers/docker/test_docker_network.py#L178) |
| No | No | No | No | | Created | Created | | [#1 Create](../tests/providers/local/test_local_file.py#L115) |
| No | No | No | Yes | | No change | Deleted | | [#1 No change (1)](../tests/providers/local/test_local_file.py#L115) |

> In this table, the first four columns represent the current state, before doing any deployment with the orchestrator. 
>   - `Exists` (Yes/No) means whether the resource we want to see deployed is already deployed.
>   - `State known` (Yes/No) means whether the orchestrator has a state saved in parameters for this resource.
>   - `Terraform id provided` (Yes/No) means whether the resource attributes contain a value which can be used to find an existing resource without any state.
>   - `Resource purged` (Yes/No) means whether the resource is meant to be purged (in the desired state).
>
> The two next columns represent what we expect to see happening when using the terraform handler in the given situation.
>   - `Action` (No change/Updated/Created/Purged) The action that the Inmanta resource is supposed to do in the deployment.  Or *Failed* if the deployment should not succeed.
>   - `State` (Updated/Created/Deleted) What should happen to the state stored in parameters in the orchestrator.

It might also be that the provider fails to do a deployment, because of permissions issues or simply internal failure.  In that was we also want to be sure we can recover as well as possible and that a single failure doesn't bring the model in a blocked state.  
Here is a list of such scenarios:
 1. Fail to read.  If the provider can not read a resource, its state should stay untouched.  See [local file](../tests/providers/local/test_local_file.py#L308)
 1. Fail to create.  If the provider can not create a resource, its state should be the current deployed resource, with doesn't match the current config then.  See [local file](../tests/providers/local/test_local_file.py#L308)
 1. Fail to update.  If the provider can not modify an existing resource, its state should stay the current deployed resource.  (TODO) *Not covered by test suite, we need to find a provider with which we can lock the resource (externally) to make it readable but not modifiable.*
 1. Fail to delete.  If the provider can not delete an existing resource, its state shouldn't be deleted either.  (TODO) *Not covered by test suite, we need to find a provider with which we can lock the resource (externally) to make it readable but not deletable.*
 1. Fail to import.  If the provided id doesn't correspond to anything that exists.  See [docker non-existing network import](../tests/providers/docker/test_docker_network.py#L178)
 1. Forbidden to import.  If the resource can not be imported using an id.  See [docker image import](../tests/providers/docker/test_docker_image.py#L170)
