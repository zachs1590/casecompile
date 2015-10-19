# By default, Django creates this file whenever a new app template is
# processed; the thinking is, define your models in appname.models.py
# and your Django admin settings in appname.admin.py. But all too
# often this separates the admin settings too far from the model
# definition code they depend on. Also, if the Django admin is a
# substantial part of the "deliverable" product to the client, then
# admin settings will be tied even more closely to the model they
# represent, making maintenance difficult if they are kept separate.
#
# Policy decision: Django admin settings should be stored with the
# models, and registration should happen in models.py.
