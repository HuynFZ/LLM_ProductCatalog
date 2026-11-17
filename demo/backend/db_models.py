from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(String(50), primary_key=True)
    name = Column(String(255))
    product_type = Column(String(100))        # Level 3: T-shirt, Dress, Shirt, Trousers...
    product_group = Column(String(100))       # Level 2: Garment Upper body, Shoes, Accessories...
    gender_group = Column(String(50))         # Level 1: Ladieswear, Menswear, Baby/Children, Divided, Sport
    department = Column(String(100))          # Nhóm phong cách: Jersey Basic, Knitwear...
    pattern = Column(String(50))              # Họa tiết: Solid, Stripe, Front print, Denim...
    detail_desc = Column(String(1000))
    
    variants = relationship("ProductVariant", back_populates="product")

class ProductVariant(Base):
    __tablename__ = "product_variants"  
    variant_id = Column(String(100), primary_key=True)
    product_id = Column(String(50), ForeignKey("products.id"))
    article_id = Column(String(50))   # Mã SKU của từng màu (dùng để load file ảnh chính xác)
    color = Column(String(50))
    size = Column(String(10))
    price = Column(Float)
    stock_quantity = Column(Integer)
    
    product = relationship("Product", back_populates="variants")