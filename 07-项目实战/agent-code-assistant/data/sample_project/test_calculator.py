"""
计算器模块的测试用例。

运行: pytest test_calculator.py -v
"""

import pytest
from calculator import (
    add, subtract, multiply, divide,
    average, percentage_change,
    max_value, min_value,
)


class TestBasicOperations:
    """基础运算测试。"""

    def test_add_integers(self):
        assert add(2, 3) == 5

    def test_add_floats(self):
        assert add(1.5, 2.5) == 4.0

    def test_add_type_error(self):
        """Bug 2: 传入字符串应该报错而非拼接。"""
        with pytest.raises((TypeError, ValueError)):
            add("hello", 3)

    def test_subtract(self):
        assert subtract(10, 3) == 7

    def test_multiply(self):
        assert multiply(4, 5) == 20

    def test_divide_normal(self):
        assert divide(10, 2) == 5.0

    def test_divide_by_zero(self):
        """Bug 1: 除零应该返回合理的错误而非抛出未处理异常。"""
        with pytest.raises((ZeroDivisionError, ValueError)):
            divide(10, 0)


class TestStatistics:
    """统计函数测试。"""

    def test_average_normal(self):
        assert average([1, 2, 3, 4, 5]) == 3.0

    def test_average_single(self):
        assert average([42]) == 42.0

    def test_average_empty(self):
        """Bug 3: 空列表应该返回 0 或 None，而非抛出异常。"""
        result = average([])
        assert result is None or result == 0

    def test_max_value(self):
        assert max_value([3, 1, 4, 1, 5, 9]) == 9

    def test_max_value_empty(self):
        assert max_value([]) is None

    def test_min_value(self):
        assert min_value([3, 1, 4, 1, 5, 9]) == 1

    def test_min_value_empty(self):
        assert min_value([]) is None


class TestPercentage:
    """百分比变化测试。"""

    def test_percentage_increase(self):
        result = percentage_change(100, 150)
        assert abs(result - 50.0) < 0.01

    def test_percentage_decrease(self):
        result = percentage_change(200, 150)
        assert abs(result - (-25.0)) < 0.01

    def test_percentage_zero_base(self):
        """Bug 4: 基数为 0 时应该处理而非除零。"""
        result = percentage_change(0, 100)
        assert result is not None  # 不应该抛异常
