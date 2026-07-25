import pytest
from src.add import add

@pytest.mark.parametrize("a, b, expected", [
    (2, 3, 5),           # Positive integers
    (-1, -1, -2),        # Negative integers
    (0, 0, 0),           # Zero inputs
    (3.5, 2.5, 6.0),     # Positive floats
    (-1.5, 1.5, 0.0),    # Mixed sign floats
    (0, -5, -5),         # Zero and negative
    (1000000, 1000000, 2000000),     # Large numbers
    (1.7976931348623157e+308, 1.0, 1.7976931348623157e+308),  # Near float max
    (1.0, 1.7976931348623157e+308, 1.7976931348623157e+308),  # Reverse order
    (1.1, 2.2, 3.3),     # Floating-point precision
    (1, 2.5, 3.5),       # Mixed types (int + float)
    (0, 0.0, 0.0),       # Zero with float
    (-3, 5, 2),          # Negative to positive
    (1e-10, 1e-10, 2e-10), # Very small numbers
])
def test_add(a, b, expected):
    result = add(a, b)
    # Use pytest.approx for floating-point comparisons to handle precision issues
    if isinstance(expected, float) and not expected.is_integer():
        assert result == pytest.approx(expected)
    else:
        assert result == expected