import numpy as np
from scipy.optimize import curve_fit


def exp_decay(
    generations: np.ndarray[float], T0: float, tau: float, plateau: float
):
    """Model exponential decay of journey times:

        t = (T0 - c) * exp(-g / tau) + c

    where t = duration/journey time,
          T0 = initial best duration,
          c = plateau duration.
          g = generation,
          tau = exponential time constant.

    Args:
        generations (np.nadarray[float]): list of generations.
        T0 (float): initial best duration,
        tau (float): exponential time constant.
        plateau (float): plateau duration.

    Returns:
        exponential decay curve.
    """
    return (T0 - plateau) * np.exp(-generations / tau) + plateau


def fit_exp_decay(generations: np.ndarray[float], durations: list[float]):
    """Fit exponential decay function to durations.

    Args:
        generations (numpy.ndarray[float]): list of generations.
        durations (list[float]): list of shortest durations per generation.

    Returns:
        tuple of exponential decay function parameters, and values to plot
          exponential decay curve.
    """
    # Make initial guesses for parameters
    T0_est = durations[0]
    plateau_est = durations[-1]
    tau_est = (generations[-1] - generations[0]) / 2

    popt, _ = curve_fit(
        exp_decay, generations, durations, p0=[T0_est, tau_est, plateau_est]
    )

    fine_generations = np.linspace(
        generations[0], generations[-1], len(generations) * 5
    )

    return (
        popt,
        fine_generations.tolist(),
        exp_decay(fine_generations, *popt).tolist(),
    )


def get_r_squared(
    durations: np.ndarray[float], expected_durations: np.ndarray[float]
) -> float:
    """Get R^2 (coefficient of determination):

        R^2 = 1 - sum((t_i - t_i_pred)^2) / sum((t_i - t_mean)^2)

    where t_i = shortest journey time in generation i,
          t_i_pred = expected journey time in generation i,
          t_mean = mean journey time across all generations.

    The coefficient of determination measures how well the exponential decay
    curve replicates the improvement in journey times over successive
    generations.

    Args:
        durations (np.ndarray[float]): array of shortest durations per
          generation.
        expected_durations (np.ndarray[float]): array of durations per
          generation fitted to exponential decay function.

    Returns:
        R^2 value.
    """
    # Sum of squares of residuals
    ss_res = np.sum((durations - expected_durations) ** 2)
    # Total sum of squares
    ss_tot = np.sum((durations - np.mean(durations)) ** 2)

    return float(1 - ss_res / ss_tot)


def get_rmse(
    durations: np.ndarray[float], expected_durations: np.ndarray[float]
) -> float:
    """Get Root Mean Squared Error (RMSE):

        RMSE = sqrt(sum((t_i - t_i_pred)^2) / n)

    where t_i = shortest journey time in generation i,
          t_i_pred = expected journey time in generation i,
          n = number of generations.

    Args:
        durations (np.ndarray[float]): array of shortest durations per
          generation.
        expected_durations (np.ndarray[float]): array of durations per
          generation fitted to exponential decay function.

    Returns:
        RMSE value.
    """
    return float(np.sqrt(np.mean((durations - expected_durations) ** 2)))


def get_mae(
    durations: np.ndarray[float], expected_durations: np.ndarray[float]
) -> float:
    """Get Mean Absolute Error (MAE):

        MAE = sum(|t_i - t_i_pred|) / n

    where t_i = shortest journey time in generation i,
          t_i_pred = expected journey time in generation i,
          n = number of generations.

    Args:
        durations (np.ndarray[float]): array of shortest durations per
          generation.
        expected_durations (np.ndarray[float]): array of durations per
          generation fitted to exponential decay function.

    Returns:
        MAE value.
    """
    return float(np.mean(np.abs(durations - expected_durations)))


def get_stats(generations: list[int], durations: list[float]):
    """Perform fits and derive metrics for durations as a function of
    generation.

    Args:
        generations (list[float]): list of generations.
        durations (list[float]): list of shortest durations per generation.

    Returns:
        tuple of exponential decay function parameters, values to plot
          exponential decay curve, and metrics
    """
    generations = np.array(generations, dtype=float)
    exp_decay_params, fit_generations, fit_durations = fit_exp_decay(
        generations, durations
    )

    expected_durations = exp_decay(generations, *exp_decay_params)

    durations = np.array(durations, dtype=float)
    r_squared = get_r_squared(durations, expected_durations)
    rmse = get_rmse(durations, expected_durations)
    mae = get_mae(durations, expected_durations)

    metrics = (r_squared, rmse, mae)

    return exp_decay_params.tolist(), fit_generations, fit_durations, metrics
