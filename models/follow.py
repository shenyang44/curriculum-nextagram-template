from models.base_model import BaseModel
from models.user import User
import peewee as pw


class Follow(BaseModel):
    fan = pw.ForeignKeyField(User, backref='idols')
    idol = pw.ForeignKeyField(User, backref='fans')
    authorized = pw.BooleanField(default=False)

    def validate(self):
        return
