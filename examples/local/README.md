# hashicorp/local
> This has been tested for version 2.1.0

In this document you can find the following example:
 - [File](#file)

```
provider = terraform::Provider(
    namespace="hashicorp",
    type="local",
    version="2.1.0",
    config={},
)

file = terraform::Resource(
    type="local_file",
    name="my file",
    terraform_id=null,
    config={
        "filename": "/tmp/test-file.txt",
        "content": "my original content"
    },
    purged=false,
    provider=provider,
)
```
