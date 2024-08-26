import json
from flask import Flask, jsonify, request
from db_connections.configurations import DATABASE_URL
from email_setup.email_operations import notify_success, notify_failure
from user_models.tables import db, Product, ValidProductDetails
from logging_package.logging_utility import log_info, log_error, log_debug
from sqlalchemy import desc
from datetime import datetime, timedelta

# Create Flask app instance
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Initialize SQLAlchemy with the Flask app
db.init_app(app)


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
        notify_success("Fetch Latest Products Success", "Successfully fetched latest products.")
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
        notify_success("Fetch Latest Discounted Products Success", "Successfully fetched latest discounted products.")
        return jsonify([product.to_dict() for product in latest_discounted_products])
    except Exception as e:
        log_error(f"Error fetching latest discounted products: {e}")
        notify_failure("Fetch Latest Discounted Products Error", f"Failed to fetch latest discounted products: {e}")
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
                           "Successfully fetched products sorted by discount.")
            return jsonify([product.to_dict() for product in discounted_products])
        else:
            log_info("No products with discounts found.")
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
        return jsonify({"error": "Both min_price and max_price are required"}), 400
    try:
        products = db.session.query(Product).filter(Product.price.between(min_price, max_price)).all()
        log_debug(f"Products in price range ({min_price}, {max_price}): {products}")
        if not products:
            log_info("No products found in the specified price range.")
        log_info("Products filtered by price range successfully.")
        notify_success("Filter Products by Price Range Success", "Successfully filtered products by price range.")
        return jsonify([product.to_dict() for product in products])
    except Exception as e:
        log_error(f"Error filtering products by price range: {e}")
        notify_failure("Filter Products by Price Range Error", f"Error filtering products by price range: {e}")
        return jsonify({"error": "Failed to filter products by price range"}), 500


@app.route('/products/specs', methods=['GET'])
def filter_products_by_specs():
    """
    Filters products based on specifications provided in the query parameters.

    This route filters products by specifications such as color, size, etc., based on the query parameters.

    Query Parameters:
        specs (str): A JSON string where keys are specification names and values are the desired values.

    Returns:
        Response: JSON array of products that match the specified criteria.
    """
    log_info("Starting filter products by specs.")
    specs_query = request.args.get('specs')
    if specs_query:
        try:
            specs = json.loads(specs_query)  # Convert JSON string to dictionary
            # Fetch all products from the database
            products = db.session.query(Product).all()

            # Filter products in Python if database JSON querying is not available
            filtered_products = [
                product for product in products
                if all(product.specs.get(key) == value for key, value in specs.items())
            ]

            log_debug(f"Filtered products by specs: {filtered_products}")
            if not filtered_products:
                log_info("No products match the spec criteria.")
            log_info("Products filtered by specs successfully.")
            notify_success("Filter Products by Specs Success", "Successfully filtered products by specs.")
            return jsonify([product.to_dict() for product in filtered_products])
        except json.JSONDecodeError:
            log_error("Invalid JSON format for specs.")
            notify_failure("Filter Products by Specs Error", "Invalid JSON format for specs.")
            return jsonify({"error": "Invalid JSON format for specs"}), 400
        except Exception as e:
            log_error(f"Error filtering products by specs: {e}")
            notify_failure("Filter Products by Specs Error", f"Error filtering products by specs: {e}")
            return jsonify({"error": "Failed to filter products by specs"}), 500
    else:
        return jsonify({"error": "No specs provided for filtering"}), 400


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
        if not recent_products:
            log_info("No products found created in the last 24 hours.")
        else:
            log_info("Products created in the last 24 hours fetched successfully.")

        notify_success("Fetch Recent Products Success", "Successfully fetched products created in the last 24 hours.")
        return jsonify([product.to_dict() for product in recent_products])
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
    Retrieves all products from the database.

    This route fetches all products and returns them as a JSON array.

    Returns:
        Response: JSON array of all products.
    """
    log_info("Starting to fetch all products.")
    try:
        products = db.session.query(Product).all()
        log_debug(f"Products retrieved: {products}")
        if not products:
            log_info("No products found in the database.")
        log_info("Products fetched successfully.")
        notify_success("Fetch Products Success", "Successfully fetched all products.")
        return jsonify([product.to_dict() for product in products])
    except Exception as e:
        log_error(f"Error fetching products: {e}")
        notify_failure("Fetch Products Error", f"Error fetching products: {e}")
        return jsonify({"error": "Failed to fetch products"}), 500


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
            notify_success("Fetch Product Success", f"Product with UUID {uuid} retrieved successfully.")
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
        notify_success("Filter Products Success", "Successfully filtered products.")
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
            notify_success("Product Updated", f"Product updated successfully with UUID: {uuid}")
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
