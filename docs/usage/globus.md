# Globus Configuration for plex-pipe

PlexPipe allows you to process remote datasets locally.
The machine running this software pulls raw data from a Source (e.g. storage server) directly onto its own local drives using [Globus](https://www.globus.org/).

---

## Prerequisites

- **Globus Account**: Access via [app.globus.org](https://app.globus.org/).

- **Endpoints**: You need the UUIDs for two collections:

    - **Source**: Where the raw data lives (e.g. storage server).
    - **Destination**: The collection representing the machine where you are running PlexPipe.

- **Permissions**: Your Globus identity must have Read access to the Source and Write access to the Destination.

- **GCP for Personal Machines**: If you are running this on your own workstation, you must have [Globus Connect Personal](https://www.globus.org/globus-connect-personal) running.

- **Application ID (client_id)**: You must register a "Native App" at [developers.globus.org](https://developers.globus.org/). This client_id identifies your instance of plex-pipe to the Globus network.

---

## Configuration Registry

PlexPipe uses a Registry model to manage data locations. Instead of hardcoding IDs into the pipeline, you define your local workstation and all potential remote sources once in a centralized configuration file.

This configuration is stored in a YAML file. Throughout this documentation, we refer to this file as `globus_config.yaml`.

To get started, a skeleton file containing the required structure and placeholders is provided in the [examples folder](https://github.com/StallaertLab/plex-pipe/tree/main/examples) of the repository.

```yaml
gc:
  # Get this from developers.globus.org (looks like a UUID)
  client_id: "00000000-0000-0000-0000-000000000000"

  collections:
    remote_source:
      # Find this on the Globus Web App under 'Collection Search'
      id: "source-collection-uuid-here"
      root: "/path/to/remote/data"

    local_workstation:
      # Find this on the Globus Web App under 'Collection Search'
      # The UUID of your Globus Connect Personal endpoint
      id: "destination-collection-uuid-here"
      # Windows: null (for multi-drive) or specify the entry point, e.g. "C:/"
      # Linux: null (for Home) or specify the entry point, e.g. "/home/user/data"
      root: null
```

---

## Path Translation

PlexPipe automatically translates file paths between your local operating system and the Globus POSIX standard.
This allows you to define your `analysis_dir` and `image_dir` using the native format of the system where that folder resides in the [configuration file](../configuration/reference.md).

- **Local Folders**: Use your local system's pathway format (e.g., use Windows paths if running on a Windows workstation).

- **Remote Folders**: Use the remote system's native pathway format (e.g., use Linux/POSIX paths for sourcing from a remote cluster).

### The root Parameter

The `root` parameter in your Globus configuration defines the entry point (or "scope") for the file system:

- **Multi-Drive** (Windows only): Set `root: null`. This allows the use of standard Windows paths (e.g., `D:\Data`) which map to Globus virtual paths (e.g., `/D/Data`).

- **Home Directory** (Linux/Mac): Set `root: null`. This defaults the scope to your user home folder (~/).

- **Restricted/Rooted**: Set root: `/data/images`. Use this to "jail" the converter to a specific directory if Globus was configured with a restricted access point.

### Troubleshooting "Outside of Scope" Errors

If PlexPipe reports that a path is "outside of scope," it means the pathway you provided in your [configuration file](../configuration/reference.md) falls outside the area defined by your root parameter.

- If the `root` is incorrect: Update the `root` parameter in your `globus_config.yaml` to accurately reflect the access point of that collection.

- If Globus lacks permission: If your root is correct but the path is still inaccessible, you must update the Shared Directories (in Globus Connect Personal) or the Storage Gateway (in Globus Connect Server) to grant the endpoint physical access to those folders.

---

## Authentication (Tokens)

To allow PlexPipe to move data on your behalf, you must generate a set of authentication tokens. This links your Globus identity to the pipeline.

We recommend following the Native App authentication flow to obtain a Refresh Token. This allows long-running processing jobs to automatically renew their access without manual intervention.

- **Instructions**: Follow the Globus SDK [Native App Guide](https://globus-sdk-python.readthedocs.io/en/stable/examples/native_app.html) to register your application and run the authentication script.

- **Required Scopes**: Ensure your script requests the `TransferClient.scopes.all scope`.

- **What to Save**: From the script output, copy the `refresh_token` into your `globus_config.yaml`.


```yaml
transfer_tokens:
  refresh_token: "Agv100Yp9K7D8z2L_m5N6b3V4c1X9z0A_B2C3D4E5F6G" # replace with your actual refresh token
```

!!! warning Security Notice
    Your Refresh Token is a long-lived credential that grants full access to your Globus collections. Storing this token in your `globus_config.yaml` makes that file a sensitive secret.

    - Never commit this file to GitHub or share it publicly.

    - Always add `globus_config.yaml` to your `.gitignore`.

    - If you believe your tokens have been compromised, you can revoke them at any time via the [Globus Manage Consents](https://auth.globus.org/v2/web/consents) page.
