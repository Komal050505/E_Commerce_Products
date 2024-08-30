"""
This Module is used to perform CRUD operations on e-commerce products

"""

import json
from flask import Flask, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from db_connections.configurations import DATABASE_URL, Config
from email_setup.email_operations import notify_success, notify_failure
from user_models.tables import db, Product, ValidProductDetails, User_Registration_Form, Cart
from logging_package.logging_utility import log_info, log_error, log_debug
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from users_utility.utilities import validate_string_param

# Create Flask app instance
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Initialize SQLAlchemy with the Flask app
db.init_app(app)

# --------------------------------------------- User_Registration Project (starting) -----------------------------------

"""
This codes is for performing actions with involvement of the actual e-commerce users..... [FOR E-COMMERCE USERS]
"""


@app.route('/cart/add', methods=['POST'])
def add_product_to_cart():
    """
    Adds a product to the user's cart.

    JSON Body:
        username (str): The username of the user adding the product.
        product_uuid (str): The UUID of the product to add.
        quantity (int): The quantity of the product to add.

    Returns:
        Response: JSON object with a success message or error details.
    """
    data = request.get_json()
    username = data.get('username')
    product_uuid = data.get('product_uuid')

    # Corrected line to avoid TypeError
    quantity = int(data.get('quantity', 1)) if data.get('quantity') is not None else 1

    log_info(f"Attempting to add product {product_uuid} to cart for user {username} with quantity {quantity}.")

    try:
        user = db.session.query(User_Registration_Form).filter_by(name=username).first()
        product = db.session.query(Product).filter_by(uuid=product_uuid).first()

        if not user:
            log_error(f"User '{username}' not found.")
            notify_failure("Add to Cart Error", f"User '{username}' not found.")
            return jsonify({"error": "User not found"}), 404

        if not product:
            log_error(f"Product with UUID '{product_uuid}' not found.")
            notify_failure("Add to Cart Error", f"Product with UUID '{product_uuid}' not found.")
            return jsonify({"error": "Product not found"}), 404

        # Checks if the item is already in the cart or not
        existing_cart_item = db.session.query(Cart).filter_by(user_name=username, product_uuid=product_uuid).first()

        if existing_cart_item:
            # If item exists, update the quantity
            existing_cart_item.quantity += quantity
            db.session.commit()
        else:
            # If item does not exist, it will create a new cart item
            cart_item = Cart(user_name=username, product_uuid=product_uuid, quantity=quantity)
            db.session.add(cart_item)
            db.session.commit()

        # Fetch updated cart items for the user
        cart_items = db.session.query(Cart).filter_by(user_name=username).all()
        total_items = sum(item.quantity for item in cart_items)

        log_info(f"Product '{product_uuid}' added to cart for user '{username}' successfully.")

        product_dict = product.to_dict()
        product_details = (
            f"Product details: UUID={product_dict['uuid']}, Type={product_dict['type']}, "
            f"Brand={product_dict['brand']}, Model={product_dict['model']}, Price={product_dict['price']}, "
            f"Discounts={product_dict['discounts']}, Specs={product_dict['specs']}, "
            f"Created At={product_dict['created_at']}, "
            f"Search Count={product_dict['search_count']}"
        )

        notify_success("Add to Cart Success",
                       f"Product with uuid:\n'{product_uuid}' \n\nProduct Details : \n\n({product_details}) \n\n"
                       f"Added to cart successfully. \n\nFor user: \n'{username}'."
                       f" \n\nTotal items in cart: {total_items}.")

        return jsonify({
            "message": "Product added to cart successfully",
            "product_details": product_dict,
            "total_items_in_cart": total_items
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        log_error(f"Database error while adding product to cart: {e}")
        notify_failure("Add to Cart Error", f"Database error while adding product to cart: {e}")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        log_error(f"Error adding product to cart: {e}")
        notify_failure("Add to Cart Error", f"Failed to add product to cart: {e}")
        return jsonify({"error": "Could not add product to cart."}), 500


@app.route('/cart/remove_quantity', methods=['POST'])
def remove_quantity_from_cart():
    """
    Removes a specific quantity of a product from the user's cart using URL parameters.
    """
    # Extract parameters from query string
    username = request.args.get('username')
    product_uuid = request.args.get('product_uuid')
    quantity_to_remove = request.args.get('quantity', type=int, default=1)

    log_info(
        f"Attempting to remove quantity {quantity_to_remove} of product {product_uuid} from cart for user {username}.")

    try:
        user = db.session.query(User_Registration_Form).filter_by(name=username).first()
        if not user:
            log_error(f"User '{username}' not found.")
            notify_failure("Remove Quantity from Cart Error", f"User '{username}' not found.")
            return jsonify({"error": "User not found"}), 404

        cart_item = db.session.query(Cart).filter_by(user_name=username, product_uuid=product_uuid).first()
        if not cart_item:
            log_error(f"Product with UUID '{product_uuid}' not found in cart for user '{username}'.")
            notify_failure("Remove Quantity from Cart Error",
                           f"Product with UUID '{product_uuid}' not found in cart for user '{username}'.")
            return jsonify({"error": "Product not found in cart"}), 404

        if quantity_to_remove > cart_item.quantity:
            log_error(
                f"Quantity to remove {quantity_to_remove} exceeds current quantity {cart_item.quantity} "
                f"for product {product_uuid}.")
            notify_failure("Remove Quantity from Cart Error",
                           f"Quantity to remove exceeds current quantity for product '{product_uuid}'.")
            return jsonify({"error": "Quantity to remove exceeds current quantity"}), 400

        # Remove or update the cart item
        if cart_item.quantity > quantity_to_remove:
            cart_item.quantity -= quantity_to_remove
            db.session.commit()
        else:
            db.session.delete(cart_item)
            db.session.commit()

        # Fetch the updated product details
        product = db.session.query(Product).filter_by(uuid=product_uuid).first()
        if not product:
            log_error(f"Product with UUID '{product_uuid}' not found.")
            return jsonify({"error": "Product details could not be fetched."}), 404

        product_dict = product.to_dict()
        product_details = (
            f"Product details: UUID={product_dict['uuid']}, Type={product_dict['type']}, "
            f"Brand={product_dict['brand']}, Model={product_dict['model']}, Price={product_dict['price']}, "
            f"Discounts={product_dict['discounts']}, Specs={product_dict['specs']}, "
            f"Created At={product_dict['created_at']}, "
            f"Search Count={product_dict['search_count']}"
        )

        cart_items = db.session.query(Cart).filter_by(user_name=username).all()
        total_items = sum(item.quantity for item in cart_items)

        log_info(
            f"Quantity {quantity_to_remove} of product '{product_uuid}' removed from cart for "
            f"user '{username}' successfully.")

        notify_success("Remove Quantity from Cart Success",
                       f"Quantity {quantity_to_remove} of product \n\n '{product_uuid}' and \n\n "
                       f"Product Details: \n\n{product_details}\n\n"
                       f"Removed from cart successfully. \n\nFor user \n'{username}'.\n\n"
                       f"Total items left in cart: {total_items}.")

        return jsonify({
            "message": "Quantity removed from cart successfully",
            "total_items_in_cart": total_items,
            "product_details": product_dict
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        log_error(f"Database error while removing quantity from cart: {e}")
        notify_failure("Remove Quantity from Cart Error",
                       f"Database error while removing quantity from cart: {e}")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        log_error(f"Error removing quantity from cart: {e}")
        notify_failure("Remove Quantity from Cart Error", f"Failed to remove quantity from cart: {e}")
        return jsonify({"error": "Could not remove quantity from cart."}), 500


@app.route('/purchase-single-cart-product', methods=['POST'])
def purchase_single_cart_product():
    """
    Purchases a single product from the user's cart.

    Query Parameters:
        username (str): The username of the user making the purchase.
        product_uuid (str): The UUID of the product to purchase.

    Returns:
        Response: JSON object with a success message, product details, and cost.
    """
    username = request.args.get('username')
    product_uuid = request.args.get('product_uuid')

    log_info(f"Attempting to purchase product {product_uuid} from the cart for user {username}.")

    try:
        # Fetching the user details from the database
        user = db.session.query(User_Registration_Form).filter_by(name=username).first()

        if not user:
            log_error(f"User '{username}' not found.")
            notify_failure("Purchase Cart Error", f"User '{username}' not found.")
            return jsonify({"error": "User not found"}), 404

        # Fetching the specific cart item for the user from cart
        cart_item = db.session.query(Cart).filter_by(user_name=username, product_uuid=product_uuid).first()

        if not cart_item:
            log_info(f"No item with UUID '{product_uuid}' in the cart for user '{username}'.")
            notify_failure("Purchase Cart Error",
                           f"No item with UUID '{product_uuid}' in the cart for user '{username}'.")
            return jsonify({"error": "Product not found in the cart"}), 404

        # Fetching the product details from product table in database
        product = db.session.query(Product).filter_by(uuid=product_uuid).first()
        if not product:
            log_error(f"Product with UUID '{product_uuid}' not found in the database.")
            notify_failure("Purchase Cart Error", f"Product with UUID '{product_uuid}' not found in the database.")
            return jsonify({"error": f"Product with UUID '{product_uuid}' not found"}), 404

        # Calculating the cost here
        cost = product.price * cart_item.quantity

        # Removing the cart item after purchase
        db.session.delete(cart_item)
        db.session.commit()

        log_info(f"Product '{product_uuid}' purchased successfully for user '{username}'. Cost: {cost}.")

        # Sending success email with detailed information about the purchase
        notify_success(
            "Purchase Single Product From Cart Success",
            f"Single Product '{product_uuid}' from the cart has been purchased successfully.\n\n"
            f"For user '{username}'.\n\n"
            f"Product details:\n"
            f"UUID: {product.uuid}\n"
            f"Type: {product.type}\n"
            f"Brand: {product.brand}\n"
            f"Model: {product.model}\n"
            f"Price: {product.price}\n"
            f"Quantity: {cart_item.quantity}\n"
            f"Total cost: {cost}\n"
        )

        return jsonify({
            "message": "Single Purchase completed successfully",
            "product": {
                "uuid": product.uuid,
                "type": product.type,
                "brand": product.brand,
                "model": product.model,
                "price": product.price,
                "quantity": cart_item.quantity,
                "total_cost": cost
            }
        }), 200
    # This is for Database error
    except SQLAlchemyError as e:
        db.session.rollback()
        log_error(f"Database error while purchasing cart: {e}")
        notify_failure("Single Product Purchase Cart Error",
                       f"Database error while purchasing single product from cart: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    # This is for Exception error
    except Exception as e:
        log_error(f"Error purchasing single product: {e}")
        notify_failure("Single Product Purchase Cart Error", f"Failed to purchase product: {e}")
        return jsonify({"error": "Could not complete single product purchase."}), 500


@app.route('/purchase-all-cart-products', methods=['POST'])
def purchase_all_cart_products():
    """
    Purchases all products in the user's cart.

    Query Parameters:
        username (str): The username of the user making the purchase.

    Returns:
        Response: JSON object with a success message, total cost, and the number of products.
    """
    username = request.args.get('username')

    log_info(f"Attempting to purchase all products in the cart for user {username}.")

    try:
        # Fetch the user details from the database
        user = db.session.query(User_Registration_Form).filter_by(name=username).first()

        if not user:
            log_error(f"User '{username}' not found.")
            notify_failure("Purchase Cart Error", f"User '{username}' not found.")
            return jsonify({"error": "User not found"}), 404

        # Fetch all cart items for the user
        cart_items = db.session.query(Cart).filter_by(user_name=username).all()

        if not cart_items:
            log_info(f"No items in the cart for user '{username}'.")
            notify_failure("Purchase Cart Error", f"No items in the cart for user '{username}'.")
            return jsonify({"error": "No items in the cart"}), 404

        total_cost = 0.0
        total_quantity = 0
        purchased_items = []

        for item in cart_items:
            product = db.session.query(Product).filter_by(uuid=item.product_uuid).first()
            if product:
                cost = product.price * item.quantity
                total_cost += cost
                total_quantity += item.quantity
                purchased_items.append({
                    "uuid": product.uuid,
                    "type": product.type,
                    "brand": product.brand,
                    "model": product.model,
                    "price": product.price,
                    "quantity": item.quantity,
                    "total_cost": cost
                })
            else:
                log_error(f"Product with UUID '{item.product_uuid}' not found in the database.")
                notify_failure("Purchase Cart Error", f"Product with UUID '{item.product_uuid}'"
                                                      f" not found in the database.")
                return jsonify({"error": f"Product with UUID '{item.product_uuid}' not found"}), 404

        # Clear cart after purchase
        db.session.query(Cart).filter_by(user_name=username).delete()
        db.session.commit()

        log_info(f"All products purchased successfully for user '{username}'. Total cost: {total_cost}."
                 f" Total quantity: {total_quantity}.")

        # Send success email with detailed information about the purchase
        notify_success(
            "Purchase Cart Success",
            f"All products in the cart have been purchased successfully \n\nFor user \n'{username}'.\n\n"
            f"Total cost: {total_cost}\n\n"
            f"Total number of products: {len(cart_items)}\n\n"
            f"Total quantity of all items: {total_quantity}\n\n"
            f"Purchased items: \n{purchased_items}"
        )

        return jsonify({
            "message": "Purchase completed successfully",
            "total_cost": total_cost,
            "total_products": len(cart_items),
            "total_quantity": total_quantity,
            "purchased_items": purchased_items
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        log_error(f"Database error while purchasing cart: {e}")
        notify_failure("Purchase Cart Error", f"Database error while purchasing cart: {e}")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        log_error(f"Error purchasing cart: {e}")
        notify_failure("Purchase Cart Error", f"Failed to purchase cart: {e}")
        return jsonify({"error": "Could not complete purchase."}), 500


@app.route('/most-purchased-product', methods=['GET'])
def most_purchased_product():
    """
    Retrieves the most purchased product across all users.

    Returns:
        Response: JSON object with the most purchased product details or error details.
    """
    log_info("Attempting to retrieve the most purchased product across all users.")

    try:
        # Aggregate the total quantity for each product across all users
        result = (db.session.query(Cart.product_uuid, db.func.sum(Cart.quantity).label('total_quantity')).
                  group_by(Cart.product_uuid).order_by(db.desc('total_quantity')).first())

        if not result:
            log_error("No products found in any cart.")
            notify_failure("Most Purchased Product Error", "No products found in any cart.")
            return jsonify({"error": "No products found in any cart."}), 404

        product_uuid = result.product_uuid
        total_quantity = result.total_quantity

        # Fetch product details
        product = db.session.query(Product).filter_by(uuid=product_uuid).first()

        if not product:
            log_error(f"Product with UUID '{product_uuid}' not found.")
            notify_failure(f"Most Purchased Product Error", f"Product with UUID '{product_uuid}' not found.")
            return jsonify({"error": f"Product with UUID '{product_uuid}' not found."}), 404

        product_dict = product.to_dict()
        product_details = (
            f"Product details: \nUUID={product_dict['uuid']}, Type={product_dict['type']}, "
            f"Brand={product_dict['brand']}, Model={product_dict['model']}, Price={product_dict['price']}, "
            f"Discounts={product_dict['discounts']}, Specs={product_dict['specs']}, "
            f"Created At={product_dict['created_at']}, "
            f"Search Count={product_dict['search_count']}"
        )

        log_info(f"Most purchased product across all users is '{product_uuid}' with total quantity {total_quantity}.")
        notify_success("Most Purchased Product Success",
                       f"Most purchased product across all users:\n\n"
                       f"\n{product_details}\n\n"
                       f"Total Quantity Purchased: {total_quantity}")

        return jsonify({
            "product_details": product_dict,
            "total_quantity": total_quantity
        }), 200

    except SQLAlchemyError as e:
        log_error(f"Database error while retrieving the most purchased product across all users: {e}")
        notify_failure("Most Purchased Product Error",
                       f"Database error while retrieving the most purchased product: {e}")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        log_error(f"Error retrieving the most purchased product across all users: {e}")
        notify_failure("Most Purchased Product Error",
                       f"Failed to retrieve the most purchased product: {e}")
        return jsonify({"error": "Could not retrieve the most purchased product."}), 500


@app.route('/clear-cart', methods=['POST'])
def clear_users_cart():
    """
    Clears the cart for a specified user.

    JSON Body:
        username (str): The username of the user whose cart is to be cleared.

    Returns:
        Response: JSON object with a success message or error details.
    """
    data = request.get_json()
    username = data.get('username')

    log_info(f"Attempting to clear cart for user '{username}'.")

    try:
        # Validate the user
        user = db.session.query(User_Registration_Form).filter_by(name=username).first()

        if not user:
            log_error(f"User '{username}' not found.")
            notify_failure("Clear Cart Error", f"User '{username}' not found.")
            return jsonify({"error": "User not found"}), 404

        # Clear the cart for the user
        db.session.query(Cart).filter_by(user_name=username).delete()
        db.session.commit()

        log_info(f"Cart cleared for user '{username}' successfully.")
        notify_success(
            "Clear Cart Success",
            f"Cart cleared successfully for user '{username}'."
        )

        return jsonify({"message": f"Cart cleared for user '{username}'."}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        log_error(f"Database error while clearing cart for user '{username}': {e}")
        notify_failure("Clear Cart Error", f"Database error while clearing cart for user '{username}': {e}")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        log_error(f"Error clearing cart for user '{username}': {e}")
        notify_failure("Clear Cart Error", f"Failed to clear cart for user '{username}': {e}")
        return jsonify({"error": "Could not clear cart."}), 500


# --------------------------------------------- User_Registration Project (ending) -------------------------------------
# **********************************************************************************************************************
# **********************************************************************************************************************
# **********************************************************************************************************************
# --------------------------------------------- E_Commerce Project (starting) ------------------------------------------

"""
This codes is for performing actions without involvement of the actual e-commerce users... [ONLY FOR DEVELOPERS]
"""


@app.route('/products/most_searched', methods=['GET'])
def get_most_searched_products():
    """
    Retrieves products sorted by their search count in descending order.

    This route fetches the products with the highest search counts first.

    Returns:
        Response: JSON array of products sorted by search count.
    """
    log_info("Fetching most searched products.")

    try:
        # Query to fetch products sorted by search_count in descending order
        most_searched_products = db.session.query(Product).order_by(Product.search_count.desc()).all()

        if not most_searched_products:
            log_info("No products found.")
            return jsonify({"message": "No products found."}), 404

        products_list = [product.to_dict() for product in most_searched_products]

        log_info("Most searched products fetched successfully.")
        notify_success("Fetch Most Searched Products Success",
                       f"Successfully fetched most searched products:\n\n"
                       f"{''.join([str(product) for product in products_list])}")
        return jsonify(products_list)

    except Exception as e:
        log_error(f"Error fetching most searched products: {e}")
        notify_failure("Fetch Most Searched Products Error", f"Failed to fetch most searched products: {e}")
        return jsonify({"error": "Could not fetch most searched products."}), 500


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

    Query Parameters:
        start_date (str): The start date of the clearance sale in YYYY-MM-DD format.
        cutoff_date (str): The cutoff date in YYYY-MM-DD format. Products created before this date will have discounts applied.
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
            error_message = f"Invalid date format: start_date: {start_date_str}, cutoff_date: {cutoff_date_str}. Expected YYYY-MM-DD."
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
            error_message = f"Invalid discount percentage: {discount_percentage_str}. Must be a number between 0 and 100."
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

        log_debug(f"Search results: {search_results}")

        if not search_results:
            log_info("No products match the search query.")
            notify_success("Product Search Success",
                           "No products found matching the search criteria.")
            return jsonify({"message": "No products found matching your search criteria."}), 200

        # Update search count for each matching product
        for product in search_results:
            product.search_count += 1
        db.session.commit()

        # Successfully found matching products
        log_info("Products found matching the search criteria.")
        product_details = "\n".join([f"Product UUID: {product.uuid}\n"
                                     f"Type: {product.type}\n"
                                     f"Brand: {product.brand}\n"
                                     f"Model: {product.model}\n"
                                     f"Price: {product.price}\n"
                                     f"Discounts: {product.discounts}\n"
                                     f"Specs: {product.specs}\n"
                                     f"Created At: {product.created_at}\n"
                                     f"Search Count: {product.search_count}\n"
                                     for product in search_results])
        email_body = (f"Successfully found {len(search_results)} products matching the search criteria:\n\n"
                      f"{product_details}")

        # Notify success with the formatted product details in the email body
        notify_success("Product Search Success", email_body)
        return jsonify([product.to_dict() for product in search_results]), 200

    except Exception as e:
        # Log the error and send a failure notification email
        log_error(f"Error during product search: {e}")
        notify_failure("Product Search Error", f"Error during product search: {e}")
        return jsonify({"error": "Search failed"}), 500


@app.route('/products/latest', methods=['GET'])
def get_latest_products():
    """
    Retrieves the latest products based on their creation timestamp.

    This route fetches products ordered by the most recent creation time.

    Returns:
        Response: JSON array of the latest products.
    """
    log_info("Fetching latest products.")
    try:
        latest_products = db.session.query(Product).order_by(desc(Product.created_at)).all()
        log_debug(f"Latest products retrieved: {latest_products}")

        if not latest_products:
            log_info("No latest products found.")
            # Notify success with no products found
            notify_success(
                "Fetch Latest Products Success",
                "Successfully fetched latest products, but no products were found."
            )
            return jsonify([])  # Return an empty list if no products are found

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
             for product in latest_products]
        )

        log_info("Latest products fetched successfully.")
        # Notify success with detailed product information
        notify_success(
            "Fetch Latest Products Success",
            f"Successfully fetched the latest products:\n\n{products_list}"
        )
        return jsonify([product.to_dict() for product in latest_products])
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

    This route fetches products with discounts, ordered by the most recent creation time.

    Returns:
        Response: JSON array of the latest discounted products.
    """
    log_info("Fetching latest discounted products.")
    try:
        # Query for latest discounted products
        latest_discounted_products = (
            db.session.query(Product)
            .filter(Product.discounts > 11)
            .order_by(desc(Product.created_at))
            .all()
        )

        log_debug(f"Latest discounted products retrieved: {latest_discounted_products}")

        if not latest_discounted_products:
            log_info("No latest discounted products found.")
            # Notify success with no products found
            notify_success(
                "Fetch Latest Discounted Products Success",
                "Successfully fetched latest discounted products, but no products were found."
            )
            return jsonify([])  # Return an empty list if no products are found

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
             for product in latest_discounted_products]
        )

        log_info("Latest discounted products fetched successfully.")
        # Notify success with detailed product information
        notify_success(
            "Fetch Latest Discounted Products Success",
            f"Successfully fetched the latest discounted products:\n\n{products_list}"
        )
        return jsonify([product.to_dict() for product in latest_discounted_products])
    except Exception as e:
        log_error(f"Error fetching latest discounted products: {e}")
        notify_failure(
            "Fetch Latest Discounted Products Error",
            f"Failed to fetch the latest discounted products due to an error.\n\nError Details: {e}"
        )
        return jsonify({"error": "Could not fetch latest discounted products"}), 500


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
        discounted_products = db.session.query(Product).order_by(desc(Product.discounts)).all()
        log_debug(f"Products sorted by discount retrieved: {discounted_products}")

        if discounted_products:
            log_info("Products sorted by discount fetched successfully.")
            # Generate a formatted message to include product details
            product_details = "\n".join([f"Product UUID: {product.uuid}\n"
                                         f"Type: {product.type}\n"
                                         f"Brand: {product.brand}\n"
                                         f"Model: {product.model}\n"
                                         f"Price: {product.price}\n"
                                         f"Discounts: {product.discounts}\n"
                                         f"Specs: {product.specs}\n"
                                         f"Created At: {product.created_at}\n"
                                         f"Search Count: {product.search_count}\n"
                                         for product in discounted_products])
            email_body = (f"Successfully fetched the following products "
                          f"sorted by discount:\n\n{product_details}")

            # Notify success with the formatted product details in the email body
            notify_success("Fetch Products by Discount Success", email_body)

            return jsonify([product.to_dict() for product in discounted_products])
        else:
            log_info("No products with discounts found.")
            # Notify that no discounted products were found
            notify_success(
                "Fetch Products by Discount - No Products Found",
                "No products with discounts found."
            )
            return jsonify({"error": "No discounted products found"}), 404
    except Exception as e:
        log_error(f"Error fetching products sorted by discount: {e}")
        notify_failure("Fetch Products by Discount Error", f"Failed to fetch products sorted by discount: {e}")
        return jsonify({"error": "Could not fetch products sorted by discount"}), 500


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

        if not products:
            log_info("No products found in the specified price range.")
            # Notify success with no products found
            notify_success(
                "Filter Products by Price Range Success",
                "Successfully filtered products by price range, but no products were found."
            )
            return jsonify([])  # Return an empty list if no products are found

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
             for product in products]
        )

        log_info("Products filtered by price range successfully.")
        # Notify success with detailed product information
        notify_success(
            "Filter Products by Price Range Success",
            f"Successfully filtered products by price range:\n\n{products_list}"
        )
        return jsonify([product.to_dict() for product in products])
    except Exception as e:
        log_error(f"Error filtering products by price range: {e}")
        notify_failure(
            "Filter Products by Price Range Error",
            f"Failed to filter products by price range due to an error.\n\nError Details: {e}"
        )
        return jsonify({"error": "Failed to filter products by price range"}), 500


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

        log_debug(f"Recent products retrieved: {recent_products}")

        if recent_products:
            log_info("Products created in the last 24 hours fetched successfully.")
            # Generate a formatted message to include product details
            product_details = "\n".join([f"Product UUID: {product.uuid}\n"
                                         f"Type: {product.type}\n"
                                         f"Brand: {product.brand}\n"
                                         f"Model: {product.model}\n"
                                         f"Price: {product.price}\n"
                                         f"Discounts: {product.discounts}\n"
                                         f"Specs: {product.specs}\n"
                                         f"Created At: {product.created_at}\n"
                                         f"Search Count: {product.search_count}\n"
                                         for product in recent_products])
            email_body = (f"Successfully fetched the following products "
                          f"created in the last 24 hours:\n\n{product_details}")

            # Notify success with the formatted product details in the email body
            notify_success("Fetch Recent Products Success", email_body)

            return jsonify([product.to_dict() for product in recent_products])
        else:
            log_info("No products found created in the last 24 hours.")
            # Notify that no recent products were found
            notify_success(
                "Fetch Recent Products - No Products Found",
                "No products were created in the last 24 hours."
            )
            return jsonify({"message": "No products found created in the last 24 hours"}), 200
    except Exception as e:
        log_error(f"Error fetching recent products: {e}")
        notify_failure("Fetch Recent Products Error", f"Failed to fetch recent products: {e}")
        return jsonify({"error": "Could not fetch products created in the last 24 hours"}), 500


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
        if brand is not None and not brand.strip():
            log_info("Invalid input: brand parameter is empty.")
            notify_failure(
                "Fetch Products Error",
                "Failed to fetch products due to invalid brand parameter.\n\n"
                "The brand parameter is either empty or invalid. Please provide a valid brand parameter and try "
                "again.\n\n"
                "If you need further assistance, contact support.\n\n"
                "Best regards,\n"
                "Komal"
            )
            return jsonify({"error": "Invalid brand parameter."}), 400

        if types is not None and not types.strip():
            log_info("Invalid input: type parameter is empty.")
            notify_failure(
                "Fetch Products Error",
                "Failed to fetch products due to invalid type parameter.\n\n"
                "The type parameter is either empty or invalid. Please provide a valid type parameter and try "
                "again.\n\n"
                "If you need further assistance, contact support.\n\n"
                "Best regards,\n"
                "Komal"
            )
            return jsonify({"error": "Invalid type parameter."}), 400

        if model is not None and not model.strip():
            log_info("Invalid input: model parameter is empty.")
            notify_failure(
                "Fetch Products Error",
                "Failed to fetch products due to invalid model parameter.\n\n"
                "The model parameter is either empty or invalid. Please provide a valid model parameter and try "
                "again.\n\n"
                "If you need further assistance, contact support.\n\n"
                "Best regards,\n"
                "Komal"
            )
            return jsonify({"error": "Invalid model parameter."}), 400

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
        log_debug(f"Products retrieved: {products}")

        if not products:
            log_info("No products found with the provided filters.")
            notify_failure(
                "Fetch Products Info",
                "No products were found with the provided filters.\n\n"
                f"Filters used:\n"
                f"Brand: {brand}\n"
                f"Type: {types}\n"
                f"Model: {model}\n\n"
                "If you believe this is an error, please check your filters or contact support.\n\n"
                "Best regards,\n"
                "Komal"
            )
            return jsonify({"message": "No products found with the provided filters."}), 404

        log_info("Products fetched successfully.")

        products_list = "\n".join(
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

        plain_text_content = (
            "Successfully fetched filtered products:\n\n"
            f"{products_list}"
        )

        notify_success(
            "Fetch Products Success",
            plain_text_content
        )
        return jsonify([product.to_dict() for product in products])

    except SQLAlchemyError as e:
        log_error(f"Database error occurred while fetching products: {e}")
        notify_failure(
            "Fetch Products Error",
            f"Failed to fetch products due to a database error:\n\nError Details: {e}\n\n"
            "Please check the database and try again. If the issue persists, contact support.\n\n"
            "Best regards,\n"
            "Komal"
        )
        return jsonify({"error": "Could not fetch products due to a database error."}), 500

    except Exception as e:
        log_error(f"Error fetching products: {e}")
        notify_failure(
            "Fetch Products Error",
            f"Failed to fetch products:\n\nError Details: {e}\n\n"
            "Please check the request and try again. If the issue persists, contact support.\n\n"
            "Best regards,\n"
            "Komal"
        )
        return jsonify({"error": "Could not fetch products."}), 500


@app.route('/products/<uuid>', methods=['GET'])
def get_product_by_uuid(uuid):
    """
    Retrieves a specific product by its UUID.

    This route fetches a product based on the provided UUID.

    Args:
        uuid (str): The UUID of the product to retrieve.

    Returns:
        Response: JSON object of the product if found, or an error message if the product doesn't exist.
    """
    log_info(f"Fetching product with UUID: {uuid}")
    try:
        product = db.session.get(Product, uuid)
        log_debug(f"Product retrieved: {product}")

        if product:
            # Prepare detailed content for the email
            product_details = (
                f"Product UUID: {product.uuid}\n"
                f"Type: {product.type}\n"
                f"Brand: {product.brand}\n"
                f"Model: {product.model}\n"
                f"Price: {product.price}\n"
                f"Discounts: {product.discounts}\n"
                f"Specs: {product.specs}\n"
                f"Created At: {product.created_at}\n"
                f"Search Count: {product.search_count}\n"
            )
            notify_success(
                "Fetch Product Success",
                f"Successfully retrieved product with UUID: {uuid}.\n\n"
                f"Product Details:\n\n{product_details}"
            )
            return jsonify(product.to_dict())
        else:
            log_info(f"Product with UUID {uuid} not found.")
            notify_failure(
                "Fetch Product Info",
                f"Product with UUID: {uuid} was not found.\n\n"
                "The requested product does not exist in the database.\n\n"
                "If you believe this is an error, please verify the UUID or contact support.\n\n"
                "Best regards,\n"
                "Komal"
            )
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_error(f"Error fetching product by UUID: {e}")
        notify_failure(
            "Fetch Product Error",
            f"Failed to fetch product with UUID: {uuid}.\n\n"
            f"Error Details: {e}\n\n"
            "Please check the request and try again. If the issue persists, contact support.\n\n"
            "Best regards,\n"
            "Komal"
        )
        return jsonify({"error": "Could not fetch product"}), 500


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
    product_type = request.args.get('type')
    brand = request.args.get('brand')
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
                "No products match the filter criteria provided. Please adjust your filters and try again."
            )
            return jsonify({"message": "No products found matching the filter criteria."}), 404

        log_info("Products filtered successfully.")
        # Prepare detailed content for the email
        product_list = "\n\n".join(
            [f"Product UUID: {product.uuid}\nType: {product.type}\nBrand: {product.brand}\n"
             f"Model: {product.model}\nPrice: {product.price}\nDiscounts: {product.discounts}\n"
             f"Specs: {product.specs}\nCreated At: {product.created_at}\nSearch Count: {product.search_count}"
             for product in products]
        )
        plain_text_content = f"Successfully filtered products:\n\n{product_list}"
        notify_success(
            "Filter Products Success",
            plain_text_content
        )
        return jsonify([product.to_dict() for product in products])

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
