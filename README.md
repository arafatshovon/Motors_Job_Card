# Motors-Job-Card

## Live Access

Link : http://192.168.100.113:9001

```
username : misadmin
password : acimisai 
```

### Open a Screen and Host
```
screen -S jobcard [Create Screen]
screen -r jobcard [Read Screen]
cd Motors-Job-Card
source venv/bin/activate
python manage.py runserver 0.0.0.0:9001
```
### API

```
http://192.168.101.63:9000/checkout_api?chassis=RG642003173&mileage=4000
```