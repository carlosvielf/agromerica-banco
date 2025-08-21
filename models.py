from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ImageRecord(db.Model):
    __tablename__ = 'image_records'
    
    id = db.Column(db.Integer, primary_key=True)
    original_image_path = db.Column(db.String(255), nullable=False)
    processed_image_path = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    detection_results = db.Column(db.JSON)  # Store detection results as JSON
    filename = db.Column(db.String(255))
    
    def to_dict(self):
        return {
            'id': self.id,
            'original_image_path': self.original_image_path,
            'processed_image_path': self.processed_image_path,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'detection_results': self.detection_results,
            'filename': self.filename
        }

class Part(db.Model):
    __tablename__ = 'parts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f'<Part {self.name}>'

    @property
    def in_stock(self):
        """Retorna True se houver quantidade positiva em estoque."""
        try:
            return int(self.quantity) > 0
        except Exception:
            return False
