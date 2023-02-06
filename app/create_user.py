from django.contrib.auth.models import User

user = User.objects.create(
    username='motoradmin',
    email='imansiam135@gmail.com',
)
password = '1234'
user.set_password(password)
user.save()