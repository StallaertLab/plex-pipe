import shutil
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import spatialdata as sd

from plex_pipe.object_quantification.controller import QuantificationController


@pytest.fixture(scope="session")
def example_sdata_copy(tmp_path_factory):
    """
    Create a single session-level copy of the example .zarr dataset.
    """
    project_root = Path(__file__).parent
    src = project_root / "example_data" / "Core_000.zarr"
    dst = tmp_path_factory.mktemp("example_sdata") / "Core_000.zarr"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture
def sdata_read(example_sdata_copy):
    """
    Load the copied dataset freshly for each test.
    """
    return sd.read_zarr(example_sdata_copy)


def test_validate_inputs_raises_on_missing_mask_or_channel(sdata_read):
    """
    Verifies input validation for essential pipeline contracts:
    - Fails fast if a required mask or channel is absent.
    """

    sdata = sdata_read

    qc = QuantificationController(
        mask_keys={"cell": "instanseg_cell"}, markers_to_quantify=["DAPI"]
    )
    qc.validate_sdata_as_input(sdata)

    ch = "ch1"
    qc = QuantificationController(
        mask_keys={"cell": "instanseg_cell"}, markers_to_quantify=[ch]
    )
    with pytest.raises(ValueError) as er:
        qc.validate_sdata_as_input(sdata)
    assert f"Channel '{ch}' not found in sdata" in str(er.value)

    mask = "x"
    qc = QuantificationController(mask_keys={"cell": mask}, markers_to_quantify=[ch])

    with pytest.raises(ValueError) as er:
        qc.validate_sdata_as_input(sdata)
    assert f"Mask '{mask}' not found in sdata. Masks present" in str(er.value)


def test_overwrite_semantics_respected_on_existing_table(sdata_read):
    """
    If a table with the same name already exists in the dataset:
    - overwrite=False => raises,
    - overwrite=True  => replaces without error.
    Protects previous results by default, while allowing explicit refresh.
    """
    sdata = sdata_read

    table_name = "instanseg_table"
    mask = "instanseg_cell"
    ch = "DAPI"

    # overwrite=False -> error
    qc_no_over = QuantificationController(
        mask_keys={"cell": mask},
        markers_to_quantify=[ch],
        table_name=table_name,
        overwrite=False,
    )
    with pytest.raises(ValueError) as er:
        qc_no_over.run(sdata)
    assert f"Table '{table_name}' already exists in sdata." in str(er.value)

    # overwrite=True -> should succeed
    qc_over = QuantificationController(
        mask_keys={"cell": mask},
        markers_to_quantify=[ch],
        table_name=table_name,
        overwrite=True,
    )
    qc_over.run(sdata)


def test_run_writes_new_table_and_aligns_vars_obs(sdata_read):
    """
    Runs controller on a temp copy and asserts:
    - a new table is attached,
    - it has observations (labels),
    - and expected feature names (mean/median) for the chosen channel exist in var.
    This confirms end-to-end stitching of morphology+intensity on real data.
    """
    sdata = sdata_read
    mask_key, ch_key = "instanseg_cell", "DAPI"

    new_table = "qc_test_table"
    assert new_table not in getattr(sdata, "tables", {})

    qc = QuantificationController(
        mask_keys={"cell": mask_key},
        markers_to_quantify=[ch_key],
        table_name=new_table,
        mask_to_annotate=mask_key,
        overwrite=False,
    )
    qc.run(sdata)

    # Table attached
    assert new_table in sdata
    adata = sdata[new_table]
    assert adata.n_obs > 0

    # Expected feature names exist (controller-specific naming: mean/median for channel)
    var_names = list(adata.var.index)
    # Use a relaxed check: presence of "mean" and "median" features related to the channel
    assert any(ch_key in v and "mean" in v for v in var_names)
    assert any(ch_key in v and "median" in v for v in var_names)
    assert "area_cell" in adata.obs.columns


def test_init_raises_on_invalid_mask_to_annotate():
    """
    Verifies that the controller raises a ValueError if `mask_to_annotate`
    is not one of the provided mask keys' values.
    """
    with pytest.raises(ValueError) as er:
        QuantificationController(
            mask_keys={"cell": "cell_mask"}, mask_to_annotate="invalid_mask"
        )
    assert (
        "mask_to_annotate 'invalid_mask' must be one of the masks to quantify"
        in str(er.value)
    )


def test_run_logs_error_on_write_failure(sdata_read, caplog):
    """
    Verifies that if writing the table to disk fails, an error is logged.
    """
    sdata = sdata_read
    mask_key, ch_key = "instanseg_cell", "DAPI"
    new_table = "table_to_fail"

    qc = QuantificationController(
        mask_keys={"cell": mask_key},
        markers_to_quantify=[ch_key],
        table_name=new_table,
        overwrite=False,
    )

    with patch(
        "plex_pipe.object_quantification.controller.logger.error"
    ) as mock_logger_error:
        with patch.object(
            sdata, "write_element", side_effect=Exception("Disk is full")
        ):
            with pytest.raises(Exception, match="Disk is full"):
                qc.run(sdata)

    mock_logger_error.assert_called_once()
    call_args, _ = mock_logger_error.call_args
    assert f"Failed to write table '{new_table}'" in call_args[0]


def test_find_ndims_columns_raises_on_duplicates():
    """
    Verifies that find_ndims_columns raises a ValueError if duplicate
    dimension indices are found for a property.
    """
    qc = QuantificationController(mask_keys={})
    obs = pd.DataFrame(columns=["prop-0", "prop-0", "prop-1"])
    with pytest.raises(ValueError) as er:
        qc.find_ndims_columns(list(obs.columns))
    assert "Duplicate dimension indices found for 'prop'" in str(er.value)


def test_quantify_all_channels_if_none_specified(sdata_read):
    """
    If no channels are specified for quantification, the controller should
    default to quantifying all available image channels in the sdata object.
    """
    sdata = sdata_read
    mask_key = "instanseg_cell"

    # Do not specify `markers_to_quantify`
    qc = QuantificationController(
        mask_keys={"cell": mask_key},
        table_name="test_table",
    )

    # The channels list should be empty initially
    assert qc.channels is None

    # Run validation, which should populate the channels
    qc.validate_sdata_as_input(sdata)

    # Now, channels should be a list of all image keys
    all_image_keys = list(sdata.images.keys())
    assert qc.channels is not None
    assert isinstance(qc.channels, list)
    assert sorted(qc.channels) == sorted(all_image_keys)


def test_get_channel_handles_3d_input_with_warning(sdata_read):
    """
    When given a 3D image, get_channel should compute the mean along the
    first axis and log a warning.
    """
    sdata = sdata_read
    qc = QuantificationController(mask_keys={"cell": "instanseg_cell"})
    channel_key = "DAPI"

    # Create a 3D numpy array
    three_d_image = np.random.rand(3, 10, 10)

    with patch(
        "plex_pipe.object_quantification.controller.logger.warning"
    ) as mock_logger_warning:
        with patch("spatialdata.get_pyramid_levels", return_value=three_d_image):
            result = qc.get_channel(sdata, channel_key)

            # Check that the result is 2D
            assert result.ndim == 2
            # Check that the shape is correct
            assert result.shape == (10, 10)
            # Check that the values are the mean
            np.testing.assert_array_almost_equal(result, np.mean(three_d_image, axis=0))

            # Check that a warning was logged
            mock_logger_warning.assert_called_once()
            call_args, _ = mock_logger_warning.call_args
            assert f"Channel '{channel_key}' has 3 dimensions" in call_args[0]


def test_get_channel_raises_on_unsupported_dims(sdata_read):
    """
    get_channel should raise a ValueError for images that are not 2D or 3D.
    """
    sdata = sdata_read
    qc = QuantificationController(mask_keys={"cell": "instanseg_cell"})
    channel_key = "DAPI"

    # Test with 4D
    four_d_image = np.random.rand(3, 10, 10, 10)
    with patch("spatialdata.get_pyramid_levels", return_value=four_d_image):
        with pytest.raises(ValueError) as er:
            qc.get_channel(sdata, channel_key)
        assert "not supported" in str(er.value)

    # Test with 1D
    one_d_image = np.random.rand(10)
    with patch("spatialdata.get_pyramid_levels", return_value=one_d_image):
        with pytest.raises(ValueError) as er:
            qc.get_channel(sdata, channel_key)
        assert "not supported" in str(er.value)


def test_get_channel_handles_2d_input_and_logs(sdata_read):
    """
    When given a 2D image, get_channel should return it unchanged and log it.
    """
    sdata = sdata_read
    qc = QuantificationController(mask_keys={"cell": "instanseg_cell"})
    channel_key = "DAPI"

    two_d_image = np.random.rand(10, 10)

    with patch(
        "plex_pipe.object_quantification.controller.logger.info"
    ) as mock_logger_info:
        with patch("spatialdata.get_pyramid_levels", return_value=two_d_image):
            result = qc.get_channel(sdata, channel_key)

            assert result.ndim == 2
            assert result.shape == (10, 10)
            np.testing.assert_array_equal(result, two_d_image)

            mock_logger_info.assert_called_once()
            call_args, _ = mock_logger_info.call_args
            assert f"Channel '{channel_key}' is 2D" in call_args[0]


def test_get_channel_squeezes_singleton_dimensions(sdata_read):
    """
    get_channel should squeeze singleton dimensions from the image array.
    """
    sdata = sdata_read
    qc = QuantificationController(mask_keys={"cell": "instanseg_cell"})
    channel_key = "DAPI"

    # Image with singleton dimensions
    squeezable_image = np.random.rand(1, 10, 1, 10)

    with patch("spatialdata.get_pyramid_levels", return_value=squeezable_image):
        result = qc.get_channel(sdata, channel_key)

        # Should be squeezed to 2D
        assert result.ndim == 2
        assert result.shape == (10, 10)
        np.testing.assert_array_equal(result, np.squeeze(squeezable_image))


def test_run_calls_qc_masker_if_enabled(sdata_read):
    """
    Verifies that the QcShapeMasker is run during quantification if add_qc_masks is True.
    """
    sdata = sdata_read
    mask_key, ch_key = "instanseg_cell", "DAPI"
    new_table = "qc_test_table"

    with patch(
        "plex_pipe.object_quantification.controller.QcShapeMasker"
    ) as mock_qc_masker:
        qc = QuantificationController(
            mask_keys={"cell": mask_key},
            markers_to_quantify=[ch_key],
            table_name=new_table,
            add_qc_masks=True,
            qc_prefix="test_qc",
            overwrite=True,
        )
        qc.run(sdata)

        mock_qc_masker.assert_called_once_with(
            table_name=new_table,
            qc_prefix="test_qc",
            object_name="cell",
            write_to_disk=False,
        )
        mock_qc_masker.return_value.run.assert_called_once_with(sdata)


def test_run_does_not_call_qc_masker_if_disabled(sdata_read):
    """
    Verifies that the QcShapeMasker is NOT run if add_qc_masks is False.
    """
    sdata = sdata_read
    mask_key, ch_key = "instanseg_cell", "DAPI"
    new_table = "no_qc_test_table"

    with patch(
        "plex_pipe.object_quantification.controller.QcShapeMasker"
    ) as mock_qc_masker:
        qc = QuantificationController(
            mask_keys={"cell": mask_key},
            markers_to_quantify=[ch_key],
            table_name=new_table,
            add_qc_masks=False,
            overwrite=True,
        )
        qc.run(sdata)

        mock_qc_masker.assert_not_called()
        mock_qc_masker.return_value.run.assert_not_called()
