import peewee as pw
from models.base_model import BaseModel
from playhouse.hybrid import hybrid_property
from config import S3_LOCATION
from models.user import User


class Card(BaseModel):
    category = pw.CharField()
    image = pw.CharField(null=True)
    description = pw.CharField(null=True)
    order = pw.IntegerField(null=True, unique=True)
    user = pw.ForeignKeyField(User, backref='card', null=True)
    activated = pw.BooleanField(default=False)

    @hybrid_property
    def image_url(self):
        return(S3_LOCATION + self.image)

    def validate(self):
        return
