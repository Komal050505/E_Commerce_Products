"""
This module defines the Product class for managing products in a database.

The Product class represents items in the 'productss' table, including details like the product's unique ID, type, brand, model, price, discounts, specifications, and when it was created.

Classes:
    Product: Represents a product in the database with various attributes.

Functions:
    to_dict: Converts a Product object into a dictionary format.
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String
from datetime import datetime

db = SQLAlchemy()


class Product(db.Model):
    """
    The Product class represents a product in the database.

    This class maps to the 'productss' table and includes information about each product, such as its unique ID, type, brand, model, price, discounts, specifications, and creation date.

    Attributes:
        uuid (str): Unique identifier for the product.
        type (str): The type or category of the product.
        brand (str): The brand name of the product.
        model (str): The model name or number of the product.
        price (float): The price of the product.
        discounts (float): The discount applied to the product.
        specs (dict): Additional details about the product in JSON format.
        created_at (datetime): The date and time when the product was added to the database.

    Methods:
        to_dict: Returns a dictionary representation of the product, including all its details.
    """
    __tablename__ = "productss"
    uuid = db.Column(db.String, primary_key=True)
    type = db.Column(db.String(50))
    brand = db.Column(db.String(50))
    model = db.Column(db.String(100))
    price = db.Column(db.Float)
    discounts = db.Column(db.Float)
    specs = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Converts the Product instance into a dictionary.

        This method returns a dictionary where each key corresponds to a product attribute, and the values are the
        product's details. This is useful for easily converting the product data into JSON format for APIs or other
        uses.

        Returns: dict: A dictionary containing the product's details such as UUID, type, brand, model, price,
        discounts, specs, and creation date.
        """
        return {
            "uuid": self.uuid,
            "type": self.type,
            "brand": self.brand,
            "model": self.model,
            "price": self.price,
            "discounts": self.discounts,
            "specs": self.specs,
            "created_at": self.created_at.isoformat()
        }


class ValidProductDetails(db.Model):
    __tablename__ = 'valid_product_details'

    id = Column(db.Integer, primary_key=True)
    product = Column(String(100), nullable=False, unique=True)
    type = Column(String(100), nullable=False)
    brand = Column(String(100), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "product": self.product,
            "type": self.type,
            "brand": self.brand
        }
