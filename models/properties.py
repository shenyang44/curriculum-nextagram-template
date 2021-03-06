import peewee as pw
from models.base_model import BaseModel
from models.user import User
from playhouse.hybrid import hybrid_property
from config import S3_LOCATION


class Property(BaseModel):
    name = pw.CharField(unique=True, null=False)
    houses = pw.IntegerField(default=0)
    mortgaged = pw.BooleanField(default=False)
    user = pw.ForeignKeyField(User, backref='properties')
    house_price = pw.IntegerField()
    category = pw.CharField()
    image = pw.CharField(null=True)
    price = pw.IntegerField()

    def validate(self):
        return

    @hybrid_property
    def is_owned(self):
        if self.user.username == 'Banker':
            return False
        else:
            return True

    @hybrid_property
    def image_url(self):
        return(S3_LOCATION + str(self.image))
