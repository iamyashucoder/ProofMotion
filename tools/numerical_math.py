from typing import Callable


def gradient_descent_sequence(initial_x: float, learning_rate: float, steps: int, derivative: Callable[[float], float]) -> list[float]:
    values = [initial_x]
    for _ in range(steps):
        values.append(values[-1] - learning_rate * derivative(values[-1]))
    return values
