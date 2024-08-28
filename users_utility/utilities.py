def validate_string_param(param, param_name):
    if param is not None:
        if not isinstance(param, str):
            raise ValueError(f"Invalid {param_name} parameter. Expected a string.")
        if param.isdigit():
            raise ValueError(f"Invalid {param_name} parameter. Numeric value provided as a string.")