import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import globus_sdk
import yaml
from globus_sdk import GlobusAPIError


class GlobusEndpoint:
    """A single Globus Collection and its associated path logic."""

    def __init__(self, collection_id: str, root: str | None = None) -> None:
        """Initializes the GlobusEndpoint.

        Args:
            collection_id: The Globus collection ID.
            root: The root path for the collection. Defaults to None.
        """

        self.collection_id = collection_id

        if root is None:
            if os.name == "nt":
                self.shared_root = None
            else:
                self.shared_root = Path.home().resolve()
        else:
            self.shared_root = Path(root).resolve()

    def check_path_within_scope(self, path: Path) -> None:
        """Checks if a path is within the configured scope.

        Args:
            path: The path to check.

        Raises:
            ValueError: If the path is outside the scope or lacks a drive letter when required.
        """
        resolved = path.resolve()
        if self.shared_root is not None:
            if not resolved.is_relative_to(self.shared_root):
                raise ValueError(
                    f"Path {resolved} is outside Globus scope {self.shared_root}"
                )
        elif self.shared_root is None and not resolved.drive:
            raise ValueError(
                f"Path {resolved} requires a drive letter for multi_drive."
            )

    def local_to_globus(self, local_path: str | Path) -> str:
        """Converts a local path to a Globus path.

        Args:
            local_path: The local path to convert.

        Returns:
            The corresponding Globus path.
        """
        p = Path(local_path).resolve()
        self.check_path_within_scope(p)

        if os.name == "nt" or p.drive:
            wp = PureWindowsPath(p)
            if self.shared_root is None:
                drive = wp.drive.replace(":", "").upper()
                return str(PurePosixPath("/") / drive / Path(*wp.parts[1:]).as_posix())
            else:
                rel_path = p.relative_to(self.shared_root)
                return str(PurePosixPath("/") / rel_path.as_posix())

        # Linux/Mac Logic
        if self.shared_root is not None:
            return str(PurePosixPath("/") / p.relative_to(self.shared_root).as_posix())

        return p.as_posix()

    def globus_to_local(self, globus_path: str) -> Path:
        """Converts a Globus path to a local path.

        Args:
            globus_path: The Globus path to convert.

        Returns:
            The corresponding local path.
        """
        gp = PurePosixPath(globus_path)
        if os.name == "nt" or (self.shared_root and self.shared_root.drive):
            if self.shared_root is None:
                drive = f"{gp.parts[1]}:\\"
                return Path(drive) / Path(*gp.parts[2:])
            return self.shared_root / Path(*gp.parts[1:])

        if self.shared_root is not None:
            return self.shared_root / Path(*gp.parts[1:])

        return Path(gp)


class GlobusConfig:
    """Master configuration loaded from a registry-style YAML."""

    def __init__(
        self, config_dict: dict[str, Any], source_key: str, dest_key: str
    ) -> None:
        """Initializes the GlobusConfig.

        Args:
            config_dict: The configuration dictionary.
            source_key: Key for the source collection.
            dest_key: Key for the destination collection.

        Raises:
            KeyError: If a collection key is missing in the configuration.
        """
        self.client_id = config_dict["gc"]["client_id"]
        self.transfer_tokens = config_dict.get("transfer_tokens", {})

        collections = config_dict["gc"]["collections"]

        # Validation: Ensure nicknames exist
        for key in [source_key, dest_key]:
            if key not in collections:
                raise KeyError(
                    f"Collection '{key}' not found in configuration registry."
                )

        self.source = GlobusEndpoint(
            collections[source_key]["id"], collections[source_key].get("root")
        )
        self.destination = GlobusEndpoint(
            collections[dest_key]["id"], collections[dest_key].get("root")
        )

    @classmethod
    def from_yaml(
        cls, yaml_path: str | Path, source_key: str, dest_key: str
    ) -> "GlobusConfig":
        """Loads configuration from a YAML file.

        Args:
            yaml_path: Path to the YAML configuration file.
            source_key: Key for the source collection.
            dest_key: Key for the destination collection.

        Returns:
            An instance of GlobusConfig.
        """
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return cls(data, source_key, dest_key)


def create_globus_tc(
    client_id: str, transfer_tokens: dict[str, Any]
) -> globus_sdk.TransferClient:
    """Creates a TransferClient object using the Globus SDK.

    Args:
        client_id: The Globus client ID.
        transfer_tokens: A dictionary containing transfer tokens.

    Returns:
        An authenticated TransferClient.
    """

    auth_client = globus_sdk.NativeAppAuthClient(client_id)

    transfer_rt = transfer_tokens["refresh_token"]

    # construct a RefreshTokenAuthorizer
    # note that `client` is passed to it, to allow it to do the refreshes
    authorizer = globus_sdk.RefreshTokenAuthorizer(
        transfer_rt,
        auth_client,
    )

    # create TransferClient
    tc = globus_sdk.TransferClient(authorizer=authorizer)

    return tc


def globus_dir_exists(
    tc: globus_sdk.TransferClient, endpoint_id: str, path: str
) -> bool:
    """Checks if a directory exists on a Globus endpoint.

    Args:
        tc: The Globus TransferClient.
        endpoint_id: The ID of the endpoint.
        path: The path to check.

    Returns:
        True if the directory exists, False otherwise.
    """
    try:
        tc.operation_ls(endpoint_id, path=path)
        return True
    except GlobusAPIError as e:
        if e.code == "ClientError.NotFound":
            return False
        raise  # some other error, bubble it up


def list_globus_tifs(gc: GlobusConfig, path: str) -> list[str]:
    """Lists ``*.tif*`` files from a Globus endpoint.

    Args:
        gc: Globus configuration object.
        path: Remote directory to list.

    Returns:
        A list of paths to files on the remote endpoint.
    """

    tc = create_globus_tc(gc.client_id, gc.transfer_tokens)
    listing = tc.operation_ls(gc.source.collection_id, path=str(path))

    files = []
    for entry in listing:
        name = entry["name"]
        if name.endswith((".tif", ".tiff")):
            files.append(str(PurePosixPath(path) / name))

    return files
