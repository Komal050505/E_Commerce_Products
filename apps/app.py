"""
This Module is used to perform CRUD operations on e-commerce products

"""

import json
from flask import Flask, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from db_connections.configurations import DATABASE_URL
from email_setup.email_operations import notify_success, notify_failure
from user_models.tables import db, Product, ValidProductDetails
from logging_package.logging_utility import log_info, log_error, log_debug
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from users_utility.utilities import validate_string_param

# Create Flask app instance
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Initialize SQLAlchemy with the Flask app
db.init_app(app)


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
        most_searched_products = db.session.query(Product).order_by(desc(Product.search_count)).all()

        if not most_searched_products:
            log_info("No products found.")
            return jsonify({"message": "No products found."}), 404

        log_info("Most searched products fetched successfully.")
        # Prepare plain text content for the email
        products_list = "\n".join(
            [str(product.to_dict()) for product in most_searched_products]
        )
        plain_text_content = f"Successfully fetched most searched products:\n\n{products_list}"
        notify_success("Fetch Most Searched Products Success", plain_text_content)

        return jsonify([product.to_dict() for product in most_searched_products])

    except Exception as e:
        log_error(f"Error fetching most searched products: {e}")
        notify_failure("Fetch Most Searched Products Error", f"Failed to fetch most searched products: {e}")
        return jsonify({"error": "Could not fetch most searched products."}), 500


@app.route('/products/count', methods=['GET'])
def get_products_count():
    """
    Fetch the count of products in stock based on type, brand, or model, with support for case-sensitive and partial
    matching. Also, includes detailed product information in email notifications.

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

        # validation for query parameters

        try:
            validate_string_param(product_type, "type")
            validate_string_param(brand, "brand")
            validate_string_param(model, "model")
        except ValueError as ve:
            log_error(str(ve))
            notify_failure("Product Count Error", str(ve))
            return jsonify({"error": str(ve)}), 400

        conditions = []
        if product_type:
            conditions.append(Product.type.ilike(product_type))  # using i-like() for Case-sensitive match

        if brand:
            conditions.append(Product.brand.ilike(brand))
        if model:
            conditions.append(Product.model.ilike(model))

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

        notify_success("Product Count Success",
                       f"Product count retrieved successfully: {count}\n\nProduct Details: {product_details}")

        return jsonify({
            "count": count,
            "message": "Product count retrieved successfully.",
            "products": product_details
        }), 200

    except SQLAlchemyError as e:
        log_error(f"Database error occurred: {e}")
        notify_failure("Product Count Error", f"Database error occurred: {e}")
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        log_error(f"An unexpected error occurred: {e}")
        notify_failure("Product Count Error", f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500


@app.route('/products/clearance_sale', methods=['PATCH'])
def clearance_sale():
    """
    Applies a discount to old stock based on the provided cutoff date and discount percentage, valid for 5 days.

    Query Parameters: - start_date (str): The start date of the clearance sale in YYYY-MM-DD format. - cutoff_date (
    str): The cutoff date in YYYY-MM-DD format. Products created before this date will have discounts applied. -
    discount_percentage (float): The discount percentage to apply to the old products.

    Returns:
        JSON: A JSON object with the number of products updated and a success message.
        HTTP Status Codes:
            - 200 OK: Discounts applied successfully.
            - 400 Bad Request: Invalid date format or missing parameters.
            - 500 Internal Server Error: Database or server errors.
    """
    log_info("Starting clearance sale for old stock.")
    try:
        start_date_str = request.args.get('start_date')
        cutoff_date_str = request.args.get('cutoff_date')
        discount_percentage_str = request.args.get('discount_percentage')

        if not start_date_str or not cutoff_date_str or not discount_percentage_str:
            return jsonify({"error": "start_date, cutoff_date, and discount_percentage parameters are required."}), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            cutoff_date = datetime.strptime(cutoff_date_str, '%Y-%m-%d')
        except ValueError:
            log_error(f"Invalid date format: start_date: {start_date_str}, cutoff_date: {cutoff_date_str}")
            return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

        end_date = start_date + timedelta(days=10)

        # Checks if the current date is within the 10-day sale period
        if not (start_date <= datetime.now() <= end_date):
            log_info("Clearance sale is not active.")
            return jsonify({"message": "Clearance sale is not active at this time."}), 400

        try:
            discount_percentage = float(discount_percentage_str)
            if discount_percentage < 0 or discount_percentage > 100:
                raise ValueError("Discount percentage must be between 0 and 100.")
        except ValueError:
            log_error(f"Invalid discount percentage: {discount_percentage_str}")
            return jsonify({"error": "Invalid discount percentage. Must be a number between 0 and 100."}), 400

        # Fetch and update old products with the discount
        old_products = db.session.query(Product).filter(Product.created_at < cutoff_date).all()
        old_product_count = len(old_products)

        if old_product_count == 0:
            log_info(f"No products found before the cutoff date: {cutoff_date_str}")
            return jsonify({"message": "No products found before the specified cutoff date."}), 200

        # All discounted products are taken to the list
        discounted_products = []

        for product in old_products:
            original_price = product.price
            discount_amount = product.price * (discount_percentage / 100)
            product.price -= discount_amount
            product.discount = discount_percentage

            # Appending the details of the discounted product to the list
            discounted_products.append({
                "product_uuid": product.uuid,
                "product_brand": product.brand,
                "product_type": product.type,
                "product_model": product.model,
                "original_price": original_price,
                "new_price": product.price,
                "discount_percentage": discount_percentage
            })
        db.session.commit()

        log_info(f"Successfully applied a {discount_percentage}% discount to {old_product_count} old products.")
        notify_success("Clearance Sale Success",
                       f"Successfully applied a {discount_percentage}% discount to {old_product_count} products "
                       f"created before {cutoff_date_str}.\n \n "
                       f"Products are:\n" + "\n".join([str(product) for product in discounted_products]))
        return jsonify({
            "updated_count": old_product_count,
            "message": "Discounts applied to old products successfully.",
            "discounted_products": discounted_products
        }), 200

    except SQLAlchemyError as e:
        log_error(f"Database error during clearance sale: {e}")
        notify_failure("Clearance Sale Error", f"Database error during clearance sale: {e}")
        return jsonify({"error": "Database error occurred.", "details": str(e)}), 500

    except Exception as e:
        log_error(f"Unexpected error during clearance sale: {e}")
        notify_failure("Clearance Sale Error", f"Unexpected error during clearance sale: {e}")
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

        # Create the email body
        notify_success("Increase Product Price Success",
                       f"Successfully applied a {increase_percentage}% increase. \n \n updated count: {product_count} "
                       f" \n \n {updated_products} products"
                       f"created before start date : {start_date_str} to end date : {end_date_str}. ")

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
            - 400 Bad Request: Invalid date format.
            - 500 Internal Server Error: Database or server errors.
    """
    log_info("Starting to clear old stock.")
    try:
        cutoff_date_str = request.args.get('cutoff_date')
        if not cutoff_date_str:
            return jsonify({"error": "cutoff_date parameter is required."}), 400

        try:

            cutoff_date = datetime.strptime(cutoff_date_str, '%Y-%m-%d')
        except ValueError:
            log_error(f"Invalid date format: {cutoff_date_str}")
            return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

        # Fetch and delete old products
        old_products = db.session.query(Product).filter(Product.created_at < cutoff_date).all()
        old_product_count = len(old_products)

        if old_product_count == 0:
            log_info(f"No products found before the cutoff date: {cutoff_date_str}")
            notify_failure("Clear Old Stock Error",
                           f"No products found before the specified cutoff date : Products = {old_product_count}")
            return jsonify({"message": "No products found before the specified cutoff date."}), 200

        for product in old_products:
            db.session.delete(product)
        db.session.commit()

        log_info(f"Successfully cleared {old_product_count} old products.")
        notify_success("Clear Old Stock Success",
                       f"Successfully cleared {old_product_count} products created before {cutoff_date_str}.")

        return jsonify({"deleted_count": old_product_count, "message": "Old products cleared successfully."}), 200

    except SQLAlchemyError as e:
        log_error(f"Database error during old stock clearance: {e}")
        notify_failure("Clear Old Stock Error", f"Database error during old stock clearance: {e}")
        return jsonify({"error": "Database error occurred.", "details": str(e)}), 500

    except Exception as e:
        log_error(f"Unexpected error during old stock clearance: {e}")
        notify_failure("Clear Old Stock Error", f"Unexpected error during old stock clearance: {e}")
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
            notify_success("Product Search Success", "No products found matching the search criteria.")
            return jsonify({"message": "No products found matching your search criteria."}), 200

        for product in search_results:
            product.search_count += 1
        db.session.commit()

        # Successfully found matching products
        log_info("Products found matching the search criteria.")
        notify_success("Product Search Success \n \n",
                       f"Successfully found {len(search_results)} products i.e... "
                       f"{[product.to_dict() for product in search_results]}"
                       f"matching the search criteria.")
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
        log_info("Latest products fetched successfully.")
        notify_success("Fetch Latest Products Success \n \n",
                       f"Successfully fetched latest products {[product.to_dict() for product in latest_products]}.")
        return jsonify([product.to_dict() for product in latest_products])
    except Exception as e:
        log_error(f"Error fetching latest products: {e}")
        notify_failure("Fetch Latest Products Error", f"Failed to fetch latest products: {e}")
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
        latest_discounted_products = db.session.query(Product).filter(Product.discounts > 11).order_by(
            desc(Product.created_at)).all()
        log_debug(f"Latest discounted products retrieved: {latest_discounted_products}")
        if not latest_discounted_products:
            log_info("No latest discounted products found.")
        log_info("Latest discounted products fetched successfully.")
        notify_success("Fetch Latest Discounted Products Success",
                       f"Successfully fetched latest discounted products \n \n"
                       f"{[product.to_dict() for product in latest_discounted_products]}.")
        return jsonify([product.to_dict() for product in latest_discounted_products])
    except Exception as e:
        log_error(f"Error fetching latest discounted products: {e}")
        notify_failure("Fetch Latest Discounted Products Error",
                       f"Failed to fetch latest discounted products: {e}")
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
            notify_success("Fetch Products by Discount Success",
                           f"Successfully fetched products \n \n "
                           f"{[product.to_dict() for product in discounted_products]} sorted by discount.")
            return jsonify([product.to_dict() for product in discounted_products])
        else:
            log_info("No products with discounts found.")
            return jsonify({"error": "No discounted products found"}), 404
    except Exception as e:
        log_error(f"Error fetching products sorted by discount: {e}")
        notify_failure("Fetch Products by Discount Error",
                       f"Failed to fetch products sorted by discount: {e}")
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
        return jsonify({"error": "Both min_price and max_price are required"}), 400
    try:
        products = db.session.query(Product).filter(Product.price.between(min_price, max_price)).all()
        log_debug(f"Products in price range ({min_price}, {max_price}): {products}")
        if not products:
            log_info("No products found in the specified price range.")
        log_info("Products filtered by price range successfully.")
        notify_success("Filter Products by Price Range Success",
                       f"Successfully filtered products \n \n"
                       f"{[product.to_dict() for product in products]} by price range.")
        return jsonify([product.to_dict() for product in products])
    except Exception as e:
        log_error(f"Error filtering products by price range: {e}")
        notify_failure("Filter Products by Price Range Error",
                       f"Error filtering products by price range: {e}")
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
            return jsonify({"message": "No products match the specified criteria."}), 200

        log_info("Products filtered by specs successfully.")
        notify_success("Filter Products by Specs Success",
                       f"Successfully filtered products \n \n "
                       f"{[product.to_dict() for product in filtered_products]} by specs.")
        return jsonify([product.to_dict() for product in filtered_products])

    except json.JSONDecodeError as e:
        log_error(f"JSONDecodeError: {e}")
        return jsonify({"error": f"Invalid JSON format: {e}"}), 400
    except ValueError as ve:
        log_error(f"ValueError: {ve}")
        return jsonify({"error": f"Value error: {ve}"}), 400
    except Exception as e:
        log_error(f"Unexpected error: {e}")
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
            product_details = "\n".join([str(product.to_dict()) for product in recent_products])
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
            return jsonify({"error": "Invalid brand parameter."}), 400

        if types is not None and not types.strip():
            log_info("Invalid input: type parameter is empty.")
            return jsonify({"error": "Invalid type parameter."}), 400

        if model is not None and not model.strip():
            log_info("Invalid input: model parameter is empty.")
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
            return jsonify({"message": "No products found with the provided filters."}), 404

        log_info("Products fetched successfully.")
        # Prepare plain text content for the email
        products_list = "\n".join(
            [str(product.to_dict()) for product in products]
        )
        plain_text_content = f"Successfully fetched filtered products:\n\n{products_list}"
        notify_success("Fetch Products Success", plain_text_content)
        return jsonify([product.to_dict() for product in products])

    except SQLAlchemyError as e:
        log_error(f"Database error occurred while fetching products: {e}")
        notify_failure("Fetch Products Error", f"Failed to fetch products due to a database error: {e}")
        return jsonify({"error": "Could not fetch products due to a database error."}), 500

    except Exception as e:
        log_error(f"Error fetching products: {e}")
        notify_failure("Fetch Products Error", f"Failed to fetch products: {e}")
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
            # Notify success
            notify_success("Fetch Product Success",
                           f"Product with UUID {uuid} retrieved successfully and "
                           f"product is \n \n {(product.to_dict())}.")
            return jsonify(product.to_dict())
        else:
            log_info(f"Product with UUID {uuid} not found.")
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_error(f"Error fetching product by UUID: {e}")
        notify_failure("Fetch Product Error", f"Failed to fetch product with UUID {uuid}: {e}")
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
        log_info("Products filtered successfully.")
        notify_success("Filter Products Success",
                       f"Successfully filtered products \n \n {[product.to_dict() for product in products]}.")
        return jsonify([product.to_dict() for product in products])
    except Exception as e:
        log_error(f"Error filtering products: {e}")
        notify_failure("Filter Products Error", f"Error filtering products: {e}")
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
    valid_product = db.session.query(ValidProductDetails).filter_by(type=data['type'], brand=data['brand']
                                                                    ).first()

    # Check if the provided product details are valid
    if not valid_product:
        log_error("Invalid product, type, or brand.")
        notify_failure("Create Product Error", "Invalid product, type, or brand.")
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
        notify_success("Product Created", f"Product created successfully with UUID: {new_product.uuid}")
        return jsonify(new_product.to_dict()), 201
    except Exception as e:
        log_error(f"Error creating product: {e}")
        notify_failure("Create Product Error", f"Error creating product: {e}")
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
        notify_failure("Update Product Error", "Invalid product, type, or brand.")
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
            notify_success("Product Updated",
                           f"Product \n {product.to_dict()} \n updated successfully with UUID: {uuid}")
            return jsonify(product.to_dict()), 200
        else:
            log_info(f"Product with UUID {uuid} not found.")
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_error(f"Error updating product: {e}")
        notify_failure("Update Product Error", f"Error updating product: {e}")
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
            db.session.delete(product)
            db.session.commit()
            log_info(f"Product deleted successfully with UUID: {uuid}")
            notify_success("Product Deleted", f"Product deleted successfully with UUID: {uuid}")
            return jsonify({"message": "Product deleted successfully"}), 200
        else:
            log_info(f"Product with UUID {uuid} not found.")
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_error(f"Error deleting product: {e}")
        notify_failure("Delete Product Error", f"Error deleting product: {e}")
        return jsonify({"error": "Failed to delete product"}), 500


if __name__ == '__main__':
    app.run(debug=True)
