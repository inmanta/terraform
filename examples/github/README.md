# integrations/github
> This has been tested for version 4.9.2

In this document you can find the following example:
 - [Repository](#repository)

To use those code snippet, you will need to set the following environment variable:
 - `GITHUB_TOKEN`: A github api token, with repository read/update/delete permissions.

# Repository
```
provider = terraform::Provider(
    namespace="integrations",
    type="github",
    version="4.9.2",
    config={
        "owner": "inmanta-test",
        "token": std::get_env("GITHUB_TOKEN"),
    },
)

repo = terraform::Resource(
    type="github_repository",
    name="my repo",
    terraform_id=null,
    config={
        "name": "test-repository",
        "description": "my original description",
        "visibility": "public",
        "template": [
            {
                "owner": "fergusmacd",
                "repository": "template-repo-terraform"
            }
        ]
    },
    purged=false,
    provider=provider,
)
```
