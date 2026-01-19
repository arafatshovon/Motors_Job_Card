# Motors-Job-Card

## Live Access

Link : [http://192.168.100.113:9001](http://192.168.100.113:9001)

```
username : misadmin
password : acimisai 
```

### How to Start and Stop the Project
First login into server and open a terminal, Then type the following command for starting or stoping the project

```
sudo systemctl start/stop/status/restart motors_job_card.service
```

### API
```
Swagger UI: http://192.168.100.113:9001/api/docs/

OpenAPI schema: http://192.168.100.113:9001/api/schema/

Checkout API: http://192.168.100.113:9001/api/checkout?chassis=RG642003173&mileage=4000

Search bike names (typeahead): http://192.168.100.113:9001/api/bikes/search?query=cb&limit=20&offset=0

Bike names from warranty claims only: http://192.168.100.113:9001/api/bikes/names

Top warranty parts: http://192.168.100.113:9001/api/warranty/top-parts?limit=30

Top warranty parts (last 2 years): http://192.168.100.113:9001/api/warranty/top-parts?period=2y

Top warranty parts (last 6 months): http://192.168.100.113:9001/api/warranty/top-parts?months=6

Top warranty parts by bike model (last 2 years): http://192.168.100.113:9001/api/warranty/top-parts/by-bike-model?period=2y&limit=30

Top warranty parts for a specific bike model (last 28 months): http://192.168.100.113:9001/api/warranty/top-parts/for-bike-model?bike_model=Model%20Name&period=28m&limit=5
```
