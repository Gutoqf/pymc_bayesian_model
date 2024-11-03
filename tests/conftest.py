#   Copyright 2024 The PyMC Labs Developers
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
import warnings

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytest
from arviz import InferenceData
from xarray import DataArray, Dataset

from pymc_marketing.clv.models import CLVModel


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="also run slow tests"
    )
    parser.addoption(
        "--only-slow", action="store_true", default=False, help="only run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        # --run-slow given in cli: do not need to skip any tests
        return

    elif config.getoption("--only-slow"):
        # --only-slow given in cli: need to skip non-slow tests
        skip_fast = pytest.mark.skip(reason="Fast test")
        for item in items:
            if "slow" not in item.keywords:
                item.add_marker(skip_fast)

    else:
        # Default: skip slow tests
        skip_slow = pytest.mark.skip(reason="Slow test, use --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


@pytest.fixture(scope="module")
def cdnow_trans() -> pd.DataFrame:
    """Load CDNOW_sample transaction data into a Pandas dataframe.

    Data source: https://www.brucehardie.com/datasets/
    """
    return pd.read_csv("data/cdnow_transactions.csv")


@pytest.fixture(scope="module")
def test_summary_data() -> pd.DataFrame:
    df = pd.read_csv("data/clv_quickstart.csv")
    df["customer_id"] = df.index
    df["future_spend"] = df["monetary_value"]
    return df


def set_model_fit(model: CLVModel, fit: InferenceData | Dataset):
    if isinstance(fit, InferenceData):
        assert "posterior" in fit.groups()
    else:
        fit = InferenceData(posterior=fit)
    if not hasattr(model, "model"):
        model.build_model()
    model.idata = fit

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=UserWarning,
            message="The group fit_data is not defined in the InferenceData scheme",
        )
        model.idata.add_groups(fit_data=model.data.to_xarray())
    model.set_idata_attrs(fit)


def set_idata(model):
    """Part of basic fit method for CLVModel."""
    model.set_idata_attrs(model.idata)
    if model.data is not None:
        model._add_fit_data_group(model.data)


def create_mock_fit(params: dict[str, float]):
    """This is a mock of the fit method for the CLVModel.

    It create a fake InferenceData object that is centered around the given parameters.

    """

    def mock_fit(model, chains, draws, rng):
        model.idata = az.from_dict(
            {
                param: rng.normal(value, 1e-3, size=(chains, draws))
                for param, value in params.items()
            }
        )
        set_idata(model)

    return mock_fit


def mock_sample(*args, **kwargs):
    """This is a mock of pm.sample that returns the prior predictive samples as the posterior."""
    random_seed = kwargs.get("random_seed", None)
    model = kwargs.get("model", None)
    samples = kwargs.get("draws", 10)
    n_chains = kwargs.get("chains", 1)
    idata: InferenceData = pm.sample_prior_predictive(
        model=model,
        random_seed=random_seed,
        samples=samples,
    )

    expanded_chains = DataArray(
        np.ones(n_chains),
        coords={"chain": np.arange(n_chains)},
    )
    idata.add_groups(
        posterior=(idata.prior.mean("chain") * expanded_chains).transpose(
            "chain", "draw", ...
        )
    )
    del idata.prior
    if "prior_predictive" in idata:
        del idata.prior_predictive
    return idata
