"""
This module defines the Product class for managing products in a database.

The Product class represents items in the 'productss' table, including details like the product's unique ID, type,
brand, model, price, discounts, specifications, and when it was created.

Classes:
    Product: Represents a product in the database with various attributes.

Functions:
    to_dict: Converts a Product object into a dictionary format.
"""
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, Integer, Date, VARCHAR
from sqlalchemy.ext.declarative import declarative_base

db = SQLAlchemy()
Base = declarative_base()


class Cart(db.Model):
    """
    The Cart class represents a shopping cart entry.

    This class maps to the 'cart' table and includes information about which user added which product to their cart,
    along with the quantity.

    Attributes:
        id (int): Primary key for the cart item.
        user_name (str): Foreign key referencing the username from the 'user_registration' table.
        product_uuid (str): Foreign key referencing the UUID from the 'productss' table.
        quantity (int): Quantity of the product added to the cart.
    """
    __tablename__ = 'cart'
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(50), db.ForeignKey('user_registration.username'))
    product_uuid = db.Column(UUID(as_uuid=True), db.ForeignKey('productss.uuid'))
    quantity = db.Column(db.Integer, default=1)
    purchase_datetime = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships with unique backref names
    user = db.relationship('User_Registration_Form', backref='cart_items')  # Unique backref name
    product = db.relationship('Product', backref='carts')  # Unique backref name

    def to_dict(self):
        """
            Converts the Cart instance into a dictionary.

            Returns:
                dict: A dictionary containing the cart item's details such as id, user_name, product_uuid, and quantity.
            """
        return {
            "id": self.id,
            "user_name": self.user_name,
            "product_uuid": str(self.product_uuid) if self.product_uuid else None,
            "quantity": self.quantity,
            "purchase_datetime": self.purchase_datetime
        }


class Product(db.Model):
    """
    The Product class represents a product in the database.

    This class maps to the 'productss' table and includes information about each product, such as its unique ID,
    type, brand, model, price, discounts, specifications, and creation date.

    Attributes:
        uuid (str): Unique identifier for the product.
        type (str): The type or category of the product.
        brand (str): The brand name of the product.
        model (str): The model name or number of the product.
        price (float): The price of the product.
        discounts (float): The discount applied to the product.
        specs (dict): Additional details about the product in JSON format.
        created_at (datetime): The date and time when the product was added to the database.
        delivery_time_days (int): Estimated delivery time in days.
    Methods:
        to_dict: Returns a dictionary representation of the product, including all its details.
    """
    __tablename__ = "productss"
    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = db.Column(db.String(50))
    brand = db.Column(db.String(50))
    model = db.Column(db.String(100))
    price = db.Column(db.Float)
    discounts = db.Column(db.Float)
    specs = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    search_count = db.Column(db.Integer, default=0)
    delivery_time_days = db.Column(db.Integer, default=7)  # Default delivery time 7 days / changeable accordingly

    # Relationship to Cart
    # cart_entries = db.relationship('Cart', backref='product')

    def to_dict(self):
        """
        Converts the Product instance into a dictionary.

        This method returns a dictionary where each key corresponds to a product attribute, and the values are the
        product's details. This is useful for easily converting the product data into JSON format for APIs or other
        uses.

        Returns: dict: A dictionary containing the product's details such as UUID, type, brand, model, price,
        discounts, specs, creation date, search count, delivery time days.
        """
        return {
            "uuid": self.uuid,
            "type": self.type,
            "brand": self.brand,
            "model": self.model,
            "price": self.price,
            "discounts": self.discounts,
            "specs": self.specs,
            "created_at": self.created_at.isoformat(),
            "search_count": self.search_count,
            "delivery_time_days": self.delivery_time_days
        }


class ValidProductDetails(db.Model):
    """
    A SQLAlchemy model representing valid product details.

    Attributes:
        id (int): The primary key for the record.
        product (str): The name of the product. This field is unique and cannot be null.
        type (str): The type or category of the product. This field cannot be null.
        brand (str): The brand associated with the product. This field cannot be null.
    """

    __tablename__ = 'valid_product_details'

    id = Column(Integer, primary_key=True)
    product = Column(String(100), nullable=False, unique=True)
    type = Column(String(100), nullable=False)
    brand = Column(String(100), nullable=False)
    search_count = Column(Integer, default=0)

    def to_dict(self):
        """
        Convert the model instance into a dictionary.

        Returns: dict: A dictionary containing the product details with keys 'id', 'product', 'type', 'brand' and
        search_count.
        """
        return {
            "id": self.id,
            "product": self.product,
            "type": self.type,
            "brand": self.brand,
            "search_count": self.search_count
        }


class User_Registration_Form(db.Model):
    """
    The User_Registration_Form class represents a user registration form.

    This class maps to the 'user_registration' table and includes information about users, such as their name,
    date of birth, and contact details.

    Attributes:
        name (str): The username, used as the primary key.
        fname (str): The first name of the user.
        lname (str): The last name of the user.
        date (date): The date of birth of the user.
        password (str): The user's password.
        cpassword (str): The user's confirmed password.
        mail (str): The email address of the user.
        ph (int): The phone number of the user.
        add (str): The address of the user.
        category (str): The category of the user.
        created_date (date): The date when the user was registered.
    """
    __tablename__ = "user_registration"
    name = Column("username", String(50), primary_key=True)
    fname = Column("firstname", String(100))
    lname = Column("lastname", String(100))
    date = Column("dob", Date)
    password = Column("pwd", VARCHAR)
    cpassword = Column("confirm_password", VARCHAR)
    mail = Column("email", VARCHAR)
    ph = Column("phone", Integer)
    add = Column("address", VARCHAR)
    category = Column("category", String)
    created_date = Column("created_datetime", Date)

    def to_dict(self):
        """
        Converts the User_Registration_Form instance into a dictionary.

        Returns: dict: A dictionary containing the user's details such as username, firstname, lastname, dob, email,
        phone, address, and created_date.
        """
        return {
            "username": self.name,
            "firstname": self.fname,
            "lastname": self.lname,
            "dob": self.date.isoformat() if self.date else None,
            "email": self.mail,
            "phone": self.ph,
            "address": self.add,
            "category": self.category,
            "created_date": self.created_date.isoformat() if self.created_date else None
        }
