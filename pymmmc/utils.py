import numpy as np
import pandas as pd


def generate_fourier_modes(periods: np.array, n_order: int) -> pd.DataFrame:
    """Generate Fourier modes.

    Parameters
    ----------
    periods : np.array
        Input array denoting the period range.
    n_order : int
        Maximum order of Fourier modes.

    Returns
    -------
    pd.DataFrame
        Fourier modes (sin and cos with different frequencies) as columns in a dataframe.

    References
    ----------
    See pymc-examples/examples/time_series/Air_passengers-Prophet_with_Bayesian_workflow.html
    """
    if n_order < 1:
        raise ValueError("n_order must be greater than or equal to 1")
    return pd.DataFrame(
        {
            f"{func}_order_{order}": getattr(np, func)(2 * np.pi * periods * order)
            for order in range(1, n_order + 1)
            for func in ("sin", "cos")
        }
    )
