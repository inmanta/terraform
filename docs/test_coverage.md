# Test coverage

We try to cover in the test cases of this module as much of the different features of terraform it interacts with, and under a variety of different conditions.  Given that all different situations are not as easy to reproduce with all providers, the tests are spread across different providers.  This document tries to summarize the different scenarios we are testing, and were the corresponding test can be found.

## Test scenarios

Here is a table of the different situations we want to test, and a link to the test case which asserts we handle this situation correctly.

| *Pre* | | | | | *Post* | | | *Test* |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Exists** | **State known** | **Terraform id provided** | **Resource purged** | | **Action** | **State** |  |  |
| | | | | | | | |
| Yes | Yes | Yes | No | | No change/Updated | Updated | |
| Yes | Yes | Yes | Yes | | Purged | Deleted |  |
| Yes | Yes | No | No | | No change/Updated | Updated |  |
| Yes | Yes | No | Yes | | Purged | Deleted |  |
| Yes | No | Yes | No | | No change/Updated | Created |  |
| Yes | No | Yes | Yes | | Purged | Deleted |  |
| Yes | No | No | No | | Created | Created |  |
| Yes | No | No | Yes | | Purged | Deleted |  |
| No | Yes | Yes | No | | Created | Updated |  |
| No | Yes | Yes | Yes | | No change | Deleted |  |
| No | Yes | No | No | | Created | Updated |  |
| No | Yes | No | Yes | | No change | Deleted |  |
| No | No | Yes | No | | Created | Created |  |
| No | No | Yes | Yes | | Purged | Deleted |  |
| No | No | No | No | | Created | Created |  |
| No | No | No | Yes | | No change | Deleted |  |

> In this table, the first four columns represent the current state, before doing any deployment with the orchestrator. 
>   - `Exists` (Yes/No) means whether the resource we want to see deployed is already deployed.
>   - `State known` (Yes/No) means whether the orchestrator has a state saved in parameters for this resource.
>   - `Terraform id provided` (Yes/No) means whether the resource attributes contain a value which can be used to find an existing resource without any state.
>   - `Resource purged` (Yes/No) means whether the resource is meant to be purged (in the desired state).
>
> The two next columns represent what we expect to see happening when using the terraform handler in the given situation.
>   - `Action` (No change/Updated/Created/Purged) The action that the Inmanta resource is supposed to do in the deployment.
>   - `State` (Updated/Created/Deleted) What should happen to the state stored in parameters in the orchestrator.
