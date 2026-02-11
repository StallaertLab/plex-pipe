import re

import anndata as ad
import numpy as np
import pandas as pd
import spatialdata as sd
from loguru import logger
from skimage.measure import regionprops_table
from spatialdata.models import TableModel

from plex_pipe.object_quantification.metrics import METRIC_REGISTRY
from plex_pipe.object_quantification.qc_shape_masker import QcShapeMasker
from plex_pipe.utils.config_schema import (
    DEFAULT_intensity_properties,
    DEFAULT_morphological_properties,
)


class QuantificationController:
    """Orchestrates quantification of data within a SpatialData object.

    This class is designed as a stateless service object. It holds configuration
    for a quantification task (e.g., which channels and masks to use) and
    provides a `run` method to execute it. The `SpatialData` object is passed
    directly to the `run` method, ensuring that the controller remains
    stateless.

    Attributes:
        mask_keys: Maps a mask suffix to its `sdata.labels` key. e.g. {'cell': 'cell_mask', 'nuc': 'nucleus_mask'}
            Assumes that labels of objects correspond between the masks,
            e.g. if a single cell has the nucleus and the cytoplasm mask
            their labels should be the same.
        table_name: Name for the output AnnData table within the SpatialData object.
        mask_to_annotate: If provided, the label key to which the resulting
            table should be connected.
        channels: A list of image channel keys to quantify. If None, all images
            in the SpatialData object are quantified.
        add_qc_masks: If True, runs quality control masking after quantification.
        qc_prefix: Prefix for the quality control exclusion columns.
        overwrite: If True, allows overwriting an existing table of the same name.
    """

    def __init__(
        self,
        mask_keys: dict[str, str],
        table_name: str = "quantification",
        mask_to_annotate: str | None = None,
        markers_to_quantify: list[str] | None = None,
        add_qc_masks=False,
        qc_prefix: str | None = "qc_exclude",
        overwrite: bool = False,
        morphological_properties: list[str] | None = None,
        intensity_properties: list[str] | None = None,
    ) -> None:

        # this requirement is independent of specific sdata instance
        if (mask_to_annotate) and (mask_to_annotate not in mask_keys.values()):
            raise ValueError(
                f"mask_to_annotate '{mask_to_annotate}' must be one of the masks to quantify: {list(mask_keys.keys())}"
            )

        self.mask_keys = mask_keys.copy()
        self.mask_to_annotate = mask_to_annotate
        self.channels = markers_to_quantify
        self.table_name = table_name
        self.add_qc_masks = add_qc_masks
        self.qc_prefix = qc_prefix
        self.overwrite = overwrite
        self.morphological_properties = (
            morphological_properties or DEFAULT_morphological_properties
        )
        self.intensity_properties = intensity_properties or DEFAULT_intensity_properties

        if "label" not in self.morphological_properties:
            raise ValueError(
                "The 'morphological_properties' list must contain 'label'."
            )

        # Validate intensity metrics
        for m in self.intensity_properties:
            if m not in METRIC_REGISTRY:
                raise ValueError(
                    f"Unknown intensity metric: '{m}'. Available: {list(METRIC_REGISTRY.keys())}"
                )

    ############################################################################
    # Validate inputs
    ############################################################################

    def validate_sdata_as_input(self, sdata: sd.SpatialData) -> None:
        """Validates that required masks and channels exist in the SpatialData object.

        Args:
            sdata: The SpatialData object being processed.

        Raises:
            ValueError: If a specified mask or channel key is not found in `sdata`.
        """

        # validate masks to quantify are present
        for mask in self.mask_keys.values():
            if mask not in sdata.labels:
                message = f"Mask '{mask}' not found in sdata. Masks present: {list(sdata.labels)}"
                logger.error(message)
                raise ValueError(message)

        # validate channels to quantify are present
        if self.channels:
            for ch in self.channels:
                if ch not in sdata:
                    message = f"Channel '{ch}' not found in sdata. Channels present: {list(sdata.images)}"
                    logger.error(message)
                    raise ValueError(message)
            logger.info(
                f"Quantifying {len(self.channels)} user-specified channels: {self.channels}."
            )
        else:
            self.channels = list(sdata.images)
            logger.info(
                f"Channels not specified. Quantifying all ({len(self.channels)}) existing channels: {self.channels}."
            )

    def prepare_to_overwrite(self, sdata: sd.SpatialData) -> None:
        """Deletes an existing table from the SpatialData object if overwrite is enabled.

        Args:
            sdata: The SpatialData object being processed.

        Raises:
            ValueError: If the table already exists and ``self.overwrite`` is False.
        """

        if self.table_name in sdata:
            if not self.overwrite:
                message = f"Table '{self.table_name}' already exists in sdata. Please provide a unique table name."
                logger.error(message)
                raise ValueError(message)
            else:
                logger.warning(
                    f"Table '{self.table_name}' already exists and will be overwritten."
                )
                del sdata[self.table_name]
                sdata.delete_element_from_disk(self.table_name)
                logger.info(f"Existing table '{self.table_name}' deleted from sdata.")

    ############################################################################

    def get_mask(self, sdata: sd.SpatialData, mask_key: str) -> np.ndarray:
        """Retrieves a single label mask from a SpatialData object.

        Args:
            sdata: The SpatialData object being processed.
            mask_key: The key identifying the labels layer in the SpatialData object.

        Returns:
            The label mask as a NumPy array.
        """
        mask = np.array(sd.get_pyramid_levels(sdata[mask_key], n=0)).squeeze()
        return mask

    def get_masks_dictionary(self, sdata: sd.SpatialData) -> dict[str, np.ndarray]:
        """Creates and returns a dictionary of label masks from a SpatialData object.

        Args:
            sdata: The SpatialData object being processed.

        Returns:
            A dictionary where keys are the mask suffixes (e.g., 'cell') and
            values are the corresponding label masks as NumPy arrays.
        """
        return {
            suffix: self.get_mask(sdata, mask_key)
            for suffix, mask_key in self.mask_keys.items()
        }

    ############################################################################
    # Compute obs and obsm
    ############################################################################

    def build_obs(self, masks: dict[str, np.ndarray]) -> pd.DataFrame:
        """Calculates morphological properties for objects in each loaded mask.

        This method computes morphological features and centroid for every
        labeled object found in the masks. Column names for the calculated
        properties are suffixed with the corresponding mask key. For example,
        the 'area' column for a mask with key 'cell' becomes 'area_cell'.

        Args:
            masks: A dictionary where keys are the mask suffixes (e.g., 'cell') and
            values are the corresponding label masks as NumPy arrays.

        Returns:
            A pandas DataFrame where rows represent objects and columns represent
            the calculated morphological features with descriptive names.
        """

        morph_dfs = []
        for mask_suffix, mask in masks.items():
            logger.info(f"Quantifying morphology features for mask '{mask_suffix}'")
            morph_props = regionprops_table(
                mask,
                properties=self.morphological_properties,
            )
            morph_df = pd.DataFrame(morph_props)
            morph_df = morph_df.rename(
                columns={
                    c: f"{c}_{mask_suffix}" for c in morph_df.columns if c != "label"
                }
            )
            morph_df = morph_df.set_index("label", drop=True)
            morph_dfs.append(morph_df)

        # create obs object
        obs = pd.concat(morph_dfs, axis=1, join="outer")
        obs.index.name = "label_int"
        # keep label id as column
        obs.insert(0, "label", obs.index)

        return obs

    def find_ndims_columns(self, names: list[str]) -> dict[str, list[tuple[int, str]]]:
        """Identifies and groups columns representing multi-dimensional data.

        This function uses a regex to find column names that follow a specific
        pattern (e.g., 'property-dimension_index') and groups them by property.
        It validates that dimension indices are unique for each property.

        Args:
            names: A list of column names to search through.

        Returns:
            A dictionary where keys are base property names (e.g., 'centroid')
            and values are lists of (dimension_index, column_name) tuples.

        Raises:
            ValueError: If duplicate dimension indices are found for a property.
        """
        _ndims_regex = re.compile(
            r"^(?P<base>[^-]+)-(?P<dim>\d+)(?P<suffix>.*)?$"
        )  # first '-' is expected to precede dimension number

        ndims_buckets = {}  # (property:str) -> List[tuple[dim:int, col:str]]
        for col in names:
            m = _ndims_regex.match(col)
            if m:
                prop = "".join([m.group("base"), m.group("suffix")])
                dim = int(m.group("dim"))
                ndims_buckets.setdefault(prop, []).append((dim, col))

        for prop, dim_cols in ndims_buckets.items():
            # --- Check uniqueness of dimension indices ---
            dims = [d for d, _ in dim_cols]
            dup_dims = [d for d in set(dims) if dims.count(d) > 1]
            if dup_dims:
                raise ValueError(
                    f"Duplicate dimension indices found for '{prop}': {dup_dims}. "
                    "Each dimension (e.g., -0, -1, ...) must be unique."
                )
            if len(dims) <= 1:
                # remove from ndims_buckets
                logger.warning(
                    f"Property '{prop}' has only a single dimension. Skipping addition to obsm."
                )
                ndims_buckets[prop] = []

        return ndims_buckets

    def build_obsm(
        self, obs: pd.DataFrame, ndims_buckets: dict[str, list[tuple[int, str]]]
    ) -> tuple[dict[str, np.ndarray], list[str]]:
        """Builds multi-dimensional annotation dictionary (`obsm`) from obs columns.

        This method identifies columns in the observation DataFrame (`obs`) that
        represent different dimensions of a single property (e.g., 'centroid-0',
        'centroid-1'). It then stacks these columns into a single NumPy array
        for each property and stores them in a dictionary, suitable for assignment
        to an AnnData `obsm` attribute.

        Args:
            obs: The observation DataFrame containing morphological properties.
            ndims_buckets: A dictionary mapping property names to lists of their
                corresponding dimensional column names.

        Returns:
            A tuple containing:
                - obsm: A dictionary where keys are property names and values are
                  NumPy arrays of the stacked dimensional data.
                - cols_to_drop: A list of column names from `obs` that have been
                  consolidated into `obsm`.
        """
        obsm = {}
        cols_to_drop = []
        for prop, dim_cols in ndims_buckets.items():

            # Sort by dimension index
            dim_cols_sorted = sorted(dim_cols, key=lambda t: t[0])
            dims_sorted, cols_sorted = (
                zip(*dim_cols_sorted, strict=False) if dim_cols_sorted else ([], [])
            )

            # Build array
            arr = np.column_stack([obs[c].to_numpy() for c in cols_sorted])
            obsm[prop] = arr
            cols_to_drop.extend(cols_sorted)

        return obsm, cols_to_drop

    ############################################################################
    # Compute X and var
    ############################################################################

    def get_channel(self, sdata: sd.SpatialData, channel_key: str) -> np.ndarray:
        """Extracts a 2D image array for a single channel from a SpatialData object.

        This method retrieves the highest resolution level of the specified channel,
        squeezes it to remove singleton dimensions, and returns it as a NumPy array.
        If the resulting image has three dimensions, a warning is logged
        and the mean is computed across the leading axis to produce a 2D array.
        4D images are not supported.

        Args:
            sdata: The SpatialData object containing the image data.
            channel_key: The key identifying the channel to retrieve.

        Returns:
            A 2D NumPy array representing the channel's image data.

        Raises:
            ValueError: If the channel has 4 dimensions.
        """

        img = np.array(sd.get_pyramid_levels(sdata[channel_key], n=0)).squeeze()

        if img.ndim == 2:
            logger.info(f"Channel '{channel_key}' is 2D.")
        elif img.ndim == 3:
            # warning if more than 2D will take the mean across channels
            logger.warning(
                f"Channel '{channel_key}' has 3 dimensions. Taking mean across channels or slices."
            )
            img = np.mean(img, axis=0)
        else:
            msg = f"Channel '{channel_key}' has {img.ndim} dimensions, which is not supported."
            logger.error(msg)
            raise ValueError(msg)

        return img

    def build_signal_df(self, sdata: sd.SpatialData, masks: dict[str, np.ndarray]):
        """Quantifies channel intensities for each object across all specified masks.

        This method calculates the mean and median intensity for every object defined
        in the label masks. It iterates through each channel in `self.channels` and
        each mask in the `masks` dictionary. The results are compiled into a
        single DataFrame, which serves as the basis for the `X` matrix and `var`
        annotations in the final AnnData table.

        Args:
            masks: A dictionary where keys are mask suffixes (e.g., 'cell') and
                values are the corresponding label masks as NumPy arrays.

        Returns:
            A pandas DataFrame where each row corresponds to an object label and
            each column represents a specific intensity measurement (e.g.,
            'channel_mean_intensity_mask').
        """

        quant_dfs = []

        # Prepare properties for regionprops
        props = ["label"]
        extra_props = []
        rename_map = {}  # Maps regionprops output name -> user friendly name

        for m_name in self.intensity_properties:
            metric = METRIC_REGISTRY[m_name]
            if metric.is_extra:
                extra_props.append(metric.func)
            else:
                props.append(metric.func)

            rename_map[metric.regionprops_name] = metric.name

        for channel_key in self.channels:
            img = self.get_channel(sdata, channel_key)
            for mask_suffix, mask in masks.items():
                logger.info(
                    f"Quantifying channel '{channel_key}' with mask '{mask_suffix}'"
                )
                props = regionprops_table(
                    mask,
                    intensity_image=img,
                    properties=props,
                    extra_properties=extra_props,
                )
                df = pd.DataFrame(props)
                df = df.rename(
                    columns={
                        c: f"{channel_key}_{rename_map[c]}_{mask_suffix}"
                        for c in df.columns
                        if c != "label"
                    }
                )
                df = df.set_index("label", drop=True)
                quant_dfs.append(df)

        # create quant_df
        quant_df = pd.concat(quant_dfs, axis=1, join="outer")
        quant_df.index.name = "label_int"
        quant_df.insert(0, "label", quant_df.index)

        return quant_df

    ############################################################################
    # Build adata tabel
    ############################################################################

    def build_adata(self, sdata: sd.SpatialData) -> ad.AnnData:
        """Builds a complete AnnData object from a SpatialData object.

        This method orchestrates the quantification process by calling helper
        methods to compute morphological properties, restructure multi-dimensional
        columns, and calculate signal intensities. It assembles these components
        into a single AnnData object.

        Args:
            sdata: The SpatialData object to process.

        Returns:
            An AnnData object containing the quantified data (X), with observations
            (obs), variables (var), and multi-dimensional annotations (obsm).
        """

        # create mask dictionary
        masks = self.get_masks_dictionary(sdata=sdata)

        ########################################################################
        # Compute obs and obsm
        ########################################################################

        # create obs
        obs = self.build_obs(masks=masks)

        # if matching pairs present, create obsm
        ndims_buckets = self.find_ndims_columns(list(obs.columns))
        if ndims_buckets:
            logger.info(
                f"Found {len(ndims_buckets)} columns with multiple dimensions: {list(ndims_buckets.keys())}. Creating obsm table."
            )
            obsm, cols_to_drop = self.build_obsm(obs, ndims_buckets)
            obs = obs.drop(columns=cols_to_drop)
        else:
            logger.info("No multi-dimensional columns found.")
            obsm = None

        ########################################################################
        # Compute X and var
        ########################################################################

        quant_df = self.build_signal_df(sdata, masks)

        # re-index to match obs
        quant_df = quant_df.reindex(obs.index)

        X = quant_df.to_numpy()
        var = pd.DataFrame(index=quant_df.columns)

        ########################################################################
        # Create AnnData object
        ########################################################################

        # create AnnData object
        adata = ad.AnnData(X=X, obs=obs, var=var, obsm=obsm)

        return adata

    def connect_adata_to_mask(
        self, sdata: sd.SpatialData, adata: ad.AnnData
    ) -> sd.SpatialData:
        """Connects the AnnData table to a mask (mask_to_annotate) within the  SpatialData object.

        Args:
            sdata: The SpatialData object.
            adata: The AnnData table to connect.

        Returns:
            The updated SpatialData object.
        """
        if self.mask_to_annotate:
            adata.obs["region"] = self.mask_to_annotate
            adata.obs["cell"] = adata.obs.index.astype(int)

            # connect to the cell layer for napari-spatialdata compatibility
            adata.uns["spatialdata"] = {
                "region": [
                    self.mask_to_annotate
                ],  # the element(s) this table annotates
                "region_key": "region",  # column in obs that points to the region
                "instance_key": "cell",  # column in obs that points to the object ID
            }

            adata = TableModel.parse(
                adata,
                region=self.mask_to_annotate,
                region_key="region",  # << name of the column in obs
                instance_key="cell",  # << name of the column in obs with instance ids
                overwrite_metadata=True,
            )
        else:
            adata = TableModel.parse(
                adata,
                overwrite_metadata=True,
            )

        # add adata to sdata
        sdata[self.table_name] = adata

        # add quantification of qc if requested
        if self.add_qc_masks:
            # Determine the object suffix used for centroids based on the annotated mask
            # Default to 'cell' if mask_to_annotate is not set or not found
            object_suffix = "cell"
            if self.mask_to_annotate:
                for suffix, mask_name in self.mask_keys.items():
                    if mask_name == self.mask_to_annotate:
                        object_suffix = suffix
                        break

            qc_masker = QcShapeMasker(
                table_name=self.table_name,
                qc_prefix=self.qc_prefix,
                object_name=object_suffix,
                write_to_disk=False,
            )
            qc_masker.run(sdata)

        return sdata

    ############################################################################
    # Run
    ############################################################################

    def run(
        self,
        sdata: sd.SpatialData,
    ) -> None:

        ########################################################################
        # Validate inputs and prepare data
        ########################################################################

        # Validate masks and channels
        self.validate_sdata_as_input(sdata=sdata)

        # Handle overwiting
        self.prepare_to_overwrite(sdata=sdata)
        logger.info("Spatial Data object is valid and ready for quantification.")

        ########################################################################
        # Compute adata
        ########################################################################
        adata = self.build_adata(sdata=sdata)
        logger.info(
            f"Quantification complete. Resulting AnnData has {adata.n_obs} observations and {adata.n_vars} variables."
        )

        ########################################################################
        # Create connectivity within between sdata and adata
        ########################################################################
        sdata = self.connect_adata_to_mask(sdata=sdata, adata=adata)
        logger.info(
            f"AnnData table '{self.table_name}' connected to {self.mask_to_annotate}."
        )

        ########################################################################
        # Save adata table within sdata object
        ########################################################################
        try:
            sdata.write_element(self.table_name)
            logger.success(
                f"Quantification complete. Table '{self.table_name}' written to {sdata.path}"
            )
        except Exception as e:
            logger.error(f"Failed to write table '{self.table_name}': {e}")
            raise
