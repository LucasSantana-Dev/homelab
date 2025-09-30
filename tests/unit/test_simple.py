"""
Simple tests to verify development tools are working
"""

import pytest


def test_basic_functionality():
    """Test basic Python functionality"""
    assert 1 + 1 == 2
    assert "hello" + " " + "world" == "hello world"


def test_list_operations():
    """Test list operations"""
    test_list = [1, 2, 3, 4, 5]
    assert len(test_list) == 5
    assert max(test_list) == 5
    assert min(test_list) == 1


def test_string_operations():
    """Test string operations"""
    test_string = "Homelab Manager"
    assert test_string.lower() == "homelab manager"
    assert test_string.upper() == "HOMELAB MANAGER"
    assert "Manager" in test_string


def test_dict_operations():
    """Test dictionary operations"""
    test_dict = {"name": "Homelab", "version": "2.0.0"}
    assert test_dict["name"] == "Homelab"
    assert test_dict["version"] == "2.0.0"
    assert "name" in test_dict


@pytest.mark.parametrize(
    "input_value,expected",
    [
        (1, 1),
        (2, 2),
        (3, 3),
        (10, 10),
    ],
)
def test_parametrized(input_value, expected):
    """Test parametrized test"""
    assert input_value == expected


class TestSimpleClass:
    """Test class for demonstration"""

    def test_class_method(self):
        """Test class method"""
        assert True

    def test_another_method(self):
        """Test another method"""
        result = self.helper_method()
        assert result == "test"

    def helper_method(self):
        """Helper method for testing"""
        return "test"
