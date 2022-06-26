# Changelog

## 1.2.1 - 26/06/2022
- Fix issue with null states (#47)

## 1.2.0 - 20/06/2022
- Add support for model based config entity tree (for generated modules).

## 1.1.0 - 16/06/2022
- Decouple the terraform provider client sdk from the inmanta handler logic.

## 1.0.10 - 07/06/2022
- Remove double / from terraform registry URL

## 1.0.8 - 01/04/2022
- Add pytest-asyncio mode to remove deprecation warnings.

## 1.0.7 - 16/03/2022
- Use conditional requirement for inmanta-dev-dependencies package

## 1.0.5 - 19/01/2022
- Fine-grained test selection, based on the provider used (#20)

## 1.0.4 - 11/01/2022
- Fixed time-zone awareness issues in test cases (#17)

## 1.0.3 - 10/01/2022
- Renamed test lab config's environment variables (inmanta/infra-tickets#151)

## 1.0.2 - 03/01/2022

 - Added `INMANTA_TERRAFORM_LAB` environment variable to select testing lab.

## 1.0.1 - 10/12/2021

 - Fix bug where state was not saved if resource failed to create or update.  (#11)

## 1.0.0 - 09/12/2021

 - Add alias attribute on Provider entity.  This alias is included in the index.  (#8)

## 0.0.1 - 03/12/2021

 - Initial release
