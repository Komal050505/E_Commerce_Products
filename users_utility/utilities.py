"""
This Module is used to validate String Parameters
"""


def validate_string_param(param, param_name):
    """
        Checks if the provided parameter is a valid string and not a numeric value.

        Parameters:
            param (str): The parameter value to be checked.
            param_name (str): The name of the parameter, used in error messages.

        Raises:
            ValueError: If the parameter is not a string or if it is a numeric value represented as a string.

        Example:
            validate_string_param("test_value", "test_param")  # No exception raised
            validate_string_param(12345, "test_param")         # Raises ValueError
            validate_string_param("12345", "test_param")       # Raises ValueError
        """

    if param is not None:
        if not isinstance(param, str):
            raise ValueError(f"Invalid {param_name} parameter. Expected a string.")
        if param.isdigit():
            raise ValueError(f"Invalid {param_name} parameter. Numeric value provided as a string.")
