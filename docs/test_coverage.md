# Test coverage

We try to cover in the test cases of this module as much of the different features of terraform it interacts with, and under a variety of different conditions.  Given that all different situations are not as easy to reproduce with all providers, the tests are spread across different providers.  This document tries to summarize the different scenarios we are testing, and were the corresponding test can be found.

## Test scenarios

Here is a table of the different normal situations we want to test, and a link to the test case which asserts we handle this situation correctly.

| *Pre* | | | | | *Post* | | | *Test* |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Exists** | **State known** | **Terraform id provided** | **Resource purged** | | **Action** | **State** |  |  |
| | | | | | | | |
| Yes | Yes | Yes | No | | No change/Updated | Updated |  |
| Yes | Yes | Yes | Yes | | Purged | Deleted |  |
| Yes | Yes | No | No | | No change/Updated | Updated | [#1 No change](../tests/providers/local/test_local_file.py#L183) [#1 Update](../tests/providers/local/test_local_file.py#L197) |
| Yes | Yes | No | Yes | | Purged | Deleted | [#1 Delete](../tests/providers/local/test_local_file.py#L236) |
| Yes | No | Yes | No | | No change/Updated | Created |  |
| Yes | No | Yes | Yes | | Purged | Deleted |  |
| Yes | No | No | No | | Created | Created |  |
| Yes | No | No | Yes | | Purged | Deleted |  |
| No | Yes | Yes | No | | Created | Updated |  |
| No | Yes | Yes | Yes | | No change | Deleted |  |
| No | Yes | No | No | | Created | Updated | [#1 Repair](../tests/providers/local/test_local_file.py#L216) |
| No | Yes | No | Yes | | No change | Deleted |  |
| No | No | Yes | No | | Created | Created |  |
| No | No | Yes | Yes | | Purged | Deleted |  |
| No | No | No | No | | Created | Created | [#1 Create](../tests/providers/local/test_local_file.py#L166) |
| No | No | No | Yes | | No change | Deleted | [#1 No change](../tests/providers/local/test_local_file.py#L153) |

> In this table, the first four columns represent the current state, before doing any deployment with the orchestrator. 
>   - `Exists` (Yes/No) means whether the resource we want to see deployed is already deployed.
>   - `State known` (Yes/No) means whether the orchestrator has a state saved in parameters for this resource.
>   - `Terraform id provided` (Yes/No) means whether the resource attributes contain a value which can be used to find an existing resource without any state.
>   - `Resource purged` (Yes/No) means whether the resource is meant to be purged (in the desired state).
>
> The two next columns represent what we expect to see happening when using the terraform handler in the given situation.
>   - `Action` (No change/Updated/Created/Purged) The action that the Inmanta resource is supposed to do in the deployment.
>   - `State` (Updated/Created/Deleted) What should happen to the state stored in parameters in the orchestrator.

It might also be that the provider fails to do a deployment, because of permissions issues or simply internal failure.  In that was we also want to be sure we can recover as well as possible and that a single failure doesn't bring the model in a blocked state.  
Here is a list of such scenarios:
 1. Fail to read.  If the provider can not read a resource, its state should stay untouched.
 1. Fail to create.  If the provider can not create a resource, its state should be the current deployed resource, with doesn't match the current config then.
 1. Fail to update.  If the provider can not modify an existing resource, its state should stay the current deployed resource.
 1. Fail to delete.  If the provider can not delete an existing resource, its state shouldn't be deleted either.
At no point in time, a state stored in param should be null, a state always represents the latest information we managed to gather about the resource deployed.
