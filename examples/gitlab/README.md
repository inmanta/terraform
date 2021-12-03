# gitlabhq/gitlab
> This has been tested for version 3.6.0

In this document you can find the following example:
 - [Project](#project)

To use those code snippet, you will need to set the following environment variable:
 - `GITLAB_TOKEN`: A gitlab access token, with project create/update/delete permissions.

# Project
```
provider = terraform::Provider(
    namespace="gitlabhq",
    type="gitlab",
    version="3.6.0",
    config={
        "base_url": "https://code.inmanta.com/api/v4",
        "token": std::get_env("GITLAB_TOKEN"),
    },
)

project = terraform::Resource(
    type="gitlab_project",
    name="my project",
    config={
        "name": "example",
        "description": "my original description",
        "namespace_id": 117
    },
    purged=false,
    provider=provider,
)
```
