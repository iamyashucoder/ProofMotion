"""Probability and statistics.

Exact distribution facts come from sympy.stats; sampling, fitting and testing
come from scipy. Both report what they assumed, because a confidence interval
without its assumptions is decoration.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

from proofmotion.runtime.registry import ToolError, tool

DISTRIBUTIONS = {
    "normal": ("Normal", ("mean", "sigma")),
    "uniform": ("Uniform", ("left", "right")),
    "exponential": ("Exponential", ("rate",)),
    "poisson": ("Poisson", ("lamda",)),
    "binomial": ("Binomial", ("n", "p")),
    "bernoulli": ("Bernoulli", ("p",)),
    "geometric": ("Geometric", ("p",)),
    "gamma": ("Gamma", ("k", "theta")),
    "beta": ("Beta", ("alpha", "beta")),
    "chisquared": ("ChiSquared", ("k",)),
}


@tool
def probability(
    distribution: Literal[
        "normal", "uniform", "exponential", "poisson", "binomial",
        "bernoulli", "geometric", "gamma", "beta", "chisquared",
    ],
    parameters: list,
    query: Literal["summary", "pdf", "cdf", "quantile"] = "summary",
    at: float = 0.0,
) -> dict[str, Any]:
    """Exact facts about a named distribution: mean, variance, pdf, cdf.

    Args:
        distribution: Which distribution.
        parameters: Its parameters in order — normal takes [mean, sigma],
            binomial [n, p], exponential [rate], and so on.
        query: summary returns mean and variance; the others evaluate at `at`.
        at: The point to evaluate pdf, cdf, or quantile at.
    """
    import sympy as sp
    from sympy import stats

    name, expected = DISTRIBUTIONS[distribution]
    if len(parameters) != len(expected):
        raise ToolError(f"{distribution} takes {len(expected)} parameter(s): {', '.join(expected)}")

    try:
        variable = getattr(stats, name)("X", *[sp.nsimplify(p) for p in parameters])
    except (ValueError, TypeError) as error:
        raise ToolError(f"could not build {distribution}{tuple(parameters)}: {error}") from error

    def scalar(value: Any) -> float | str:
        try:
            return round(float(value), 10)
        except (TypeError, ValueError):
            return str(value)

    try:
        if query == "summary":
            return {
                "distribution": distribution,
                "parameters": parameters,
                "mean": scalar(stats.E(variable)),
                "variance": scalar(stats.variance(variable)),
                "std_dev": scalar(sp.sqrt(stats.variance(variable))),
            }
        if query == "pdf":
            return {"distribution": distribution, "at": at, "pdf": scalar(stats.density(variable)(at))}
        if query == "cdf":
            return {"distribution": distribution, "at": at, "cdf": scalar(stats.cdf(variable)(at))}
        return {"distribution": distribution, "at": at, "quantile": scalar(stats.quantile(variable)(at))}
    except (NotImplementedError, ValueError, TypeError) as error:
        raise ToolError(f"{query} is not available for {distribution}: {error}") from error


@tool
def statistics_summary(data: list, confidence: float = 0.95) -> dict[str, Any]:
    """Describe a sample: centre, spread, and a confidence interval for the mean.

    Args:
        data: The observations.
        confidence: Confidence level for the interval, e.g. 0.95.
    """
    from scipy import stats as sstats

    values = np.asarray(data, dtype=float)
    if values.size < 2:
        raise ToolError("at least two observations are needed")
    if not 0 < confidence < 1:
        raise ToolError("confidence must be between 0 and 1")

    mean, sd = float(values.mean()), float(values.std(ddof=1))
    margin = float(sstats.t.ppf(0.5 + confidence / 2, values.size - 1)) * sd / float(np.sqrt(values.size))
    return {
        "n": int(values.size),
        "mean": round(mean, 8),
        "median": round(float(np.median(values)), 8),
        "std_dev": round(sd, 8),
        "variance": round(float(values.var(ddof=1)), 8),
        "min": round(float(values.min()), 8),
        "max": round(float(values.max()), 8),
        "confidence_interval": [round(mean - margin, 8), round(mean + margin, 8)],
        "confidence": confidence,
        "assumes": "the sample mean is t-distributed, which needs roughly normal data or a large sample",
    }


@tool
def linear_regression(x_values: list, y_values: list) -> dict[str, Any]:
    """Fit y = a*x + b and report the fit quality honestly.

    Args:
        x_values: Predictor observations.
        y_values: Response observations.
    """
    from scipy import stats as sstats

    xs, ys = np.asarray(x_values, dtype=float), np.asarray(y_values, dtype=float)
    if xs.size != ys.size or xs.size < 3:
        raise ToolError("x_values and y_values must match in length and hold at least three points")

    fit = sstats.linregress(xs, ys)
    return {
        "slope": round(float(fit.slope), 8),
        "intercept": round(float(fit.intercept), 8),
        "r_squared": round(float(fit.rvalue) ** 2, 8),
        "p_value": round(float(fit.pvalue), 10),
        "std_err": round(float(fit.stderr), 8),
        "equation": f"y = {fit.slope:.6g}x + {fit.intercept:.6g}",
        "note": "r_squared measures fit, not causation, and not that a line is the right model",
    }


@tool
def monte_carlo(
    expression: str,
    variable: str = "x",
    distribution: Literal["uniform", "normal"] = "uniform",
    parameters: list | None = None,
    samples: int = 20000,
) -> dict[str, Any]:
    """Estimate the expected value of an expression by sampling.

    Useful where a closed form is unavailable, and for showing convergence: the
    standard error reported here is what shrinks as 1/sqrt(n).

    Args:
        expression: Function of the sampled variable, e.g. "x**2".
        variable: Name of the sampled variable.
        distribution: uniform or normal.
        parameters: [low, high] for uniform, [mean, sigma] for normal.
            Defaults to [0, 1] and [0, 1] respectively.
        samples: Number of draws.
    """
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr

    if not 100 <= samples <= 2_000_000:
        raise ToolError("samples must be between 100 and 2,000,000")
    try:
        function = sp.lambdify(sp.Symbol(variable), parse_expr(expression), "numpy")
    except (SyntaxError, TypeError, ValueError) as error:
        raise ToolError(f"could not parse {expression!r}: {error}") from error

    generator = np.random.default_rng(0)
    args = parameters or ([0.0, 1.0])
    draws = generator.uniform(*args, samples) if distribution == "uniform" else generator.normal(*args, samples)
    evaluated = np.asarray(function(draws), dtype=float)
    evaluated = evaluated[np.isfinite(evaluated)]
    if evaluated.size == 0:
        raise ToolError("every sample evaluated to a non-finite value")

    mean = float(evaluated.mean())
    error = float(evaluated.std(ddof=1) / np.sqrt(evaluated.size))
    return {
        "expression": expression,
        "distribution": distribution,
        "parameters": args,
        "samples": int(evaluated.size),
        "estimate": round(mean, 8),
        "standard_error": round(error, 8),
        "interval_95": [round(mean - 1.96 * error, 8), round(mean + 1.96 * error, 8)],
    }
