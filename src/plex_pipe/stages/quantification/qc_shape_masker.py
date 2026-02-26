from itertools import groupby

import numpy as np
import spatialdata as sd
from loguru import logger
from shapely import Point, Polygon
from shapely.strtree import STRtree


class QcShapeMasker:
    """Applies Quality Control (QC) masks based on spatial shapes.

    This class identifies cells or objects that fall within specific exclusion
    regions (defined as shapes in the SpatialData object) and marks them in the
    AnnData table.
    """

    def __init__(
        self,
        table_name: str = "quantification",
        qc_prefix: str = "qc_exclude",
        object_name: str | None = "cell",
        layer_name: str | None = "qc_mask",
        write_to_disk: bool = False,
    ) -> None:
        """Initializes the QcShapeMasker.

        Args:
            table_name: Name of the AnnData table in the SpatialData object.
            qc_prefix: Prefix for the QC shape elements in SpatialData.
            object_name: Suffix for the centroid column (e.g., 'cell' for 'centroid_cell').
            layer_name: Name of the layer to add to the AnnData object.
            write_to_disk: If True, saves the updated table to disk.
        """

        self.table_name = table_name
        self.qc_prefix = qc_prefix
        self.object_name = object_name
        self.layer_name = layer_name
        self.write_to_disk = write_to_disk

    def validate_sdata(self, sdata: sd.SpatialData) -> None:
        """Validates that the SpatialData object contains the required table and centroids.

        Args:
            sdata: The SpatialData object to validate.

        Raises:
            ValueError: If the table or centroids are missing.
        """

        # check the table present in sdata
        if self.table_name in sdata:
            logger.info(f"Table {self.table_name} present in the spatialdata object.")
        else:
            msg = f"Table {self.table_name} not present in the spatialdata object."
            logger.error(msg)
            raise ValueError(msg)

        # check that the centroids of the selected object are present in obsm
        expected_name = f"centroid_{self.object_name}"
        if expected_name in list(sdata[self.table_name].obsm.keys()):
            logger.info(
                f"Centroids: {expected_name} present in the anndata table {self.table_name}."
            )
        else:
            msg = f"Centroids: {expected_name} not present in the anndata table {self.table_name}."
            logger.error(msg)
            raise ValueError(msg)

    def rewrite_table(self, sdata: sd.SpatialData) -> None:
        """Overwrites the AnnData table on disk with the updated version.

        Args:
            sdata: The SpatialData object containing the table.

        Raises:
            Exception: If writing to disk fails.
        """

        # it's not dask backed so standard overwrite should work

        try:
            sdata.delete_element_from_disk(self.table_name)
            sdata.write_element(self.table_name, overwrite=True)
            logger.success(f"Table '{self.table_name}' written to {sdata.path}.")
        except Exception as e:
            logger.error(f"Failed to write table '{self.table_name}': {e}")
            raise

    def check_belonging(self, points: list[Point], polys: list[Polygon]) -> np.ndarray:
        """Checks which points are contained within any of the provided polygons.

        Args:
            points: A list of shapely Point objects.
            polys: A list of shapely Polygon objects defining exclusion zones.

        Returns:
            A boolean numpy array where False indicates the point is inside a polygon
            (excluded) and True indicates it is outside (kept).
        """

        # Build spatial index over polygons
        tree = STRtree(polys)

        # Candidate polygon indices for each point
        # query returns (geom_idx_in_points, geom_idx_in_polys) pairs
        pairs = tree.query(points).T

        # Initialize as all True
        mask = np.ones(len(points), dtype=bool)

        # Group candidate polygons per point to run exact test only on candidates
        # pairs is an (k, 2) ndarray; safe even if empty
        if len(pairs):
            p_idx, poly_idx = pairs[:, 0], pairs[:, 1]
            # Optional: prefetch polygon objects
            candidate_polys = [polys[j] for j in poly_idx]
            candidate_points = [points[i] for i in p_idx]

            exact = [
                poly.covers(pt)
                for pt, poly in zip(candidate_points, candidate_polys, strict=False)
            ]

            # Any True among candidates marks the point as inside some polygon
            for i, is_in in zip(p_idx, exact, strict=False):
                if is_in:
                    mask[i] = False

        return mask

    def build_qc_mask(self, sdata: sd.SpatialData) -> np.ndarray:
        """Constructs the QC mask for the entire AnnData table.

        Iterates through markers/channels in the table, looks for corresponding
        QC shapes (e.g., 'qc_exclude_DAPI'), and creates a boolean mask where
        False indicates exclusion.

        Args:
            sdata: The SpatialData object.

        Returns:
            A boolean numpy array of shape (n_obs, n_vars).
        """

        coords = np.asarray(
            sdata[self.table_name].obsm[f"centroid_{self.object_name}"],
            dtype=float,
        )
        coords = coords[:, ::-1]  # swap to match Interactive
        points = [Point(xy) for xy in coords]

        mask = np.ones(sdata[self.table_name].X.shape, dtype="bool")

        markers = [x.split("_")[0] for x in sdata[self.table_name].var.index.tolist()]

        found_any_qc = False
        # group by marker
        for marker, group in groupby(enumerate(markers), key=lambda t: t[1]):
            # collect the contiguous indices for this marker
            cols = [i for i, _ in group]
            start, end = cols[0], cols[-1] + 1

            shapes_key = f"{self.qc_prefix}_{marker}"
            if shapes_key not in sdata:
                # no QC shapes for this marker
                logger.debug(
                    f"No QC shapes found for marker '{marker}' (key: {shapes_key})."
                )
                continue

            shapes_gdf = sdata[shapes_key]
            polys = list(shapes_gdf.geometry.values)
            if not polys:
                logger.debug(
                    f"QC shape element '{shapes_key}' exists but contains no polygons."
                )
                continue

            # compute per-observation pass mask once for the marker
            mask_column = self.check_belonging(points, polys)

            # broadcast to the whole contiguous block of columns
            mask[:, start:end] = mask_column[:, None]

            logger.info(
                f"Applied QC exclusion for marker '{marker}' using shapes '{shapes_key}'."
            )
            found_any_qc = True

        if not found_any_qc:
            logger.warning(
                f"QC quantification was requested, but no exclusion shapes were found matching prefix '{self.qc_prefix}_' for any marker in the table."
            )

        return mask

    def run(self, sdata: sd.SpatialData) -> None:
        """Executes the QC masking process.

        Args:
            sdata: The SpatialData object to process.
        """

        # validate input
        self.validate_sdata(sdata)

        # add qc_mask
        mask = self.build_qc_mask(sdata)

        # add mask to anndata
        sdata[self.table_name].layers[self.layer_name] = mask

        # save to disk if requested
        if self.write_to_disk:
            self.rewrite_table(sdata)
