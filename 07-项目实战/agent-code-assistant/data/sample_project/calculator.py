"""
简易计算器模块 — 包含几个典型 bug，供 Code Agent 练习修复。

Bug 列表：
1. divide() 未处理除零
2. add() 对字符串输入没有类型检查
3. average() 对空列表没有处理
4. percentage_change() 浮点精度问题
"""


def add(a, b):
    """两数相加。"""
    # Bug 2: 没有类型检查，传入字符串会拼接而非报错
    return a + b


def subtract(a, b):
    """两数相减。"""
    return a - b


def multiply(a, b):
    """两数相乘。"""
    return a * b


def divide(a, b):
    """两数相除。"""
    # Bug 1: 除零未处理
    return a / b


def average(numbers):
    """计算列表平均值。"""
    # Bug 3: 空列表会导致 ZeroDivisionError
    total = sum(numbers)
    return total / len(numbers)


def percentage_change(old_value, new_value):
    """计算变化百分比。"""
    # Bug 4: 浮点精度问题，且 old_value=0 时会除零
    change = (new_value - old_value) / old_value * 100
    return change


def max_value(numbers):
    """找出列表最大值。"""
    if not numbers:
        return None
    result = numbers[0]
    for n in numbers:
        if n > result:
            result = n
    return result


def min_value(numbers):
    """找出列表最小值。"""
    if not numbers:
        return None
    result = numbers[0]
    for n in numbers:
        if n < result:
            result = n
    return result
