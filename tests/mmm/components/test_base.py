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
import matplotlib.pyplot as plt
import numpy as np
import pymc as pm
import pytest
import xarray as xr

from pymc_marketing.mmm.components.base import (
    MissingDataParameter,
    ParameterPriorException,
    Transformation,
    selections,
)


def test_new_transformation_missing_prefix() -> None:
    class NewTransformation(Transformation):
        pass

    with pytest.raises(NotImplementedError, match="prefix must be implemented"):
        NewTransformation()


def test_new_transformation_missing_default_priors() -> None:
    class NewTransformation(Transformation):
        prefix = "new"

    with pytest.raises(NotImplementedError, match="default_priors must be implemented"):
        NewTransformation()


def test_new_transformation_missing_function() -> None:
    class NewTransformation(Transformation):
        prefix = "new"
        default_priors = {}

    with pytest.raises(NotImplementedError, match="function must be implemented"):
        NewTransformation()


lambda_function = lambda x, a: x + a  # noqa: E731


def function(x, a):
    return x + a


def method_like_function(self, x, a):
    return x + a


@pytest.mark.parametrize(
    "function",
    [
        lambda_function,
        function,
        method_like_function,
        staticmethod(function),
    ],
)
def test_new_transformation_function_works_on_instances(function) -> None:
    class NewTransformation(Transformation):
        prefix = "new"
        default_priors = {"a": "dummy"}
        function = function

    try:
        new_transformation = NewTransformation()
    except Exception as e:
        pytest.fail(f"Error: {e}")

    x = np.array([1, 2, 3])
    expected = np.array([2, 3, 4])
    np.testing.assert_allclose(new_transformation.function(x, 1), expected)


def test_new_transformation_missing_data_parameter() -> None:
    def function_without_reserved_parameter(spends, a):
        return spends + a

    class NewTransformation(Transformation):
        prefix = "new"
        function = function_without_reserved_parameter
        default_priors = {"a": "dummy"}

    with pytest.raises(MissingDataParameter):
        NewTransformation()


def test_new_transformation_missing_priors() -> None:
    def method_like_function(self, x, a, b):
        return x + a + b

    class NewTransformation(Transformation):
        prefix = "new"
        function = method_like_function
        default_priors = {"a": "dummy"}

    with pytest.raises(ParameterPriorException, match="Missing default prior: {'b'}"):
        NewTransformation()


def test_new_transformation_missing_parameter() -> None:
    class NewTransformation(Transformation):
        prefix = "new"
        function = method_like_function
        default_priors = {"b": "dummy"}

    with pytest.raises(
        ParameterPriorException, match="Missing function parameter: {'b'}"
    ):
        NewTransformation()


@pytest.fixture
def new_transformation_class() -> type[Transformation]:
    class NewTransformation(Transformation):
        prefix = "new"

        def function(self, x, a, b):
            return a * b * x

        default_priors = {
            "a": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
            "b": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
        }

    return NewTransformation


@pytest.fixture
def new_transformation(new_transformation_class) -> Transformation:
    return new_transformation_class()


def test_new_transformation_function_priors(new_transformation) -> None:
    assert new_transformation.function_priors == {
        "a": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
        "b": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
    }


def test_new_transformation_priors_at_init(new_transformation_class) -> None:
    new_prior = {"a": {"dist": "HalfNormal", "kwargs": {"sigma": 2}}}
    new_transformation = new_transformation_class(priors=new_prior)
    assert new_transformation.function_priors == {
        "a": {"dist": "HalfNormal", "kwargs": {"sigma": 2}},
        "b": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
    }


def test_new_transformation_variable_mapping(new_transformation) -> None:
    assert new_transformation.variable_mapping == {"a": "new_a", "b": "new_b"}


def test_apply(new_transformation):
    x = np.array([1, 2, 3])
    expected = np.array([6, 12, 18])
    with pm.Model() as generative_model:
        pm.Deterministic("y", new_transformation.apply(x))

    fixed_model = pm.do(generative_model, {"new_a": 2, "new_b": 3})
    np.testing.assert_allclose(fixed_model["y"].eval(), expected)


def test_new_transformation_access_function(new_transformation) -> None:
    x = np.array([1, 2, 3])
    expected = np.array([6, 12, 18])
    np.testing.assert_allclose(new_transformation.function(x, 2, 3), expected)


def test_new_transformation_apply_outside_model(new_transformation) -> None:
    with pytest.raises(TypeError, match="on context stack"):
        new_transformation.apply(1)


def test_model_config(new_transformation) -> None:
    assert new_transformation.model_config == {
        "new_a": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
        "new_b": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
    }


def test_new_transform_update_priors(new_transformation) -> None:
    new_transformation.update_priors(
        {"new_a": {"dist": "HalfNormal", "kwargs": {"sigma": 2}}}
    )

    assert new_transformation.function_priors == {
        "a": {"dist": "HalfNormal", "kwargs": {"sigma": 2}},
        "b": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
    }


def test_new_transformation_warning_no_priors_updated(new_transformation) -> None:
    with pytest.warns(UserWarning, match="No priors were updated"):
        new_transformation.update_priors(
            {"new_c": {"dist": "HalfNormal", "kwargs": {"sigma": 1}}}
        )


def test_new_transformation_sample_prior(new_transformation) -> None:
    prior = new_transformation.sample_prior()

    assert isinstance(prior, xr.Dataset)
    assert dict(prior.coords.sizes) == {
        "chain": 1,
        "draw": 500,
    }

    assert set(prior.keys()) == {"new_a", "new_b"}


def create_curve(coords) -> xr.DataArray:
    size = [len(values) for values in coords.values()]
    dims = list(coords.keys())
    data = np.ones(size)
    return xr.DataArray(
        data,
        dims=dims,
        coords=coords,
        name="data",
    )


@pytest.mark.parametrize(
    "coords, expected_size",
    [
        ({"chain": np.arange(1), "draw": np.arange(250), "x": np.arange(10)}, 1),
        (
            {
                "chain": np.arange(1),
                "draw": np.arange(250),
                "x": np.arange(10),
                "channel": ["A", "B", "C"],
            },
            3,
        ),
    ],
)
def test_new_transformation_plot_curve(
    new_transformation, coords, expected_size
) -> None:
    curve = create_curve(coords)
    fig, axes = new_transformation.plot_curve(curve)

    assert isinstance(fig, plt.Figure)
    assert len(axes) == expected_size

    plt.close()


@pytest.mark.parametrize(
    "coords, expected",
    [
        ({}, [{}]),
        ({"channel": [1, 2, 3]}, [{"channel": 1}, {"channel": 2}, {"channel": 3}]),
        (
            {"channel": [1, 2], "country": ["A", "B"]},
            [
                {"channel": 1, "country": "A"},
                {"channel": 1, "country": "B"},
                {"channel": 2, "country": "A"},
                {"channel": 2, "country": "B"},
            ],
        ),
    ],
)
def test_selections(coords, expected) -> None:
    assert list(selections(coords)) == expected


def test_change_instance_function_priors_has_no_impact(
    new_transformation_class,
) -> None:
    """What happens in the MMM logic."""
    instance = new_transformation_class()

    for _, config in instance.function_priors.items():
        config["dims"] = "channel"

    new_instance = new_transformation_class()

    assert new_instance.function_priors == {
        "a": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
        "b": {"dist": "HalfNormal", "kwargs": {"sigma": 1}},
    }
