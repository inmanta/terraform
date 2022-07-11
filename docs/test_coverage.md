# Test coverage

We try to cover in the test cases of this module as much of the different features of terraform it interacts with, and under a variety of different conditions.  Given that all different situations are not as easy to reproduce with all providers, the tests are spread across different providers.  This document tries to summarize the different scenarios we are testing, and were the corresponding test can be found.

## Test scenarios

| *Pre* | | | | | *Post* | | |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Exists** | **State known** | **Terraform id provided** | **Resource purged** | | **Action** | **State** | **Test** |
| | | | | | | | |
| Yes | Yes | Yes | No | | No change/Updated | Updated | ... |
| Yes | Yes | Yes | Yes | | Purged | Deleted | ... |
| Yes | Yes | No | No | | No change/Updated | Updated | ... |
| Yes | Yes | No | Yes | | Purged | Deleted | ... |
| Yes | No | Yes | No | | No change/Updated | Created | ... |
| Yes | No | Yes | Yes | | Purged | Deleted | ... |
| Yes | No | No | No | | Created | Created | ... |
| Yes | No | No | Yes | | Purged | Deleted | ... |
| No | Yes | Yes | No | | Created | Updated | ... |
| No | Yes | Yes | Yes | | No change | Deleted | ... |
| No | Yes | No | No | | Created | Updated | ... |
| No | Yes | No | Yes | | No change | Deleted | ... |
| No | No | Yes | No | | Created | Created | ... |
| No | No | Yes | Yes | | Purged | Deleted | .. |
| No | No | No | No | | Created | Created | ... |
| No | No | No | Yes | | No change | Deleted | ... |
