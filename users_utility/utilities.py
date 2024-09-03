"""
This Module is used to validate String Parameters
"""

from flask import jsonify
from datetime import datetime
import pytz
from sqlalchemy.exc import SQLAlchemyError

from user_models.tables import db, User_Registration_Form, Product, Cart
from logging_package.logging_utility import log_info, log_error
from email_setup.email_operations import notify_success, notify_failure

import os

from user_models.tables import User_Registration_Form, Product, Cart


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


# Environment variables
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
EMAIL_SUBJECT_SUCCESS = os.getenv("EMAIL_SUBJECT_SUCCESS", "Operation Successful")
EMAIL_SUBJECT_ERROR = os.getenv("EMAIL_SUBJECT_ERROR", "Operation Failed")


def get_user_by_name(username):
    """Retrieve user details by username."""
    return db.session.query(User_Registration_Form).filter_by(name=username).first()


def get_product_by_uuid(product_uuid):
    """Retrieve product details by UUID."""
    return db.session.query(Product).filter_by(uuid=product_uuid).first()


def log_and_notify_error(operation, error_message):
    """Log error and send failure notification email."""
    log_error(f"{operation} Error: {error_message}")
    notify_failure(EMAIL_SUBJECT_ERROR, error_message)
    return {"message": error_message}, 400


def handle_database_error(operation, error):
    """Handle database errors."""
    error_message = f"{operation} Database Error: {str(error)}"
    return log_and_notify_error(operation, error_message)


def add_or_update_cart_item(username, product_uuid, quantity):
    """Add or update a product in the user's cart."""
    cart_item = db.session.query(Cart).filter_by(user_name=username, product_uuid=product_uuid).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        new_cart_item = Cart(user_name=username, product_uuid=product_uuid, quantity=quantity)
        db.session.add(new_cart_item)
    db.session.commit()


def log_and_notify_success(operation, username, product_uuid, product_details, total_items):
    """Log success and send success notification email."""
    success_message = f"{operation} successful for user {username} with product {product_uuid}."
    log_info(success_message)
    email_body = f"{success_message}\n\nProduct Details:\n{product_details}\nTotal Items in Cart: {total_items}"
    notify_success(EMAIL_SUBJECT_SUCCESS, email_body)


def format_product_details(product):
    """Format product details for output."""
    return {
        "uuid": product.uuid,
        "type": product.type,
        "brand": product.brand,
        "model": product.model,
        "price": product.price,
        "discounts": product.discounts,
        "specs": product.specs
    }


def format_response(status, message, data=None):
    """
    Utility function to format API response.

    Parameters:
        status (str): Status of the response ('success' or 'error').
        message (str): Detailed message of the response.
        data (dict): Additional data to be included in the response.

    Returns:
        dict: A formatted response dictionary.
    """
    response = {
        "status": status,
        "message": message,
    }
    if data:
        response["data"] = data
    return response


def prepare_product_details(product):
    """
    Prepare and format product details for logging and response.

    Args:
        product (Product): The product object.

    Returns:
        str: Formatted product details.
        dict: Product details as a dictionary.
    """
    product_details = format_product_details(product)
    product_details_str = "\n".join([f"{key}: {value}" for key, value in product_details.items()])
    return product_details_str, product_details


def format_time_12hr(naive_datetime=None, timezone='Asia/Kolkata'):
    """
    Formats the given datetime in 12-hour format with AM/PM.

    Parameters:
        - naive_datetime: datetime object, optional. If not provided, current time is used.
        - timezone: str, timezone name to localize the datetime. Default is 'Asia/Kolkata'.

    Returns:
        str: Formatted datetime string in 12-hour format with AM/PM.
    """
    if naive_datetime is None:
        naive_datetime = datetime.now()

    # Get timezone
    tz = pytz.timezone(timezone)

    # Localize and format time
    localized_datetime = tz.localize(naive_datetime)
    return localized_datetime.strftime('%Y-%m-%d %I:%M:%S %p %Z')


def calculate_delivery_days(product):
    """
    Calculates estimated delivery days based on product details.

    Parameters:
        - product: Product object

    Returns:
        int: Estimated delivery days.
    """
    # Example logic; you can customize based on your business logic
    # Assuming a standard delivery time; modify as needed
    return 5  # For example, 5 days for standard delivery


# utils.py

def format_purchase_details(success_message, product_details_str, time_of_purchase, item_cost, discount_applied,
                            total_cost_after_discount, delivery_days):
    """
    Utility function to format the purchase details for success notifications and responses.

    Parameters:
        - success_message (str): Message indicating successful purchase.
        - product_details_str (str): Formatted string with product details.
        - time_of_purchase (str): Time of purchase in 12-hour format.
        - item_cost (float): Cost of the item.
        - discount_applied (float): Discount applied to the item.
        - total_cost_after_discount (float): Total cost after discount.
        - delivery_days (int): Estimated delivery days.

    Returns:
        str: Formatted string with all purchase details.
    """
    return (f"{success_message}\n\nProduct Details:\n{product_details_str}\n"
            f"Time of Purchase: {time_of_purchase}\nCost of Item: Rs.{item_cost:.2f}\n"
            f"Discount Applied: {discount_applied}%\nTotal Cost After Discount: Rs.{total_cost_after_discount:.2f}\n"
            f"Estimated Delivery Days: {delivery_days}")


def format_filter_query_params(brand, types, model):
    """
    Format filter query parameters into a string for logging and notifications.

    Parameters:
        - brand (str): Brand filter value.
        - types (str): Type filter value.
        - model (str): Model filter value.

    Returns:
        str: Formatted string of filter query parameters.
    """
    return (f"Brand: {brand if brand else 'None'}\n"
            f"Type: {types if types else 'None'}\n"
            f"Model: {model if model else 'None'}")


def format_product_list(products):
    """
    Format a list of product objects into a readable string.

    Parameters:
        - products (list): List of Product objects.

    Returns:
        str: Formatted string of product details.
    """
    return "\n".join(
        [f"Product UUID: {product.uuid}\n"
         f"Type: {product.type}\n"
         f"Brand: {product.brand}\n"
         f"Model: {product.model}\n"
         f"Price: {product.price}\n"
         f"Discounts: {product.discounts}\n"
         f"Specs: {product.specs}\n"
         f"Created At: {product.created_at}\n"
         f"Search Count: {product.search_count}\n\n"
         for product in products]
    )


def fetch_product_by_uuid(product_uuid):
    """
    Retrieves a product by its UUID from the database.

    :param product_uuid: UUID of the product
    :return: product object or None if not found
    """
    try:
        # Ensure correct Product object is retrieved from the database
        product = db.session.query(Product).filter_by(uuid=product_uuid).first()
        if not product:
            log_error(f"Product with UUID {product_uuid} not found.")
            return None
        return product
    except SQLAlchemyError as e:
        log_error(f"Database error occurred while fetching product: {str(e)}")
        return None
