# Changelog

## v1.3.15 - ?


## v1.3.14 - 2024-01-03


## v1.3.13 - 2023-10-12


## v1.3.12 - 2023-06-30


## v1.3.11 - 2023-04-04


## v1.3.10 - 2023-03-03


## v1.3.7 - 07/12/2022
- Fix asyncio tests for python 3.6 (#549)

## v1.3.5 - 07/11/2022
- Minor test case improvement

## v1.3.4 - 27/10/2022
- Minor test case improvement

## v1.3.3 - 26/10/2022
- Minor test case improvement

## v1.3.2 - 24/10/2022
- Add timeouts on external http requests.
- Use native python warnings.

## v1.3.1 - 06/10/2022
- Add py.typed file in module's plugins.

## v1.3.0 - 28/09/2022
- Attach state to config blocks automatically.
- Fix repair issue when resource has been deleted (introduced in 1.2.1)

## v1.2.4 - 30/08/2022
- Exclude grpcio-tools==1.49.0rc1.

## v1.2.3 - 30/08/2022
- Exclude grpcio==1.49.0rc1.

## v1.2.2 - 02/08/2022
- Various dependency updates.

## v1.2.1 - 30/06/2022
- Fix issue with null states (#47)

## v1.2.0 - 20/06/2022
- Add support for model based config entity tree (for generated modules).

## v1.1.0 - 16/06/2022
- Decouple the terraform provider client sdk from the inmanta handler logic.

## v1.0.10 - 07/06/2022
- Remove double / from terraform registry URL

## v1.0.8 - 01/04/2022
- Add pytest-asyncio mode to remove deprecation warnings.

## v1.0.7 - 16/03/2022
- Use conditional requirement for inmanta-dev-dependencies package

## v1.0.5 - 19/01/2022
- Fine-grained test selection, based on the provider used (#20)

## v1.0.4 - 11/01/2022
- Fixed time-zone awareness issues in test cases (#17)

## v1.0.3 - 10/01/2022
- Renamed test lab config's environment variables (inmanta/infra-tickets#151)

## v1.0.2 - 03/01/2022

 - Added `INMANTA_TERRAFORM_LAB` environment variable to select testing lab.

## v1.0.1 - 10/12/2021

 - Fix bug where state was not saved if resource failed to create or update.  (#11)

## v1.0.0 - 09/12/2021

 - Add alias attribute on Provider entity.  This alias is included in the index.  (#8)

## v0.0.1 - 03/12/2021

 - Initial release
