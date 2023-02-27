# Motors-Job-Card

## Live Access

Link : http://192.168.101.63:9000

```
username : misadmin
password : acimisai 
```

## Server Hosting

### Server Login
```
ssh aci-mis-ai@192.168.101.63
Pass : 987654321
```

### Open a Screen and Host
```
screen -S jobcard [Create Screen]
screen -r jobcard [Read Screen]
cd Motors-Job-Card
source venv/bin/activate
python manage.py runserver 0.0.0.0:9000
```
### API

```
http://192.168.101.63:9000/checkout_api?chassis=RG642003173&mileage=4000
```