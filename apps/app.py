"""
This Module is used to perform CRUD operations on e-commerce products

"""

import json
from flask import Flask, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from apps.constants import DISCOUNT_THRESHOLD
from db_connections.configurations import DATABASE_URL, Config
from email_setup.email_operations import notify_success, notify_failure, send_email
from user_models.tables import db, Product, ValidProductDetails, User_Registration_Form, Cart
from logging_package.logging_utility import log_info, log_error, log_debug
from sqlalchemy import desc, and_, func
from datetime import datetime, timedelta
from users_utility.utilities import validate_string_param, format_product_details, log_and_notify_success, \
    add_or_update_cart_item, log_and_notify_error, get_user_by_name, handle_database_error, format_response, \
    prepare_product_details, format_time_12hr, calculate_delivery_days, format_purchase_details, EMAIL_SUBJECT_SUCCESS, \
    format_product_list, format_filter_query_params, fetch_product_by_uuid

# Create Flask app instance
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Initialize SQLAlchemy with the Flask app
db.init_app(app)

# --------------------------------------------- User_Registration Project (starting) -----------------------------------

"""
This codes is for performing actions with involvement of the actual e-commerce users..... [FOR E-COMMERCE USERS]
"""


# CART RELATED APIS
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """
    API to add a product to a user's cart.

    Request Parameters:
        - username: str
        - product_uuid: str
        - quantity: int

    Returns:
        JSON response with operation status, message, product details, and time of addition if successful.
    """
    # Retrieve parameters from the form data or query string
    username = request.form.get("username") or request.args.get("username")
    product_uuid = request.form.get("product_uuid") or request.args.get("product_uuid")
    quantity = request.form.get("quantity") or request.args.get("quantity")

    try:
        # Validate and convert inputs
        validate_string_param(username, "username")
        validate_string_param(product_uuid, "product_uuid")

        if quantity is None:
            raise ValueError("Quantity parameter is required.")

        try:
            quantity = int(quantity)
        except ValueError:
            raise ValueError("Invalid quantity parameter. Expected a positive integer.")

        if quantity <= 0:
            raise ValueError("Invalid quantity parameter. Expected a positive integer.")

        # Get user and product details
        user = get_user_by_name(username)
        if not user:
            error_message = f"User {username} not found"
            notify_failure("User Not Found", f"{error_message}\n\nUser: {username}")
            return jsonify(format_response("error", error_message)), 404

        product = fetch_product_by_uuid(product_uuid)
        if not product:
            error_message = f"Product {product_uuid} not found"
            notify_failure("Product Not Found", f"{error_message}\n\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message)), 404

        # Add or update cart item
        add_or_update_cart_item(username, product_uuid, quantity)

        # Get the current time in IST using the utility function
        timestamp_ist = format_time_12hr()

        # Log and notify success
        product_details_str, product_details = prepare_product_details(product)
        total_items = sum(item.quantity for item in Cart.query.filter_by(user_name=username).all())
        success_message = f"Product: \n{product_uuid} with quantity ( {quantity} ) added to cart at \n{timestamp_ist}."
        notify_success("Product Added to Cart",
                       f"{success_message}\n\nProduct Details:"
                       f"\n{product_details_str}\nTotal Items in Cart: {total_items}")

        return jsonify(format_response("success", "Product added to cart successfully",
                                       {"product_details": product_details, "total_items": total_items,
                                        "time_of_addition": timestamp_ist})), 200

    except ValueError as ve:
        error_message = str(ve)
        notify_failure("Input Validation Error",
                       f"{error_message}\n\nUsername: {username}"
                       f"\nProduct UUID: {product_uuid}\nRequested Quantity: {quantity}")
        return jsonify(format_response("error", error_message)), 400
    except Exception as e:
        error_message = handle_database_error("Add to Cart", e)
        notify_failure("Unexpected Error", error_message)
        return jsonify(error_message)


@app.route('/remove_quantity_from_cart', methods=['DELETE'])
def remove_quantity_from_cart():
    """
    API to remove a specified quantity of a product from the user's cart.

    Request Parameters:
        - username: str
        - product_uuid: str
        - quantity: int

    Returns:
        JSON response with operation status and message.
    """
    # Retrieve parameters from the form data or query string
    username = request.form.get("username") or request.args.get("username")
    product_uuid = request.form.get("product_uuid") or request.args.get("product_uuid")
    quantity = request.form.get("quantity") or request.args.get("quantity")

    try:
        # Validate and convert inputs
        validate_string_param(username, "username")
        validate_string_param(product_uuid, "product_uuid")

        if quantity is None:
            raise ValueError("Quantity parameter is required.")

        try:
            quantity = int(quantity)
        except ValueError:
            raise ValueError("Invalid quantity parameter. Expected a positive integer.")

        if quantity <= 0:
            raise ValueError("Invalid quantity parameter. Expected a positive integer.")

        # Get user and product details
        user = get_user_by_name(username)
        if not user:
            error_message = f"User {username} not found"
            notify_failure("User Not Found", f"{error_message}\n\nUser: {username}")
            return jsonify(format_response("error", error_message)), 404

        product = fetch_product_by_uuid(product_uuid)
        if not product:
            error_message = f"Product {product_uuid} not found"
            notify_failure("Product Not Found", f"{error_message}\n\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message)), 404

        cart_item = Cart.query.filter_by(user_name=username, product_uuid=product_uuid).first()
        if not cart_item:
            error_message = f"Product {product_uuid} not found in {username}'s cart"
            notify_failure("Product Not Found in Cart",
                           f"{error_message}\n\nUser: {username}\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message)), 404

        if cart_item.quantity < quantity:
            error_message = "Quantity to remove exceeds quantity in cart"
            notify_failure("Excess Quantity Removal Attempt",
                           f"{error_message}\n\nCart Item Quantity: {cart_item.quantity}"
                           f"\nRequested Removal Quantity: {quantity}")
            return jsonify(format_response("error", error_message)), 400

        # Update cart quantity
        cart_item.quantity -= quantity
        if cart_item.quantity == 0:
            db.session.delete(cart_item)
        db.session.commit()

        product_details_str, product_details = prepare_product_details(product)
        success_message = f"Quantity of ( {quantity} ) removed from cart for product {product_uuid}."
        notify_success("Cart Quantity Updated",
                       f"{success_message}\n\nProduct Details:\n{product_details_str}"
                       f"\nRemaining Quantity in Cart: {cart_item.quantity}")
        return jsonify(format_response("success", success_message, {"product_details": product_details,
                                                                    "remaining_quantity": cart_item.quantity})), 200

    except ValueError as ve:
        error_message = str(ve)
        notify_failure("Input Validation Error",
                       f"{error_message}\n\nUsername: {username}"
                       f"\nProduct UUID: {product_uuid}\nRequested Quantity: {quantity}")
        return jsonify(format_response("error", error_message)), 400
    except Exception as e:
        error_message = handle_database_error("Remove Quantity from Cart", e)
        notify_failure("Unexpected Error", error_message)
        return jsonify(error_message)


@app.route('/purchase-single-cart-product', methods=['POST'])
def purchase_single_cart_product():
    """
    API to purchase a single product from the user's cart.

    Query Parameters:
        - username: str
        - product_uuid: str

    Returns:
        JSON response with operation status, message, cost of item, total cost after discount,
         time of purchase, and delivery days.
    """
    # Retrieve parameters from query string
    username = request.args.get("username")
    product_uuid = request.args.get("product_uuid")

    try:
        # Validate inputs
        validate_string_param(username, "username")
        validate_string_param(product_uuid, "product_uuid")

        # Get user and product details
        user = get_user_by_name(username)
        if not user:
            error_message = f"User {username} not found."
            notify_failure("User Not Found", f"{error_message}\n\nUsername: {username}")
            return jsonify(format_response("error", error_message)), 404

        product = fetch_product_by_uuid(product_uuid)
        if not product:
            error_message = f"Product {product_uuid} not found."
            notify_failure("Product Not Found", f"{error_message}\n\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message)), 404

        cart_item = Cart.query.filter_by(user_name=username, product_uuid=product_uuid).first()
        if not cart_item:
            error_message = f"Product {product_uuid} not found in {username}'s cart."
            notify_failure("Product Not Found in Cart",
                           f"{error_message}\n\nUsername: {username}\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message)), 404

        # Get current time and calculate delivery days
        time_of_purchase = format_time_12hr()
        item_cost = product.price
        discount_applied = product.discounts
        total_cost_after_discount = item_cost * (1 - discount_applied / 100)
        delivery_days = calculate_delivery_days(product)  # Implement this function based on your logic

        # Simulate purchase
        db.session.delete(cart_item)
        db.session.commit()

        # Prepare product details
        product_details_str, product_details = prepare_product_details(product)
        success_message = "Product purchased successfully."
        formatted_details = format_purchase_details(
            success_message, product_details_str, time_of_purchase, item_cost,
            discount_applied, total_cost_after_discount, delivery_days
        )
        notify_success("Product Purchased", formatted_details)

        return jsonify(format_response("success", success_message, {
            "product_details": product_details,
            "time_of_purchase": time_of_purchase,
            "item_cost": item_cost,
            "discount_applied": discount_applied,
            "total_cost_after_discount": total_cost_after_discount,
            "delivery_days": delivery_days
        })), 200

    except ValueError as ve:
        error_message = str(ve)
        notify_failure("Input Validation Error",
                       f"{error_message}\n\nUsername: {username}\nProduct UUID: {product_uuid}")
        return jsonify(format_response("error", error_message)), 400
    except Exception as e:
        error_message = handle_database_error("Purchase Single Cart Product", e)
        notify_failure("Unexpected Error", error_message)
        return jsonify(error_message)


@app.route('/purchase-all-cart-products', methods=['POST'])
def purchase_all_cart_products():
    """
    API to purchase all products from the user's cart.

    Query Parameters:
        - username: str

    Returns:
        JSON response with operation status and message.
    """
    # Retrieve parameters from query string
    username = request.args.get("username")

    try:
        # Validate input
        validate_string_param(username, "username")

        # Get user details
        user = get_user_by_name(username)
        if not user:
            error_message = f"User {username} not found"
            notify_failure("User Not Found", f"{error_message}\n\nUsername: {username}")
            return jsonify(format_response("error", error_message)), 404

        # Fetch all cart items for the user
        cart_items = Cart.query.filter_by(user_name=username).all()
        if not cart_items:
            error_message = f"No products in {username}'s cart to purchase"
            notify_failure("No Products in Cart", f"{error_message}\n\nUsername: {username}")
            return jsonify(format_response("error", error_message)), 404

        purchased_products = []
        total_count = 0

        for item in cart_items:
            product = fetch_product_by_uuid(item.product_uuid)
            if product:
                # Get current time and calculate delivery days
                time_of_purchase = format_time_12hr()
                item_cost = product.price
                discount_applied = product.discounts
                total_cost_after_discount = item_cost * (1 - discount_applied / 100)
                delivery_days = calculate_delivery_days(product)

                product_details_str, product_details = prepare_product_details(product)
                formatted_details = format_purchase_details(
                    "\nProduct purchased successfully.", product_details_str, time_of_purchase,
                    item_cost, discount_applied, total_cost_after_discount, delivery_days
                )
                purchased_products.append({
                    "product_details": product_details,
                    "time_of_purchase": time_of_purchase,
                    "item_cost": item_cost,
                    "discount_applied": discount_applied,
                    "total_cost_after_discount": total_cost_after_discount,
                    "delivery_days": delivery_days,
                    "formatted_details": formatted_details
                })

                # Increment the count of purchased products
                total_count += 1

                # Delete the cart item after processing
                db.session.delete(item)
            else:
                error_message = f"Product with UUID {item.product_uuid} not found"
                notify_failure("Product Not Found", f"{error_message}\n\nUsername: {username}")
                return jsonify(format_response("error", error_message)), 404

        # Commit all deletions from cart
        db.session.commit()

        success_message = f"All products purchased successfully. Total products purchased: {total_count}"
        notify_success("All Products Purchased",
                       f"{success_message}\n\nPurchased Products:"
                       f"\n{', '.join([p['formatted_details'] for p in purchased_products])}"
                       f"\nTotal Count: {total_count}")

        return jsonify(format_response("success", success_message,
                                       {"purchased_products": purchased_products,
                                        "total_count": total_count})), 200

    except ValueError as ve:
        error_message = str(ve)
        notify_failure("Input Validation Error", f"{error_message}\n\nUsername: {username}")
        return jsonify(format_response("error", error_message)), 400
    except Exception as e:
        error_message = handle_database_error("Purchase All Cart Products", e)
        notify_failure("Unexpected Error", error_message)
        return jsonify(format_response("error", error_message)), 500


@app.route('/cart/delete-single-product', methods=['DELETE'])
def delete_single_product_from_cart():
    """
    Deletes a specific product from the user's cart.

    Query Parameters:
        - username: str
        - product_uuid: str

    Returns:
        JSON response with a success message or error details.
    """
    username = request.args.get('username')
    product_uuid = request.args.get('product_uuid')

    log_info(f"Attempting to delete product '{product_uuid}' from cart for user '{username}'.")

    try:
        # Validate inputs
        validate_string_param(username, "username")
        validate_string_param(product_uuid, "product_uuid")

        # Get user details
        user = get_user_by_name(username)
        if not user:
            error_message = f"User '{username}' not found."
            log_error(error_message)
            notify_failure("Delete Product from Cart Error", f"{error_message}\n\nUsername: {username}")
            return jsonify(format_response("error", error_message, {"username": username})), 404

        # Find the product in the user's cart
        cart_item = db.session.query(Cart).filter_by(user_name=username, product_uuid=product_uuid).first()
        if not cart_item:
            error_message = f"Product with UUID '{product_uuid}' not found in cart for user '{username}'."
            log_error(error_message)
            notify_failure("Delete Product from Cart Error",
                           f"{error_message}\n\nUsername: {username}\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message,
                                           {"username": username, "product_uuid": product_uuid})), 404

        # Get product details
        product = fetch_product_by_uuid(product_uuid)
        if not product:
            error_message = f"Product with UUID '{product_uuid}' not found."
            log_error(error_message)
            notify_failure("Delete Product from Cart Error",
                           f"{error_message}\n\nUsername: {username}\nProduct UUID: {product_uuid}")
            return jsonify(format_response("error", error_message,
                                           {"username": username, "product_uuid": product_uuid})), 404

        # Delete the product from the cart
        db.session.delete(cart_item)
        db.session.commit()

        # Format product details
        product_details_str, product_details = prepare_product_details(product)
        deletion_time = format_time_12hr()  # Get the current time in 12-hour format

        success_message = f"Product '{product_uuid}' deleted from cart for user '{username}' successfully."
        log_info(f"{success_message} Time of Deletion: {deletion_time}")

        email_body = (f"Success: {success_message}\n\n"
                      f"Product Details:\n{product_details_str}\n"
                      f"Time of Deletion: {deletion_time}\n"
                      f"Username: {username}\n")
        notify_success("Delete Product from Cart Success", email_body)

        return jsonify(format_response("success", success_message,
                                       {"username": username, "product_uuid": product_uuid,
                                        "product_details": product_details, "time_of_deletion": deletion_time})), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return handle_database_error("Delete Product from Cart", e)

    except Exception as e:
        error_message = f"Error deleting product from cart for user '{username}': {e}"
        log_error(error_message)
        notify_failure("Delete Product from Cart Error", f"{error_message}\n\nUsername: {username}")
        return jsonify(format_response("error",
                                       "Could not delete product from cart.", {"username": username})), 500


@app.route('/cart/clear', methods=['DELETE'])
def clear_user_cart():
    """
    Clears all items in a user's cart and sends a notification with product details and time of deletion.
    The username is expected to be provided as a URL parameter or form data.
    """
    # Retrieve the username from form data or query string
    username = request.form.get('username') or request.args.get('username')

    if not username:
        return log_and_notify_error("Clear Cart", "Username is required.")

    log_info(f"Attempting to clear cart for user {username}.")

    try:
        # Validate user existence
        user = fetch_product_by_uuid(username)
        if not user:
            return log_and_notify_error("Clear Cart", f"User '{username}' not found.")

        # Retrieve cart items
        cart_items = db.session.query(Cart).filter_by(user_name=username).all()
        if not cart_items:
            success_message = f"Cart is already empty for user {username}."
            log_info(success_message)
            notify_success(EMAIL_SUBJECT_SUCCESS, success_message)
            return jsonify({"message": success_message}), 200

        # Prepare details of products to be cleared
        product_details_list = []
        for item in cart_items:
            product = fetch_product_by_uuid(item.product_uuid)
            if product:
                product_details_str, product_details_dict = prepare_product_details(product)
                # Add spacing between products
                product_details_list.append(f"Product Details:\n{product_details_str}\n\n")

        # Clear the cart
        db.session.query(Cart).filter_by(user_name=username).delete()
        db.session.commit()

        # Time of deletion
        time_of_deletion = format_time_12hr()

        # Success message
        success_message = f"Cart cleared successfully for user {username}."
        log_info(success_message)

        # Format email body with added spacing
        email_body = (
                f"{success_message}\n\n"
                f"Products Cleared:\n" + "".join(product_details_list) + "\n\n"
                                                                         f"Time of Deletion: {time_of_deletion}"
        )
        notify_success(EMAIL_SUBJECT_SUCCESS, email_body)

        return jsonify({"message": success_message, "time_of_deletion": time_of_deletion}), 200

    except SQLAlchemyError as e:
        return handle_database_error("Clear Cart", e)

    except Exception as e:
        return log_and_notify_error("Clear Cart", f"Error clearing cart for user {username}: {e}")


# Delivery Details api
@app.route('/products/delivery/<uuid>', methods=['GET'])
def get_product_delivery_info(uuid):
    """
    Retrieves the estimated delivery time for a product based on its UUID.

    Args:
        uuid (str): The UUID of the product.

    Returns:
        Response: JSON object with product UUID, estimated delivery time in days, and product details.
    """
    log_info(f"Fetching delivery information for product UUID: {uuid}")

    try:
        # Fetch the product by UUID
        product = db.session.query(Product).filter_by(uuid=uuid).first()

        if not product:
            log_info(f"Product with UUID {uuid} not found.")
            return jsonify({"message": "Product not found."}), 404

        # Prepare product details for email and response
        product_details_str, product_details_dict = prepare_product_details(product)

        # Prepare the delivery information
        delivery_info = {
            "uuid": str(product.uuid),
            "delivery_time_days": product.delivery_time_days,
            "product_details": product_details_dict  # Include product details in the response
        }

        log_info(f"Delivery information for product UUID {uuid} fetched successfully.")
        notify_success(
            "Fetch Product Delivery Info Success",
            f"Successfully fetched delivery information for product UUID: {uuid}\n\n"
            f"Delivery Time (Days): {product.delivery_time_days}\n\n"
            f"Product Details:\n{product_details_str}"
        )

        return jsonify(delivery_info), 200

    except Exception as e:
        log_error(f"Error fetching delivery information for product UUID {uuid}: {e}")

        # Include product details if available in failure notification
        notify_failure(
            "Fetch Product Delivery Info Error",
            f"Failed to fetch delivery information for product UUID {uuid}: {e}\n\n"
            f"Product Details:\n{product_details_str if 'product_details_str' in locals() else 'N/A'}"
        )

        return jsonify({"error": "Could not fetch delivery information."}), 500


# --------------------------------------------- User_Registration Project (ending) -------------------------------------
# **********************************************************************************************************************
# **********************************************************************************************************************
# **********************************************************************************************************************
# --------------------------------------------- E_Commerce Project (starting) ------------------------------------------

"""
This codes is for performing actions without involvement of the actual e-commerce users... [ONLY FOR DEVELOPERS]
"""


@app.route('/products/count', methods=['GET'])
def get_products_count():
    """
    Fetches the count of products in stock based on type, brand, or model, with support for case-sensitive and partial
    matching. Includes detailed product information and criteria used in email notifications.

    Query Parameters:
        type (str): Filter by product type (case-sensitive).
        brand (str): Filter by product brand (case-insensitive).
        model (str): Filter by product model (case-insensitive).

    Returns:
        JSON: A JSON object containing the count of products and an optional message.
        HTTP Status Codes:
            - 200 OK: Success with product count.
            - 400 Bad Request: Invalid input or missing query parameters.
            - 500 Internal Server Error: Database or server errors.
    """
    log_info("Starting product count retrieval.")
    try:
        product_type = request.args.get('type')
        brand = request.args.get('brand')
        model = request.args.get('model')

        # Validation for query parameters
        try:
            validate_string_param(product_type, "type")
            validate_string_param(brand, "brand")
            validate_string_param(model, "model")
        except ValueError as ve:
            log_error(f"Validation error: {ve}")
            notify_failure("Product Count Error", f"Validation error: {ve}")
            return jsonify({"error": str(ve)}), 400

        conditions = []
        if product_type:
            conditions.append(Product.type.ilike(product_type))  # Case-sensitive match

        if brand:
            conditions.append(Product.brand.ilike(brand))  # Case-insensitive match
        if model:
            conditions.append(Product.model.ilike(model))  # Case-insensitive match

        if not conditions:
            error_message = "At least one query parameter (type, brand, or model) must be provided."
            log_info(error_message)
            notify_failure("Product Count Error", error_message)
            return jsonify({"error": error_message}), 400

        products = db.session.query(Product).filter(and_(*conditions)).all()
        count = len(products)
        log_info(f"Product count retrieved successfully: {count}")

        product_details = [product.to_dict() for product in products]
        log_debug(f"Product details: {product_details}")

        # Build the criteria string
        criteria_str = []
        if product_type:
            criteria_str.append(f"Type: {product_type}")
        if brand:
            criteria_str.append(f"Brand: {brand}")
        if model:
            criteria_str.append(f"Model: {model}")
        criteria_str = ', '.join(criteria_str) or "None"

        if product_details:
            # Build the product details string with separation between products
            product_details_str = '\n\n'.join([
                f"UUID: {product['uuid']}\n"
                f"Type: {product['type']}\n"
                f"Brand: {product['brand']}\n"
                f"Model: {product['model']}\n"
                f"Price: {product['price']}\n"
                f"Discounts: {product['discounts']}\n"
                f"Specs: {product['specs']}\n"
                f"Created At: {product['created_at']}\n"
                f"Search Count: {product['search_count']}"
                for product in product_details
            ])

            # Construct the email body
            email_body = (f"Product count retrieved successfully: {count}\n\n"
                          f"Criteria used for filtering:\n{criteria_str}\n\n"
                          f"Products matching the criteria:\n\n"
                          f"{product_details_str}")

        else:
            email_body = (f"Product count retrieved successfully: {count}\n\n"
                          f"Criteria used for filtering:\n{criteria_str}\n\n"
                          f"No products match the criteria.")

        # Notify success with detailed information
        notify_success("Product Count Success",
                       f"The count of products matching the criteria has been retrieved successfully.\n\n"
                       f"Details:\n{email_body}")

        return jsonify({
            "count": count,
            "message": "Product count retrieved successfully.",
            "products": product_details
        }), 200

    except SQLAlchemyError as e:
        log_error(f"Database error occurred: {e}")
        notify_failure("Product Count Error",
                       f"A database error occurred while retrieving product count: {e}")
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        log_error(f"An unexpected error occurred: {e}")
        notify_failure("Product Count Error",
                       f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500


@app.route('/products/clearance_sale', methods=['PATCH'])
def clearance_sale():
    """
    Applies a discount to old stock based on the provided cutoff date and discount percentage, valid for 12 days
    from the provided start date.

    Query Parameters: start_date (str): The start date of the clearance sale in YYYY-MM-DD format. cutoff_date (str):
    The cutoff date in YYYY-MM-DD format. Products created before this date will have discounts applied.

    discount_percentage (float): The discount percentage to apply to the old products.

    Returns:
        JSON: A JSON object with the number of products updated and a success message.
        HTTP Status Codes:
            - 200 OK: Discounts applied successfully.
            - 400 Bad Request: Invalid date format, missing parameters, or discount percentage out of range.
            - 500 Internal Server Error: Database or server errors.
    """
    log_info("Starting clearance sale for old stock.")
    try:
        start_date_str = request.args.get('start_date')
        cutoff_date_str = request.args.get('cutoff_date')
        discount_percentage_str = request.args.get('discount_percentage')

        if not start_date_str or not cutoff_date_str or not discount_percentage_str:
            error_message = "The 'start_date', 'cutoff_date', and 'discount_percentage' parameters are required."
            log_error(error_message)
            notify_failure("Clearance Sale Error", error_message)
            return jsonify({"error": error_message}), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            cutoff_date = datetime.strptime(cutoff_date_str, '%Y-%m-%d')
        except ValueError:
            error_message = (f"Invalid date format: start_date: {start_date_str}, cutoff_date: {cutoff_date_str}."
                             f" Expected YYYY-MM-DD.")
            log_error(error_message)
            notify_failure("Clearance Sale Error", error_message)
            return jsonify({"error": error_message}), 400

        end_date = start_date + timedelta(days=12)

        # Checks if the current date is within the 12-day sale period
        if not (start_date <= datetime.now() <= end_date):
            log_info("Clearance sale is not active.")
            return jsonify({"message": "Clearance sale is not active at this time."}), 400

        try:
            discount_percentage = float(discount_percentage_str)
            if discount_percentage < 0 or discount_percentage > 100:
                raise ValueError("Discount percentage must be between 0 and 100.")
        except ValueError:
            error_message = (f"Invalid discount percentage: {discount_percentage_str}. Must be a number between 0 and "
                             f"100.")
            log_error(error_message)
            notify_failure("Clearance Sale Error", error_message)
            return jsonify({"error": error_message}), 400

        # Fetch and update old products with the discount
        old_products = db.session.query(Product).filter(Product.created_at < cutoff_date).all()
        old_product_count = len(old_products)

        if old_product_count == 0:
            log_info(f"No products found before the cutoff date: {cutoff_date_str}")
            notify_success("Clearance Sale Success",
                           f"No products found before the specified cutoff date: {cutoff_date_str}.")
            return jsonify({"message": "No products found before the specified cutoff date."}), 200

        # Build product details for notification
        discounted_products = []
        for product in old_products:
            original_price = product.price
            discount_amount = product.price * (discount_percentage / 100)
            product.price -= discount_amount
            product.discount = discount_percentage
            discounted_products.append({
                "product_uuid": str(product.uuid),
                "product_brand": product.brand,
                "product_type": product.type,
                "product_model": product.model,
                "original_price": original_price,
                "new_price": product.price,
                "discount_percentage": discount_percentage
            })

        db.session.commit()

        log_info(f"Successfully applied a {discount_percentage}% discount to {old_product_count} old products.")
        # Construct the email body with additional newline gaps
        product_details_str = '\n\n'.join([
            f"UUID: {product['product_uuid']}\n"
            f"Brand: {product['product_brand']}\n"
            f"Type: {product['product_type']}\n"
            f"Model: {product['product_model']}\n"
            f"Original Price: {product['original_price']:.2f}\n"
            f"New Price: {product['new_price']:.2f}\n"
            f"Discount: {product['discount_percentage']}%"
            for product in discounted_products
        ])

        notify_success("Clearance Sale Success",
                       f"Successfully applied a {discount_percentage}% discount to {old_product_count} products "
                       f"created before {cutoff_date_str}.\n\n"
                       f"Clearance Sale Criteria:\n"
                       f"Start Date: {start_date_str}\n"
                       f"Cutoff Date: {cutoff_date_str}\n"
                       f"Discount Percentage: {discount_percentage}\n\n"
                       f"Details of discounted products:\n{product_details_str}")

        return jsonify({
            "updated_count": old_product_count,
            "message": "Discounts applied to old products successfully.",
            "discounted_products": discounted_products
        }), 200

    except SQLAlchemyError as e:
        log_error(f"Database error during clearance sale: {e}")
        notify_failure("Clearance Sale Error",
                       f"Database error occurred during clearance sale: {e}")
        return jsonify({"error": "Database error occurred.", "details": str(e)}), 500

    except Exception as e:
        log_error(f"Unexpected error during clearance sale: {e}")
        notify_failure("Clearance Sale Error",
                       f"Unexpected error occurred during clearance sale: {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500


@app.route('/products/bulk/increase-price/by-date-range', methods=['PATCH'])
def increase_bulk_product_price_by_date_range():
    """
    Increases the price of products based on the provided date range and increase percentage.

    Query Parameters:
    start_date (str): The start date in YYYY-MM-DD format. Products created on or after this date
    will have price increases applied.

    end_date (str): The end date in YYYY-MM-DD format. Products created on or
    before this date will have price increases applied.

    increase_percentage (float): The percentage by which to increase the prices of the products.

    Returns:
        JSON: A JSON object with the number of products updated and a success message.
        HTTP Status Codes:
            - 200 OK: Price increases applied successfully.
            - 400 Bad Request: Invalid date format or missing parameters.
            - 500 Internal Server Error: Database or server errors.
    """
    log_info("Starting to increase product prices.")
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        increase_percentage_str = request.args.get('increase_percentage')

        if not start_date_str or not end_date_str or not increase_percentage_str:
            log_error("Missing required parameters: start_date, end_date, and increase_percentage.")
            return jsonify({"error": "start_date, end_date, and increase_percentage parameters are required."}), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            log_error(f"Invalid date format: start_date={start_date_str}, end_date={end_date_str}")
            return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

        try:
            increase_percentage = float(increase_percentage_str)
            if increase_percentage < 0:
                raise ValueError("Increase percentage must be a positive number.")
        except ValueError as ve:
            log_error(f"Invalid increase percentage: {increase_percentage_str} - {ve}")
            return jsonify({"error": "Invalid increase percentage. Must be a positive number."}), 400

        # Fetch and update products within the date range
        products_to_update = (db.session.query(Product).filter
                              (Product.created_at >= start_date, Product.created_at <= end_date).all())
        product_count = len(products_to_update)

        if product_count == 0:
            log_info(f"No products found between the dates: {start_date_str} and {end_date_str}")
            return jsonify({"message": "No products found within the specified date range."}), 200

        updated_products = []

        for product in products_to_update:
            original_price = product.price
            increase_amount = product.price * (increase_percentage / 100)
            product.price += increase_amount

            updated_products.append({
                "product_uuid": product.uuid,
                "product_brand": product.brand,
                "product_type": product.type,
                "product_model": product.model,
                "original_price": original_price,
                "new_price": product.price,
                "increase_percentage": increase_percentage
            })

        db.session.commit()

        log_info(f"Successfully increased prices by {increase_percentage}% for {product_count} products.")

        # Create the email body with additional newline gaps
        product_details_str = '\n\n'.join([
            f"UUID: {product['product_uuid']}\n"
            f"Brand: {product['product_brand']}\n"
            f"Type: {product['product_type']}\n"
            f"Model: {product['product_model']}\n"
            f"Original Price: {product['original_price']:.2f}\n"
            f"New Price: {product['new_price']:.2f}\n"
            f"Increase Percentage: {product['increase_percentage']}%"
            for product in updated_products
        ])

        notify_success("Increase Product Price Success",
                       f"Successfully applied a {increase_percentage}% increase.\n\n"
                       f"Updated count: {product_count}\n\n"
                       f"Products created between start date: {start_date_str} and end date: {end_date_str}:\n\n"
                       f"{product_details_str}")

        return jsonify({
            "updated_count": product_count,
            "message": "Prices increased for products successfully.",
            "updated_products": updated_products
        }), 200

    except SQLAlchemyError as e:
        log_error(f"Database error during price increase: {e}")
        notify_failure("Price Increase Error", f"Database error during price increase: {e}")
        return jsonify({"error": "Database error occurred.", "details": str(e)}), 500

    except Exception as e:
        log_error(f"Unexpected error during price increase: {e}")
        notify_failure("Price Increase Error", f"Unexpected error during price increase: {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500


@app.route('/products/clear_old_stock', methods=['DELETE'])
def clear_old_stock():
    """
    Clears old stock based on the provided cutoff date.

    Query Parameters:
        cutoff_date (str): The cutoff date in YYYY-MM-DD format. Products created before this date will be deleted.

    Returns:
        JSON: A JSON object with the number of products deleted and a success message.
        HTTP Status Codes:
            - 200 OK: Products cleared successfully.
            - 400 Bad Request: Invalid date format or missing parameter.
            - 500 Internal Server Error: Database or server errors.
    """
    log_info("Starting to clear old stock.")
    try:
        cutoff_date_str = request.args.get('cutoff_date')
        if not cutoff_date_str:
            error_message = "The 'cutoff_date' parameter is required."
            log_error(error_message)
            notify_failure("Clear Old Stock Error", error_message)
            return jsonify({"error": error_message}), 400

        try:
            cutoff_date = datetime.strptime(cutoff_date_str, '%Y-%m-%d')
        except ValueError:
            error_message = f"Invalid date format: {cutoff_date_str}. Expected YYYY-MM-DD."
            log_error(error_message)
            notify_failure("Clear Old Stock Error", error_message)
            return jsonify({"error": error_message}), 400

        # Fetch old products
        old_products = db.session.query(Product).filter(Product.created_at < cutoff_date).all()
        old_product_count = len(old_products)

        if old_product_count == 0:
            log_info(f"No products found before the cutoff date: {cutoff_date_str}")
            notify_failure("Clear Old Stock Success",
                           f"No products found before the specified cutoff date: {cutoff_date_str}.")
            return jsonify({"message": "No products found before the specified cutoff date."}), 200

        # Build product details for notification
        product_details_str = '\n'.join([
            f"UUID: {product.uuid}, Type: {product.type}, Brand: {product.brand}, "
            f"Model: {product.model}, Price: {product.price}, Discounts: {product.discounts}, "
            f"Specs: {product.specs}, Created At: {product.created_at}, "
            f"Search Count: {product.search_count}"
            for product in old_products
        ])

        # Delete old products
        for product in old_products:
            db.session.delete(product)
        db.session.commit()

        log_info(f"Successfully cleared {old_product_count} old products.")
        notify_success("Clear Old Stock Success",
                       f"Successfully cleared {old_product_count} products created before {cutoff_date_str}.\n\n"
                       f"Details of products deleted:\n{product_details_str}")

        return jsonify({"deleted_count": old_product_count, "message": "Old products cleared successfully."}), 200

    except SQLAlchemyError as e:
        log_error(f"Database error during old stock clearance: {e}")
        notify_failure("Clear Old Stock Error",
                       f"Database error occurred during old stock clearance: {e}")
        return jsonify({"error": "Database error occurred.", "details": str(e)}), 500

    except Exception as e:
        log_error(f"Unexpected error during old stock clearance: {e}")
        notify_failure("Clear Old Stock Error",
                       f"Unexpected error occurred during old stock clearance: {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500


@app.route('/products/search', methods=['GET'])
def search_products():
    """
    Searches for products based on the provided query string in the URL parameters.

    This route searches for products where the 'type', 'brand', or 'model' fields match the
    search query string provided by the user in a case-insensitive manner.

    Query Parameters:
        query (str): A string to search for in the 'type', 'brand', or 'model' fields of the products.

    Returns:
        Response: JSON array of products that match the search query, or a message indicating no matches found.
    """
    log_info("Starting product search.")
    query = request.args.get('query', '', type=str)

    try:
        # Perform the search query on the database
        search_results = db.session.query(Product).filter(
            Product.type.ilike(f'%{query}%') |
            Product.brand.ilike(f'%{query}%') |
            Product.model.ilike(f'%{query}%')
        ).all()

        # Check and log the type of search_results
        if isinstance(search_results, list):
            log_debug("Search results are of type 'list'.")
        else:
            log_error(f"Search results are not a list: {search_results}")

        # Calculate the total count of search results
        total_count = len(search_results)
        log_debug(f"Total number of products found: {total_count}")

        if not search_results:
            log_info("No products match the search query.")
            notify_success(
                "Product Search Success",
                f"No products found matching the search criteria.\n\n"
                f"Search Query: {query}\n"
                f"Total Products Count: 0"
            )
            return jsonify({
                "query": query,
                "total_count": total_count,
                "products": []
            }), 200

        # Update search count for each matching product
        for product in search_results:
            if hasattr(product, 'search_count'):
                product.search_count += 1
            else:
                log_error("Product object does not have 'search_count' attribute.")
        db.session.commit()

        # Format the product list using the utility function
        products_list_str = format_product_list(search_results)

        log_info("Products found matching the search criteria.")
        email_body = (
            f"Successfully found {total_count} products matching the search criteria:\n\n"
            f"Search Query: {query}\n"
            f"Total Products Count: {total_count}\n\n"
            f"{products_list_str}"
        )

        # Notify success with the formatted product details in the email body
        notify_success("Product Search Success", email_body)
        return jsonify({
            "query": query,
            "total_count": total_count,
            "products": [product.to_dict() for product in search_results]
        }), 200

    except Exception as e:
        # Log the error and send a failure notification email
        log_error(f"Error during product search: {e}")
        notify_failure(
            "Product Search Error",
            f"Error during product search.\n\n"
            f"Search Query: {query}\n"
            f"Error Details: {e}"
        )
        return jsonify({
            "error": "Search failed",
            "query": query,
            "total_count": 0
        }), 500


@app.route('/products/latest', methods=['GET'])
def get_latest_products():
    """
    Retrieves the latest products based on their creation timestamp.

    This route fetches products ordered by the most recent creation time.

    Returns:
        Response: JSON object with total count and array of latest products.
    """
    log_info("Fetching latest products.")
    try:
        latest_products = db.session.query(Product).order_by(desc(Product.created_at)).all()
        log_debug(f"Latest products retrieved: {latest_products}")

        # Calculate the total count of products
        total_count = len(latest_products)

        if not latest_products:
            log_info("No latest products found.")
            # Notify success with no products found
            notify_success(
                "Fetch Latest Products Success",
                "Successfully fetched latest products, but no products were found."
            )
            # Return a response with total count and empty product list
            return jsonify({"total_count": total_count, "products": []})

        # Prepare the detailed product list for the email using the utility function
        products_list_str = format_product_list(latest_products)

        log_info("Latest products fetched successfully.")
        # Notify success with detailed product information and total count
        notify_success(
            "Fetch Latest Products Success",
            f"Successfully fetched the latest products.\n\nTotal Products Count: {total_count}\n\n{products_list_str}"
        )

        # Return a response with total count and product details
        return jsonify({"total_count": total_count, "products": [product.to_dict() for product in latest_products]})
    except Exception as e:
        log_error(f"Error fetching latest products: {e}")
        notify_failure(
            "Fetch Latest Products Error",
            f"Failed to fetch the latest products due to an error.\n\nError Details: {e}"
        )
        return jsonify({"error": "Could not fetch latest products"}), 500


@app.route('/products/latest-discounted', methods=['GET'])
def get_latest_discounted_products():
    """
    Retrieves the latest discounted products based on their creation timestamp.

    This route fetches products with discounts greater than the defined threshold,
    ordered by the most recent creation time.

    Returns:
        Response: JSON object with total count and array of latest discounted products.
    """
    log_info("Fetching latest discounted products.")
    try:
        # Query for latest discounted products
        latest_discounted_products = (
            db.session.query(Product)
            .filter(Product.discounts > DISCOUNT_THRESHOLD)
            .order_by(desc(Product.created_at))
            .all()
        )

        # Calculate the total count of discounted products
        total_count = len(latest_discounted_products)
        log_debug(f"Latest discounted products retrieved: {latest_discounted_products}")

        if not latest_discounted_products:
            log_info("No latest discounted products found.")
            # Notify success with no products found
            notify_success(
                "Fetch Latest Discounted Products Success",
                f"Successfully fetched latest discounted products, but no products were found.\n\n"
                f"Discount Condition: Discounts greater than {DISCOUNT_THRESHOLD}%\n"
                "Total Products Count: 0"
            )
            # Return a response with total count and empty product list
            return jsonify({
                "discount_condition": f"Discounts greater than {DISCOUNT_THRESHOLD}%",
                "total_count": total_count,
                "products": []
            })

        # Prepare the detailed product list using the utility function
        products_list_str = format_product_list(latest_discounted_products)

        log_info("Latest discounted products fetched successfully.")
        # Notify success with detailed product information and total count
        notify_success(
            "Fetch Latest Discounted Products Success",
            f"Successfully fetched the latest discounted products.\n\n"
            f"Discount Condition: Discounts greater than {DISCOUNT_THRESHOLD}%\n"
            f"Total Products Count: {total_count}\n\n{products_list_str}"
        )

        # Return a response with discount condition, total count, and product details
        return jsonify({
            "discount_condition": f"Discounts greater than {DISCOUNT_THRESHOLD}%",
            "total_count": total_count,
            "products": [product.to_dict() for product in latest_discounted_products]
        })
    except Exception as e:
        log_error(f"Error fetching latest discounted products: {e}")
        notify_failure(
            "Fetch Latest Discounted Products Error",
            f"Failed to fetch the latest discounted products due to an error.\n\n"
            f"Discount Condition: Discounts greater than {DISCOUNT_THRESHOLD}%\n"
            f"Error Details: {e}"
        )
        return jsonify({
            "error": "Could not fetch latest discounted products",
            "discount_condition": f"Discounts greater than {DISCOUNT_THRESHOLD}%",
            "total_count": 0
        }), 500


@app.route('/products/discounted', methods=['GET'])
def get_products_by_discount():
    """
    Retrieves products sorted by discount, from the highest to the lowest.

    This route fetches all products ordered by discount value in descending order.

    Returns:
        Response: JSON array of products sorted by discount.
    """
    log_info("Fetching products sorted by discount.")
    try:
        # Query for products sorted by discount
        discounted_products = db.session.query(Product).order_by(desc(Product.discounts)).all()

        total_count = len(discounted_products)
        log_debug(f"Products sorted by discount retrieved: {discounted_products}")

        if discounted_products:
            log_info("Products sorted by discount fetched successfully.")
            # Generate a formatted message to include product details
            product_details_str = format_product_list(discounted_products)
            email_body = (f"Successfully fetched {total_count} products "
                          f"sorted by discount:\n\n{product_details_str}")

            # Notify success with the formatted product details in the email body
            notify_success("Fetch Products by Discount Success", email_body)

            return jsonify({
                "total_count": total_count,
                "products": [product.to_dict() for product in discounted_products]
            })
        else:
            log_info("No products with discounts found.")
            # Notify that no discounted products were found
            notify_success(
                "Fetch Products by Discount - No Products Found",
                "No products with discounts found."
            )
            return jsonify({
                "total_count": 0,
                "message": "No discounted products found"
            }), 404
    except Exception as e:
        log_error(f"Error fetching products sorted by discount: {e}")
        notify_failure("Fetch Products by Discount Error", f"Failed to fetch products sorted by discount: {e}")
        return jsonify({
            "error": "Could not fetch products sorted by discount",
            "details": str(e)
        }), 500


@app.route('/products/price-range', methods=['GET'])
def filter_by_price_range():
    """
    Filters products based on a price range.

    This route filters products by a minimum and maximum price based on the provided query parameters.

    Query Parameters:
        min_price (float): The minimum price of the product to filter by.
        max_price (float): The maximum price of the product to filter by.

    Returns:
        Response: JSON array of products within the price range.
    """
    log_info("Starting filter by price range.")
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    if min_price is None or max_price is None:
        log_info("Invalid input: Both min_price and max_price are required.")
        return jsonify({"error": "Both min_price and max_price are required"}), 400

    try:
        # Query for products within the specified price range
        products = db.session.query(Product).filter(Product.price.between(min_price, max_price)).all()
        log_debug(f"Products in price range ({min_price}, {max_price}): {products}")

        # Calculate the total count of filtered products
        total_count = len(products)

        if not products:
            log_info("No products found in the specified price range.")
            # Notify success with no products found
            notify_success(
                "Filter Products by Price Range Success",
                f"Successfully filtered products by price range ({min_price} - {max_price}), "
                f"but no products were found."
            )
            return jsonify({
                "min_price": min_price,
                "max_price": max_price,
                "total_count": 0,
                "products": []
            }), 200

        # Prepare the detailed product list for the email
        products_list_str = format_product_list(products)

        log_info("Products filtered by price range successfully.")
        # Notify success with detailed product information
        notify_success(
            "Filter Products by Price Range Success",
            f"Successfully filtered products by price range ({min_price} - {max_price}):\n\n"
            f"Total Products Count: {total_count}\n\n"
            f"{products_list_str}"
        )
        return jsonify({
            "min_price": min_price,
            "max_price": max_price,
            "total_count": total_count,
            "products": [product.to_dict() for product in products]
        }), 200

    except Exception as e:
        log_error(f"Error filtering products by price range: {e}")
        notify_failure(
            "Filter Products by Price Range Error",
            f"Failed to filter products by price range due to an error.\n\n"
            f"Price Range: ({min_price} - {max_price})\n"
            f"Error Details: {e}"
        )
        return jsonify({
            "error": "Failed to filter products by price range",
            "min_price": min_price,
            "max_price": max_price
        }), 500


@app.route('/products/specs', methods=['POST'])
def filter_products_by_specs():
    """
    Filters products based on specifications provided in the JSON body.

    This route filters products by specifications such as color, size, etc., based on the JSON body.

    JSON Body:
        specs (dict): A dictionary where keys are specification names and values are the desired values.

    Returns:
        Response: JSON array of products that match the specified criteria.
    """
    log_info("Starting filter products by specs.")

    # Capture raw data for debugging
    raw_data = request.get_data(as_text=True)
    log_debug(f"Raw data received: {raw_data}")

    try:
        # Attempt to parse the JSON data
        data = json.loads(raw_data)
        log_debug(f"Parsed data: {data}")

        if "specs" not in data or not isinstance(data["specs"], dict):
            log_error("No valid specs provided in the request body.")
            return jsonify({"error": "No valid specs provided for filtering"}), 400

        specs = data["specs"]

        # Fetch all products from the database
        products = db.session.query(Product).all()

        # Filter products based on the specs
        filtered_products = []
        for product in products:
            try:
                if isinstance(product.specs, str):
                    product_specs = json.loads(product.specs)
                elif isinstance(product.specs, dict):
                    product_specs = product.specs
                else:
                    raise ValueError(f"Invalid type for product specs: {type(product.specs)}")

                if all(product_specs.get(key) == value for key, value in specs.items()):
                    filtered_products.append(product)
            except json.JSONDecodeError as e:
                log_error(f"Failed to parse product specs: {e}")
                continue

        log_debug(f"Filtered products: {filtered_products}")
        if not filtered_products:
            log_info("No products match the spec criteria.")
            notify_success(
                "Filter Products by Specs Success",
                "Successfully filtered products by specs, but no products were found."
            )
            return jsonify({"message": "No products match the specified criteria."}), 200

        log_info("Products filtered by specs successfully.")
        # Prepare the detailed product list for the email
        products_list = "\n".join(
            [f"Product UUID: {product.uuid}\n"
             f"Type: {product.type}\n"
             f"Brand: {product.brand}\n"
             f"Model: {product.model}\n"
             f"Price: {product.price}\n"
             f"Discounts: {product.discounts}\n"
             f"Specs: {product.specs}\n"
             f"Created At: {product.created_at}\n"
             f"Search Count: {product.search_count}\n"
             for product in filtered_products]
        )

        # Notify success with detailed product information
        notify_success(
            "Filter Products by Specs Success",
            f"Successfully filtered products by specs:\n\n{products_list}"
        )
        return jsonify([product.to_dict() for product in filtered_products])

    except json.JSONDecodeError as e:
        log_error(f"JSONDecodeError: {e}")
        notify_failure("Filter Products by Specs Error", f"Invalid JSON format: {e}")
        return jsonify({"error": f"Invalid JSON format: {e}"}), 400
    except ValueError as ve:
        log_error(f"ValueError: {ve}")
        notify_failure("Filter Products by Specs Error", f"Value error: {ve}")
        return jsonify({"error": f"Value error: {ve}"}), 400
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        notify_failure("Filter Products by Specs Error", f"Failed to filter products by specs: {e}")
        return jsonify({"error": f"Failed to filter products by specs: {e}"}), 500


@app.route('/products/recent/24hrs', methods=['GET'])
def get_recent_within_last_24hrs_products():
    """
    Retrieves products created in the last 24 hours.

    This route fetches products with a creation timestamp within the last 24 hours.

    Returns:
        Response: JSON array of products created in the last 24 hours.
    """
    log_info("Fetching products created in the last 24 hours.")
    try:
        # Calculate the timestamp for 24 hours ago
        time_24_hours_ago = datetime.utcnow() - timedelta(hours=24)

        # Query products created after this timestamp
        recent_products = db.session.query(Product).filter(Product.created_at >= time_24_hours_ago).all()

        total_count = len(recent_products)
        log_debug(f"Recent products retrieved: {recent_products}")

        if recent_products:
            log_info("Products created in the last 24 hours fetched successfully.")
            # Generate a formatted message to include product details
            product_details_str = format_product_list(recent_products)
            email_body = (f"Successfully fetched {total_count} products "
                          f"created in the last 24 hours:\n\n{product_details_str}")

            # Notify success with the formatted product details in the email body
            notify_success("Fetch Recent Products Success", email_body)

            return jsonify({
                "total_count": total_count,
                "products": [product.to_dict() for product in recent_products]
            })
        else:
            log_info("No products found created in the last 24 hours.")
            # Notify that no recent products were found
            notify_success(
                "Fetch Recent Products - No Products Found",
                "No products were created in the last 24 hours."
            )
            return jsonify({
                "total_count": 0,
                "message": "No products found created in the last 24 hours"
            }), 200
    except Exception as e:
        log_error(f"Error fetching recent products: {e}")
        notify_failure("Fetch Recent Products Error", f"Failed to fetch recent products: {e}")
        return jsonify({
            "error": "Could not fetch products created in the last 24 hours",
            "details": str(e)
        }), 500


@app.route('/products', methods=['GET'])
def get_products():
    """
    Retrieves filtered products from the database based on query parameters.

    This route fetches products based on the provided query parameters like brand, type, and model.

    Returns:
        Response: JSON array of filtered products or an error message if invalid input is provided.
    """
    log_info("Starting to fetch products with filters.")

    try:
        # Retrieve query parameters
        brand = request.args.get('brand', default=None, type=str)
        types = request.args.get('type', default=None, type=str)
        model = request.args.get('model', default=None, type=str)

        # Validate input parameters
        validate_string_param(brand, 'brand')
        validate_string_param(types, 'type')
        validate_string_param(model, 'model')

        # Start building the query
        query = db.session.query(Product)

        # Apply filters based on query parameters
        if brand:
            query = query.filter(Product.brand.ilike(f"%{brand}%"))
            log_debug(f"Filtering by brand: {brand}")

        if types:
            query = query.filter(Product.type.ilike(f"%{types}%"))
            log_debug(f"Filtering by type: {types}")

        if model:
            query = query.filter(Product.model.ilike(f"%{model}%"))
            log_debug(f"Filtering by model: {model}")

        # Execute the query
        products = query.all()
        total_count = len(products)
        log_debug(f"Products retrieved: {total_count}")

        if not products:
            filters_str = format_filter_query_params(brand, types, model)
            log_info("No products found with the provided filters.")
            notify_failure(
                "Fetch Products Info",
                f"No products were found with the provided filters.\n\n{filters_str}\n\n"
                "If you believe this is an error, please check your filters or contact support.\n\n"
                "Best regards,\n"
                "Komal"
            )
            return jsonify({"message": "No products found with the provided filters."}), 404

        log_info("Products fetched successfully.")
        products_list_str = format_product_list(products)

        notify_success(
            "Fetch Products Success",
            f"Successfully fetched filtered products:\n\n'Total Count': {total_count}\n\n"
            f"Product Details are: {products_list_str}"

        )
        return jsonify({
            "total_count": total_count,
            "products": [product.to_dict() for product in products]
        })

    except ValueError as ve:
        return log_and_notify_error("Fetch Products", str(ve))

    except SQLAlchemyError as e:
        return handle_database_error("Fetch Products", e)

    except Exception as e:
        return log_and_notify_error("Fetch Products", str(e))


@app.route('/products/uuids', methods=['GET'])
def get_all_product_uuids():
    """
    Retrieves all product UUIDs and checks for duplicates.

    Returns:
        Response: JSON object with the count of UUIDs, list of UUIDs, and any duplicated UUIDs.
    """
    log_info("Fetching all product UUIDs.")

    try:
        # Fetch all products
        products = db.session.query(Product).all()

        # Extract UUIDs and convert them to strings
        product_uuids = [str(product.uuid) for product in products]

        if not product_uuids:
            log_info("No products found.")
            return jsonify({"message": "No products found."}), 404

        # Count UUIDs and find duplicates
        uuid_count = len(product_uuids)
        uuid_counts = {}
        for uuid in product_uuids:
            if uuid in uuid_counts:
                uuid_counts[uuid] += 1
            else:
                uuid_counts[uuid] = 1

        duplicates = {uuid: count for uuid, count in uuid_counts.items() if count > 1}

        # Prepare the UUIDs and duplicates for email notification
        uuids_str = ', '.join(product_uuids)
        duplicates_str = '\n'.join([f"UUID: {uuid}, Count: {count}" for uuid, count in duplicates.items()])

        log_info(f"Fetched product UUIDs: {uuids_str}")
        log_info(f"Duplicate UUIDs found: {duplicates_str}")

        notify_success(
            "Fetch Product UUIDs Success",
            f"Successfully fetched product UUIDs:\n\n{uuids_str}\n\n"
            f"Total UUIDs Count: {uuid_count}\n\n"
            f"Duplicate UUIDs:\n{duplicates_str if duplicates else 'No duplicates found.'}"
        )

        return jsonify({
            "total_uuids_count": uuid_count,
            "uuids": product_uuids,
            "duplicate_uuids": duplicates
        })

    except Exception as e:
        log_error(f"Error fetching product UUIDs: {e}")
        notify_failure("Fetch Product UUIDs Error", f"Failed to fetch product UUIDs: {e}")
        return jsonify({"error": "Could not fetch product UUIDs."}), 500


@app.route('/products/<product_uuid>', methods=['GET'])
def get_product_by_uuid(product_uuid):
    """
    Retrieves a product by its UUID from the database.

    :param product_uuid: UUID of the product
    :return: JSON object of the product if found, otherwise a 404 error
    """
    log_info(f"Request to get product with UUID: {product_uuid}")

    try:
        # Retrieve the product from the database
        product = fetch_product_by_uuid(product_uuid)

        if not product:
            log_error(f"Product with UUID {product_uuid} not found.")
            notify_failure(
                "Product Retrieval Failure",
                f"Product with UUID {product_uuid} was not found in the database.\n\n"
                "Please check the UUID and try again."
            )
            return jsonify({"message": "Product not found"}), 404

        log_info(f"Product with UUID {product_uuid} retrieved successfully.")
        # Prepare product details for the response
        product_details_str, product_details = prepare_product_details(product)

        notify_success(
            "Product Retrieval Success",
            f"Successfully retrieved product with UUID {product_uuid}.\n\n"
            f"Product Details:\n{product_details_str}"
        )

        return jsonify(product_details)

    except SQLAlchemyError as e:
        return handle_database_error("Product Retrieval", e)


@app.route('/create-tables', methods=['POST'])
def create_tables():
    """
    Creates all tables defined in the database models.

    This route initializes the database and creates all tables defined in the models.

    Returns:
        Response: JSON message indicating whether table creation was successful.
    """
    log_info("Starting table creation process.")
    try:
        with app.app_context():
            db.create_all()
        log_info("Tables created successfully.")
        notify_success("Table Creation Success", "Tables created successfully.")
        return jsonify({"message": "Tables created successfully"}), 200
    except Exception as e:
        log_error(f"Error creating tables: {e}")
        notify_failure("Table Creation Error", f"Error creating tables: {e}")
        return jsonify({"error": "Failed to create tables"}), 500


@app.route('/products/filter', methods=['GET'])
def filter_products():
    """
    Filters products based on query parameters.

    This route filters products by type and/or brand based on the provided query parameters.

    Query Parameters:
        type (str): The type of the product to filter by.
        brand (str): The brand of the product to filter by.

    Returns:
        Response: JSON array of filtered products.
    """
    log_info("Starting filter products.")

    # Get query parameters
    product_type = request.args.get('type')
    brand = request.args.get('brand')

    # Format filter query parameters for logging and notification
    filter_params = format_filter_query_params(brand, product_type, None)

    query = db.session.query(Product)

    if product_type:
        log_info(f"Filtering by type: {product_type}")
        query = query.filter_by(type=product_type)
    if brand:
        log_info(f"Filtering by brand: {brand}")
        query = query.filter_by(brand=brand)

    try:
        products = query.all()
        log_debug(f"Filtered products: {products}")

        if not products:
            log_info("No products match the filter criteria.")
            # Notify about no products found
            notify_failure(
                "Filter Products Info",
                f"No products match the filter criteria:\n\n{filter_params}\n\n"
                "Please adjust your filters and try again."
            )
            return jsonify({"message": "No products found matching the filter criteria."}), 404

        log_info("Products filtered successfully.")
        product_list = format_product_list(products)
        product_count = len(products)
        # Prepare detailed content for the email
        plain_text_content = (
            f"Successfully filtered products:\n\nTotal Products Found: \n{product_count}\n\n"
            f"Filter Criteria:\n{filter_params}\n\n"
            f"Total Products Found: \n{product_list}"

        )
        notify_success(
            "Filter Products Success",
            plain_text_content
        )
        return jsonify({
            "total_count": product_count,
            "products": [product.to_dict() for product in products],

        })

    except Exception as e:
        log_error(f"Error filtering products: {e}")
        notify_failure(
            "Filter Products Error",
            f"Error occurred while filtering products:\n\nError Details: {e}\n\n"
            "Please check the request and try again. If the issue persists, contact support."
        )
        return jsonify({"error": "Failed to filter products"}), 500


@app.route('/products', methods=['POST'])
def create_new_product():
    """
    Creates a new product in the database.

    This route creates a new product based on the data provided in the request body.

    Request Body:
        JSON object with product details (uuid, type, brand, model, price, discounts, specs).

    Returns:
        Response: JSON object of the created product, or an error message if the creation fails.
    """
    data = request.json
    log_info(f"Starting product creation with data: {data}.")

    # Fetch valid product details from the database
    valid_product = db.session.query(ValidProductDetails).filter_by(type=data['type'], brand=data['brand']).first()

    # Check if the provided product details are valid
    if not valid_product:
        log_error("Invalid product, type, or brand.")
        notify_failure(
            "Create Product Error",
            "Failed to create a new product due to invalid product details.\n\n"
            f"Provided details:\n"
            f"Type: {data['type']}\n"
            f"Brand: {data['brand']}\n\n"
            "Please ensure the product type and brand are valid and try again.\n\n"
            "If the issue persists, contact support.\n\n"
            "Best regards,\n"
            "The Team"
        )
        return jsonify({"error": "Invalid product, type, or brand"}), 400

    try:
        new_product = Product(
            uuid=data['uuid'],
            type=data['type'],
            brand=data['brand'],
            model=data['model'],
            price=data['price'],
            discounts=data['discounts'],
            specs=data['specs']
        )
        log_debug(f"New product object created: {new_product}")
        db.session.add(new_product)
        db.session.commit()
        log_info(f"Product created successfully with UUID: {new_product.uuid}")

        # Construct product details string for the email
        product_dict = new_product.to_dict()
        product_details = (
            f"Product Details:\n"
            f"UUID: {product_dict['uuid']}\n"
            f"Type: {product_dict['type']}\n"
            f"Brand: {product_dict['brand']}\n"
            f"Model: {product_dict['model']}\n"
            f"Price: {product_dict['price']}\n"
            f"Discounts: {product_dict['discounts']}\n"
            f"Specs: {product_dict['specs']}\n"
            f"Created At: {product_dict['created_at']}\n"
            f"Search Count: {product_dict['search_count']}\n"
        )

        # Notify success with detailed product information
        notify_success(
            "Product Created Successfully",
            f"Product created successfully with UUID: {new_product.uuid}\n\n"
            f"{product_details}\n\n"
            "If you need further assistance or have any questions, please contact support.\n\n"
            "Best regards,\n"
            "The Team"
        )

        return jsonify(new_product.to_dict()), 201

    except Exception as e:
        log_error(f"Error creating product: {e}")
        notify_failure(
            "Create Product Error",
            f"An error occurred while creating a new product:\n\n"
            f"Error Details: {e}\n\n"
            "Please check the request data and database setup.\n\n"
            "If the issue persists, contact support.\n\n"
            "Best regards,\n"
            "Komal"
        )
        return jsonify({"error": "Failed to create product"}), 500


@app.route('/products/<uuid>', methods=['PUT'])
def update_product(uuid):
    """
    Updates an existing product by its UUID.

    This route updates a product using the data provided in the request body.

    Args:
        uuid (str): The UUID of the product to update.

    Request Body:
        JSON object with updated product details (type, brand, model, price, discounts, specs).

    Returns:
        Response: JSON object of the updated product, or an error message if the update fails.
    """
    data = request.json
    log_info(f"Updating product with UUID: {uuid} using data: {data}.")

    # Fetch valid product details from the database
    valid_product = db.session.query(ValidProductDetails).filter_by(
        type=data.get('type'),
        brand=data.get('brand')
    ).first()

    # Check if the provided product details are valid
    if not valid_product:
        log_error("Invalid product, type, or brand.")
        notify_failure(
            "Update Product Error",
            "Invalid product, type, or brand.\n\n"
            "The update request contained invalid product details. Please ensure that the type and brand "
            "are valid and try again."
        )
        return jsonify({"error": "Invalid product, type, or brand"}), 400

    try:
        product = db.session.get(Product, uuid)
        if product:
            log_debug(f"Product before update: {product.to_dict()}")
            product.type = data.get('type', product.type)
            product.brand = data.get('brand', product.brand)
            product.model = data.get('model', product.model)
            product.price = data.get('price', product.price)
            product.discounts = data.get('discounts', product.discounts)
            product.specs = data.get('specs', product.specs)
            db.session.commit()
            log_info(f"Product updated successfully with UUID: {uuid}")

            # Prepare the email content
            product_details = (
                f"Product UUID: {product.uuid}\n"
                f"Type: {product.type}\n"
                f"Brand: {product.brand}\n"
                f"Model: {product.model}\n"
                f"Price: {product.price}\n"
                f"Discounts: {product.discounts}\n"
                f"Specs: {product.specs}\n"
                f"Created At: {product.created_at}\n"
                f"Search Count: {product.search_count}"
            )
            notify_success(
                "Product Updated Successfully",
                f"Product with UUID: {uuid} has been updated successfully.\n\n"
                f"Updated Product Details:\n\n{product_details}"
            )
            return jsonify(product.to_dict()), 200
        else:
            log_info(f"Product with UUID {uuid} not found.")
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_error(f"Error updating product: {e}")
        notify_failure(
            "Update Product Error",
            f"Error occurred while updating product with UUID {uuid}:\n\nError Details: {e}\n\n"
            "Please check the request and try again. If the issue persists, contact support."
        )
        return jsonify({"error": "Failed to update product"}), 500


@app.route('/products/<uuid>', methods=['DELETE'])
def delete_product(uuid):
    """
    Deletes a product from the database by its UUID.

    This route removes a product using its UUID.

    Args:
        uuid (str): The UUID of the product to delete.

    Returns:
        Response: JSON message indicating whether the deletion was successful, or an error message if it failed.
    """
    log_info(f"Deleting product with UUID: {uuid}.")
    try:
        product = db.session.get(Product, uuid)
        if product:
            product_details = product.to_dict()
            db.session.delete(product)
            db.session.commit()
            log_info(f"Product deleted successfully with UUID: {uuid}")

            # Prepare the email content for success
            notify_success(
                "Product Deleted Successfully",
                f"Product with UUID: {uuid} has been deleted from the database.\n\n"
                f"Product Details:\n"
                f"Type: {product_details['type']}\n"
                f"Brand: {product_details['brand']}\n"
                f"Model: {product_details['model']}\n"
                f"Price: {product_details['price']}\n"
                f"Discounts: {product_details['discounts']}\n"
                f"Specs: {product_details['specs']}\n"
                f"Created At: {product_details['created_at']}\n"
                f"Search Count: {product_details['search_count']}\n\n"
                "The product was removed successfully."
            )
            return jsonify({"message": "Product deleted successfully"}), 200
        else:
            log_info(f"Product with UUID {uuid} not found.")

            # Prepare the email content for not found error
            notify_failure(
                "Product Not Found Error",
                f"Attempted to delete product with UUID: {uuid}, but it was not found in the database.\n\n"
                "Please verify the UUID and try again."
            )
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_error(f"Error deleting product: {e}")

        # Prepare the email content for internal server error
        notify_failure(
            "Delete Product Error",
            f"An error occurred while trying to delete product with UUID: {uuid}.\n\n"
            f"Error Details: {e}\n\n"
            "Please check the request and try again. If the issue persists, contact support."
        )
        return jsonify({"error": "Failed to delete product"}), 500


# --------------------------------------------- E_Commerce Project (ending) --------------------------------------------

if __name__ == '__main__':
    app.run(port=Config.PORT, debug=True)
